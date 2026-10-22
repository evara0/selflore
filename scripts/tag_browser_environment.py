"""Own a fresh 6179 database and 24568 API for unified-tag browser acceptance."""
from pathlib import Path
import os
import subprocess
import sys
from uuid import uuid4
from ci_backend import ROOT, Cluster, clean_environment, require_free_ports, private_directory


def main():
    require_free_ports((6179,24568))
    binary=Path(os.environ['SELFLORE_PG_BIN']).resolve()
    env=clean_environment(dict(os.environ))
    folder=ROOT/'.cache/card-tests'/('browser-'+uuid4().hex[:8])
    private_directory(folder,ROOT)
    pgpass=folder/'empty.pgpass'; pgpass.write_text('')
    env.update(PGPASSFILE=str(pgpass),SELFLORE_ENV='dev',SELFLORE_TEST_ISOLATED='1',
        SELFLORE_MIGRATOR_PASSWORD=uuid4().hex,SELFLORE_APP_PASSWORD=uuid4().hex,
        SELFLORE_DATABASE_URL='host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_app',
        SELFLORE_ALLOW_REGISTRATION='true',SELFLORE_ALLOWED_ORIGINS='http://127.0.0.1:24568',
        SELFLORE_MEDIA_ROOT=str(folder/'media'),SELFLORE_MEDIA_OPS_ROOT=str(folder/'ops'))
    cluster=Cluster(binary,folder,6179,env); server=None
    try:
        cluster.start()
        setup="""from app.db_bootstrap import Target,bootstrap
from app.db_migrate import migrate
from app.media_storage import initialize,MediaConfig
bootstrap(Target('dev','127.0.0.1',6179,'postgres'))
migrate('dev','127.0.0.1',6179)
initialize(MediaConfig.load())
"""
        subprocess.run([sys.executable,'-c',setup],cwd=ROOT/'apps/api',env=env,check=True)
        print('Browser environment owned by this run: '+str(folder),flush=True)
        server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','24568','--no-access-log'],cwd=ROOT/'apps/api',env=env)
        print('To stop gracefully, create: '+str(folder/'stop-requested'),flush=True)
        while server.poll() is None and not (folder/'stop-requested').exists():
            try:
                server.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        if server and server.poll() is None:
            server.terminate(); server.wait(timeout=20)
        cluster.stop()
        print('Owned browser server and database stopped.',flush=True)


if __name__=='__main__': main()
