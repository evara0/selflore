import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app import db_backup


@pytest.fixture
def bundle(monkeypatch, tmp_path):
    root = tmp_path / 'private-backups'
    root.mkdir()
    monkeypatch.setattr(db_backup, 'BACKUPS', root)
    path = root / 'dev-sample'
    path.mkdir()
    dump = path / 'selflore_dev.dump'
    dump.write_bytes(b'synthetic-test-archive')
    manifest = {'format':'selflore-backup-v1','source':{'host':'127.0.0.1','port':6171,'database':'selflore_dev','role':'selflore_dev_migrator','pg_major':18},'snapshot_consistent':True,'dump_sha256':db_backup.file_hash(dump),'signature':{'tables':{'app.cards':{'rows':0,'sha256':'test-only'}},'structure':{'history':[['0001_identity','test-only']]}}}
    (path/'manifest.json').write_text(json.dumps(manifest))
    return path


def test_changed_archive_refused_before_any_tool_or_cluster(bundle, monkeypatch):
    (bundle/'selflore_dev.dump').write_bytes(b'changed')
    tools = MagicMock()
    monkeypatch.setattr(db_backup,'run_tool',tools)
    with pytest.raises(db_backup.BackupError,match='校验和'):
        db_backup.rehearse(bundle,Path('.'))
    tools.assert_not_called()


@pytest.mark.parametrize('bad',['[]','not json','{}'])
def test_invalid_manifest_refused(bundle,bad):
    (bundle/'manifest.json').write_text(bad)
    with pytest.raises(db_backup.BackupError):
        db_backup.validate_bundle(bundle)


def test_external_bundle_refused_before_file_reads(tmp_path):
    with pytest.raises(db_backup.BackupError,match='私有备份目录'):
        db_backup.validate_bundle(tmp_path)


def test_missing_manifest_refused(bundle):
    (bundle/'manifest.json').unlink()
    with pytest.raises(db_backup.BackupError,match='缺失'):
        db_backup.validate_bundle(bundle)


def test_busy_port_does_not_start_or_stop_other_services(bundle,monkeypatch):
    socket = MagicMock()
    socket.__enter__.return_value.bind.side_effect=OSError('occupied')
    monkeypatch.setattr(db_backup.socket,'socket',MagicMock(return_value=socket))
    tool=MagicMock()
    monkeypatch.setattr(db_backup,'run_tool',tool)
    with pytest.raises(db_backup.BackupError,match='6179'):
        db_backup.rehearse(bundle,Path('.'))
    tool.assert_not_called()


def test_subprocess_does_not_inherit_foreign_pg_connections(monkeypatch):
    for key in ('PGHOSTADDR','PGSERVICE','PGPASSFILE','SELFLORE_MIGRATOR_PASSWORD'):
        monkeypatch.setenv(key,'should-not-leak')
    environment=db_backup.environment('temporary-test-password')
    assert not any(key in environment for key in ('PGHOSTADDR','PGSERVICE','PGPASSFILE','SELFLORE_MIGRATOR_PASSWORD'))
    assert environment['PGPASSWORD']=='temporary-test-password'


def test_backup_without_credential_does_not_connect(monkeypatch):
    monkeypatch.delenv('SELFLORE_MIGRATOR_PASSWORD',raising=False)
    connect=MagicMock()
    monkeypatch.setattr(db_backup.psycopg,'connect',connect)
    with pytest.raises(db_backup.BackupError,match='缺少'):
        db_backup.backup(Path('.'))
    connect.assert_not_called()


def test_failed_source_identity_never_runs_dump(tmp_path,monkeypatch):
    monkeypatch.setenv('SELFLORE_MIGRATOR_PASSWORD','test-only')
    monkeypatch.setattr(db_backup,'BACKUPS',tmp_path)
    monkeypatch.setattr(db_backup,'protect_directory',lambda _:None)
    connection=MagicMock()
    connection.__enter__.return_value.execute.return_value.fetchone.return_value=('selflore_prod','wrong',6171,180004)
    monkeypatch.setattr(db_backup.psycopg,'connect',MagicMock(return_value=connection))
    tool=MagicMock();monkeypatch.setattr(db_backup,'run_tool',tool)
    with pytest.raises(db_backup.BackupError,match='源库身份'):
        db_backup.backup(Path('.'))
    tool.assert_not_called()
    assert not list(tmp_path.rglob('manifest.json'))


def test_failure_after_private_start_still_stops_only_owned_cluster(bundle,tmp_path,monkeypatch):
    monkeypatch.setattr(db_backup,'REHEARSALS',tmp_path/'private-rehearsals')
    monkeypatch.setattr(db_backup,'check_restore_port',lambda:None)
    monkeypatch.setattr(db_backup,'protect_directory',lambda p:p.mkdir(parents=True,exist_ok=True))
    tool=MagicMock(side_effect=lambda bin_dir,name,args,password,log: log.write_text('legacy table listing') if name=='pg_restore' else None);monkeypatch.setattr(db_backup,'run_tool',tool)
    import psycopg
    monkeypatch.setattr(db_backup.psycopg,'connect',MagicMock(side_effect=psycopg.OperationalError('synthetic connection failure')))
    with pytest.raises(psycopg.OperationalError):
        db_backup.rehearse(bundle,Path('.'))
    operations=[call.args[1:3] for call in tool.call_args_list]
    assert [operation[0] for operation in operations]==['pg_restore','initdb','pg_ctl','pg_ctl']
    assert operations[-1][1][0]=='stop'
    assert not list((tmp_path/'private-rehearsals').rglob('initdb-password'))
    assert not list((tmp_path/'private-rehearsals').rglob('verification.json'))


def test_only_exact_associative_username_check_is_normalized():
    lower='(char_length((username)::text) >= 3)'; upper='(char_length((username)::text) <= 32)'
    pattern='(((username)::text COLLATE "C") !~ \'[^a-z0-9_一-鿿-]\'::text)'
    nested=f'CHECK ((({lower} AND {upper}) AND {pattern}))'; flat=f'CHECK (({lower} AND {upper} AND {pattern}))'
    def signature(expression): return {'tables':{},'structure':{'constraints':[['app','users','users_username_check',expression]]}}
    assert db_backup.comparable_signature(signature(nested))==db_backup.comparable_signature(signature(flat))
    assert db_backup.comparable_signature(signature(nested))!=db_backup.comparable_signature(signature(flat.replace('<= 32','<= 33')))
    assert db_backup.comparable_signature(signature(nested))!=db_backup.comparable_signature(signature(flat.replace('AND','OR',1)))
    assert signature(nested)['structure']['constraints'][0][3]==nested
