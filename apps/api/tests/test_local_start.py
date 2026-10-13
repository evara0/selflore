from unittest.mock import MagicMock

import psycopg
import pytest

from app import local_start


@pytest.fixture
def configured(monkeypatch, tmp_path):
    password_file = tmp_path / 'local' / 'pgpass.conf'
    monkeypatch.setattr(local_start, 'PASSWORD_FILE', password_file)
    monkeypatch.setenv('SELFLORE_ENV', 'dev')
    monkeypatch.setenv('SELFLORE_DATABASE_URL', 'host=127.0.0.1 port=6171 dbname=selflore_dev user=selflore_dev_app')
    monkeypatch.setenv('PGPASSFILE', str(password_file))
    return password_file


@pytest.mark.parametrize('connection', [
    'host=remote.example port=6171 dbname=selflore_dev user=selflore_dev_app',
    'host=127.0.0.1 port=6171 dbname=selflore_prod user=selflore_dev_app',
    'host=127.0.0.1 port=6171 dbname=selflore_dev user=selflore_dev_migrator',
    'host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_app',
    'host=127.0.0.1 port=6171 dbname=selflore_dev user=selflore_dev_app hostaddr=10.0.0.1',
])
def test_wrong_target_never_connects(configured, monkeypatch, connection):
    connect = MagicMock()
    monkeypatch.setattr(local_start.psycopg, 'connect', connect)
    monkeypatch.setenv('SELFLORE_DATABASE_URL', connection)
    assert local_start.main(['--check']) == 1
    connect.assert_not_called()


def test_missing_credential_never_connects(configured, monkeypatch, capsys):
    connect = MagicMock()
    monkeypatch.setattr(local_start.psycopg, 'connect', connect)
    assert local_start.main(['--check']) == 1
    assert '-Configure' in capsys.readouterr().out
    connect.assert_not_called()


def test_noninteractive_password_prompt_is_rejected(configured, monkeypatch, capsys):
    prompt = MagicMock()
    monkeypatch.setattr(local_start.getpass, 'getpass', prompt)
    monkeypatch.setattr(local_start.sys.stdin, 'isatty', lambda: False)
    assert local_start.main(['--configure']) == 1
    assert '交互终端' in capsys.readouterr().out
    prompt.assert_not_called()


def test_configuration_removes_inherited_privileged_credentials(configured, monkeypatch):
    for key in ('PGPASSWORD', 'PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'SELFLORE_MIGRATOR_PASSWORD'):
        monkeypatch.setenv(key, 'must-not-be-used')
    local_start.configuration()
    import os
    assert all(key not in os.environ for key in ('PGPASSWORD', 'PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'SELFLORE_MIGRATOR_PASSWORD'))


def test_secret_parse_or_database_error_not_printed(configured, monkeypatch, capsys):
    monkeypatch.setenv('SELFLORE_DATABASE_URL', 'secret-that-must-not-be-printed')
    assert local_start.main(['--check']) == 1
    assert 'secret-that-must-not-be-printed' not in capsys.readouterr().out
    monkeypatch.setenv('SELFLORE_DATABASE_URL', 'host=127.0.0.1 port=6171 dbname=selflore_dev user=selflore_dev_app')
    configured.parent.mkdir(); configured.write_text('test-only-placeholder')
    monkeypatch.setattr(local_start.psycopg, 'connect', MagicMock(side_effect=psycopg.OperationalError('SENSITIVE_PASSWORD')))
    assert local_start.main(['--check']) == 1
    output = capsys.readouterr().out
    assert 'SENSITIVE_PASSWORD' not in output and '6171' in output


def test_failed_password_confirmation_preserves_existing_file(configured):
    configured.parent.mkdir(); configured.write_text('existing')
    with pytest.raises(local_start.LocalConfigurationError):
        local_start.save_password('new', 'different')
    assert configured.read_text() == 'existing'


def test_password_escape_and_acl_failure_are_atomic(configured, monkeypatch):
    monkeypatch.setattr(local_start, 'protect_directory', lambda directory: directory.mkdir(parents=True, exist_ok=True))
    password = r"colon:slash\hash#quotes'$value"
    local_start.save_password(password, password)
    assert configured.read_text() == "127.0.0.1:6171:selflore_dev:selflore_dev_app:colon\\:slash\\\\hash#quotes'$value\n"
    before = configured.read_bytes()
    def fail(_):
        raise local_start.LocalConfigurationError('cannot protect')
    monkeypatch.setattr(local_start, 'protect_directory', fail)
    with pytest.raises(local_start.LocalConfigurationError):
        local_start.save_password('replacement', 'replacement')
    assert configured.read_bytes() == before


def test_preflight_queries_are_readonly_and_never_read_history(configured, monkeypatch):
    configured.parent.mkdir(); configured.write_text('test-only-placeholder')
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [('selflore_dev', 'selflore_dev_app', 180004), 'app.account_audit', (False, False)]
    monkeypatch.setattr(local_start.psycopg, 'connect', MagicMock(return_value=connection))
    local_start.check_database(local_start.configuration())
    queries = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert queries[0] == 'SET TRANSACTION READ ONLY'
    assert all(not any(word in query.upper() for word in ('INSERT ', 'UPDATE ', 'DELETE ', 'GRANT ', 'CREATE TABLE', 'SCHEMA_MIGRATIONS')) for query in queries)


def test_existing_listener_is_not_stopped(configured, monkeypatch):
    listener = MagicMock()
    listener.__enter__.return_value.bind.side_effect = OSError('occupied')
    monkeypatch.setattr(local_start.socket, 'socket', MagicMock(return_value=listener))
    with pytest.raises(local_start.LocalConfigurationError, match='24566'):
        local_start.check_port()
