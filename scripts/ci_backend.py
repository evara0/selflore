"""Run existing API tests in owned, loopback-only disposable PG18 clusters."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import sys
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PORTS = (6179, 6180)


def clean_environment(values: dict[str, str]) -> dict[str, str]:
    result = {k: v for k, v in values.items() if not k.startswith(('PG', 'SELFLORE_'))}
    result.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    return result


def require_free_ports(ports: tuple[int, ...] = PORTS) -> None:
    sockets = []
    try:
        for port in ports:
            sock = socket.socket()
            sockets.append(sock)
            try:
                sock.bind(('127.0.0.1', port))
            except OSError as error:
                raise RuntimeError(f'test port {port} is occupied; no process was stopped') from error
    finally:
        for sock in sockets:
            sock.close()


def private_directory(path: Path, root: Path) -> None:
    if '..' in path.parts or not path.resolve().is_relative_to(root.resolve()):
        raise RuntimeError('cache directory must stay inside repository')
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise RuntimeError('linked cache path refused')
        if part == root:
            break
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        path.chmod(0o700)


def validate_junit(path: Path) -> dict[str, int]:
    tree = ET.parse(path)
    cases = list(tree.iter('testcase'))
    result = {'total': len(cases), 'failed': 0, 'skipped': 0}
    for case in cases:
        result['failed'] += int(case.find('failure') is not None or case.find('error') is not None)
        result['skipped'] += int(case.find('skipped') is not None)
    bad_totals = any(int(node.get(key, '0')) != 0 for node in tree.iter()
                     if node.tag in {'testsuite', 'testsuites'} for key in ('errors', 'failures', 'skipped'))
    if not cases or result['failed'] or result['skipped'] or bad_totals or list(tree.iter('error')) or list(tree.iter('failure')):
        raise RuntimeError(f'backend report is not a complete pass: {result}')
    return result


class Cluster:
    def __init__(self, binary: Path, folder: Path, port: int, env: dict[str, str]):
        if port not in PORTS:
            raise ValueError('only disposable test ports are supported')
        self.binary, self.folder, self.port, self.env = binary, folder, port, env
        self.data = folder / 'pgdata'
        self.start_attempted = False

    def tool(self, name: str) -> Path:
        return self.binary / (name + ('.exe' if os.name == 'nt' else ''))

    def command(self, name: str, args: list[str]) -> None:
        with (self.folder / f'{name}.log').open('ab') as log:
            subprocess.run([str(self.tool(name)), *args], env=self.env, check=True,
                           stdout=log, stderr=subprocess.STDOUT, timeout=90)

    def start(self) -> None:
        self.command('initdb', ['-D', str(self.data), '-U', 'postgres', '-A', 'trust', '--encoding=UTF8', '--no-locale'])
        # PGDG's compiled socket directory is not writable by an ordinary runner.
        # All CI clients use loopback TCP, including the policy test cluster.
        with (self.data / 'postgresql.conf').open('a', encoding='utf-8') as config:
            config.write("\nunix_socket_directories = ''\n")
        self.start_attempted = True
        startup_log = self.folder / 'postgres.log'
        try:
            self.command('pg_ctl', ['-D', str(self.data), '-l', str(startup_log),
                                    '-o', f'-h 127.0.0.1 -p {self.port}', '-w', 'start'])
        except subprocess.SubprocessError:
            # This log only covers startup, before credentials or SQL are sent.
            if startup_log.is_file():
                print(startup_log.read_text(encoding='utf-8', errors='replace')[-16000:], file=sys.stderr)
            raise

    def stop(self) -> None:
        if self.start_attempted and (self.data / 'postmaster.pid').exists():
            self.command('pg_ctl', ['-D', str(self.data), '-m', 'fast', '-w', 'stop'])
        if (self.data / 'postmaster.pid').exists():
            raise RuntimeError(f'owned test cluster {self.port} did not stop')


@contextmanager
def owned_clusters(clusters: list[Cluster]):
    attempted = []
    try:
        for cluster in clusters:
            attempted.append(cluster)
            cluster.start()
        yield
    finally:
        failures = []
        for cluster in reversed(attempted):
            try:
                cluster.stop()
            except Exception as error:
                failures.append(f'{cluster.port}: {type(error).__name__}')
        if failures:
            raise RuntimeError('owned cluster cleanup failed: ' + ', '.join(failures))


def run(binary: Path) -> int:
    require_free_ports()
    env = clean_environment(dict(os.environ))
    binary = binary.resolve()
    for tool in ('initdb', 'pg_ctl', 'pg_dump', 'pg_restore'):
        path = binary / (tool + ('.exe' if os.name == 'nt' else ''))
        version = subprocess.check_output([str(path), '--version'], env=env, text=True)
        if not re.search(r'\b18(?:\.|\b)', version):
            raise RuntimeError('PostgreSQL 18 tools required')
    run_id = uuid4().hex
    folder = ROOT / '.cache/card-tests' / ('ci-' + run_id)
    policy = ROOT / '.cache/registration-policy' / ('ci-' + run_id)
    reports = ROOT / '.cache/ci-reports'
    for directory in (folder, policy, reports):
        private_directory(directory, ROOT)
    # Prevent libpq from falling back to any developer's default credential file.
    pgpass = folder / 'empty.pgpass'
    pgpass.write_text('', encoding='utf-8')
    if os.name != 'nt':
        pgpass.chmod(0o600)
    env.update(PGPASSFILE=str(pgpass), SELFLORE_ENV='dev', SELFLORE_TEST_ISOLATED='1',
               SELFLORE_POLICY_TEST_ISOLATED='1', SELFLORE_PG_BIN=str(binary),
               SELFLORE_MIGRATOR_PASSWORD=secrets.token_urlsafe(24), SELFLORE_APP_PASSWORD=secrets.token_urlsafe(24),
               SELFLORE_TEST_APP_DSN='host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_app',
               SELFLORE_TEST_MIGRATOR_DSN='host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_migrator')
    report = reports / f'backend-{run_id}.xml'
    summary = reports / f'backend-{run_id}.json'
    state: dict = {'status': 'running', 'ports': list(PORTS), 'run_id': run_id}
    clusters = [Cluster(binary, folder, 6179, env), Cluster(binary, policy, 6180, env)]
    try:
        with owned_clusters(clusters):
            print('Bootstrapping owned 6179 test database; 6180 remains empty.', flush=True)
            setup = ('from app.db_bootstrap import Target,bootstrap; from app.db_migrate import migrate; '
                     "bootstrap(Target('dev','127.0.0.1',6179,'postgres')); migrate('dev','127.0.0.1',6179)")
            subprocess.run([sys.executable, '-B', '-c', setup], cwd=ROOT / 'apps/api', env=env, check=True, timeout=120)
            print('Running API tests (no skips permitted).', flush=True)
            result = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                                     '--basetemp', str(ROOT / '.cache/card-tests' / ('p-' + run_id[:8])), '--junitxml', str(report)],
                                    cwd=ROOT / 'apps/api', env=env, timeout=600)
            state['tests'] = validate_junit(report)
            if result.returncode:
                raise RuntimeError(f'pytest failed with exit code {result.returncode}')
        state.update(status='passed', owned_clusters_stopped=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        state.update(status='failed', error=type(error).__name__, owned_clusters_stopped=all(
            not (cluster.data / 'postmaster.pid').exists() for cluster in clusters))
        print(f'Backend CI failed: {type(error).__name__}: {error}', file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        summary.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        print(f'Backend report: {summary.relative_to(ROOT)}', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin', type=Path, default=os.environ.get('SELFLORE_PG_BIN'))
    args = parser.parse_args()
    if args.pg_bin is None:
        parser.error('provide --pg-bin or SELFLORE_PG_BIN pointing to PostgreSQL 18 tools')

    def interrupted(signum, frame):
        raise KeyboardInterrupt('CI interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return run(args.pg_bin)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Backend CI preflight failed: {type(error).__name__}: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
