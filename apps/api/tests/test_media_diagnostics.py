from collections import namedtuple
from datetime import datetime,timedelta,timezone
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from app import media_diagnostics as diag,media_telemetry as telemetry
from app.media_storage import file_hash,MediaError
from app.media_backup import pack_media,validate_media,restore_media
from test_media_storage import configured,image_bytes

NOW=datetime(2026,10,12,tzinfo=timezone.utc)


def row(config):
    path=config.root/'original.bin'; path.write_bytes(image_bytes())
    preview=config.root/'thumb.webp'; preview.write_bytes(b'thumbnail')
    return {'id':'sample','status':'ready','reference_count':1,'original_key':'original.bin','thumbnail_key':'thumb.webp',
            'original_bytes':path.stat().st_size,'thumbnail_bytes':preview.stat().st_size,
            'original_sha256':file_hash(path),'thumbnail_sha256':file_hash(preview),
            'created_at':NOW.isoformat(),'updated_at':NOW.isoformat()}


def test_integrity_severity_and_readonly(tmp_path,monkeypatch):
    config=configured(tmp_path); entry=row(config)
    disk=namedtuple('Disk','total used free')
    monkeypatch.setattr(diag.shutil,'disk_usage',lambda _:disk(100*1024**3,85*1024**3,15*1024**3))
    (config.root/'original.bin').unlink()
    report=diag.inspect(config,[entry],now=NOW)
    assert report['exit_code']==2
    assert {'missing_original','disk_usage','growth_unknown'}<={i['code'] for i in report['issues']}
    assert report['growth']['runway_days'] is None
    assert sorted(p.name for p in config.root.iterdir())==['.selflore-media.json','thumb.webp']
    assert sorted(p.name for p in config.ops_root.iterdir())==['.selflore-media.json']
    (config.root/'original.bin').write_bytes(b'x'*entry['original_bytes'])
    assert any(i['code']=='corrupt_original' for i in diag.inspect(config,[entry],now=NOW,deep=True)['issues'])
    entry['reference_count']=0
    assert any(i['code']=='unreferenced_ready' for i in diag.inspect(config,[entry],now=NOW)['issues'])


def test_growth_uses_observations_not_uploaded_amount():
    samples=[{'time':(NOW-timedelta(days=10)).isoformat(),'media_bytes':100}]
    result=diag.growth(samples,NOW,200,1000,100)
    assert result['daily_net_bytes']==10 and result['runway_days']==90
    assert diag.growth(samples,NOW,100,1000,100)['runway_days'] is None
    assert diag.growth([{'time':(NOW-timedelta(days=6)).isoformat(),'media_bytes':100}],NOW,200,1000,100)['daily_net_bytes'] is None


def test_request_thresholds_and_coverage(tmp_path):
    config=configured(tmp_path)
    events=[{'category':'start','time':(NOW-timedelta(hours=25)).isoformat()}]
    events += [{'category':'thumbnail','time':(NOW-timedelta(minutes=1)).isoformat(),'status':200,'result':'complete','elapsed_ms':1500,'bytes':1000} for _ in range(100)]
    metrics=diag.request_metrics(events,NOW)
    assert metrics['categories']['thumbnail']['p95_ms']==1500
    assert metrics['bandwidth_utilization'] is None
    report=diag.inspect(config,[],now=NOW,events=events)
    assert any(i['code']=='thumbnail_latency' for i in report['issues'])
    assert diag.request_metrics(events[1:],NOW)['categories']['thumbnail']['p95_ms'] is None
    assert diag.request_metrics(events[:2],NOW)['categories']['thumbnail']['p95_ms'] is None
    for minutes in (4,9,14):
        events.append({'category':'original','time':(NOW-timedelta(minutes=minutes)).isoformat(),'status':200,'result':'complete','elapsed_ms':1,'bytes':100_000_000})
    assert all(v>0.5 for v in diag.request_metrics(events,NOW,1)['bandwidth_utilization'])


def test_backup_age_and_restore_duration(tmp_path):
    config=configured(tmp_path); backups=tmp_path/'backups'; restores=tmp_path/'restores'
    backups.mkdir(); restores.mkdir(); (backups/'one').mkdir(); (restores/'one').mkdir()
    (backups/'one'/'manifest.json').write_text(json.dumps({'source':{'database':'selflore_dev'},'format':'selflore-backup-v2','snapshot_consistent':True,'media':[],'created_at':(NOW-timedelta(hours=25)).isoformat()}))
    (restores/'one'/'verification.json').write_text(json.dumps({'source':{'database':'selflore_dev'},'status':'passed','media_verified':True,'restore_completed_at':NOW.isoformat(),'duration_seconds':7201}))
    report=diag.inspect(config,[],now=NOW,backups=backups,rehearsals=restores)
    assert {'backup_stale','restore_slow'}<={i['code'] for i in report['issues']}


def test_bounded_telemetry_lock_and_no_private_fields(tmp_path,monkeypatch):
    config=configured(tmp_path); (config.ops_root/'telemetry.lock').write_bytes(b'0')
    monkeypatch.setattr(telemetry,'MAX_LOG_BYTES',150)
    def write(_): telemetry.append_event(config,{'time':NOW.isoformat(),'category':'thumbnail','status':200,'bytes':12,'elapsed_ms':5,'result':'complete'})
    with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(write,range(20)))
    paths=list(config.ops_root.glob('media-requests*.jsonl'))
    assert len(paths)<=6
    events=telemetry.read_events(config)
    assert events and all(e['bytes']==12 for e in events)
    assert all(not ({'user_id','cookie','url','body'} & set(e)) for e in events)


def test_partial_scan_and_pack_restore_path_guards(tmp_path):
    config=configured(tmp_path); entry=row(config)
    report=diag.inspect(config,[entry],now=NOW,max_files=1)
    assert not report['scope']['scan_complete'] and any(i['code']=='scan_partial' for i in report['issues'])
    bundle=tmp_path/'bundle'; bundle.mkdir(); pack_media(config,[entry],bundle)
    target=tmp_path/'restore'; restore_media(bundle,[entry],target); validate_media(target,[entry])
    with pytest.raises(MediaError): restore_media(bundle,[entry],target)
    with pytest.raises(MediaError): validate_media(target,[entry,{**entry,'id':'other'}])
    with pytest.raises(MediaError): validate_media(target,[{**entry,'original_key':'../secret'}])
    (bundle/'media'/'original.bin').unlink()
    with pytest.raises(MediaError): validate_media(bundle/'media',[entry])
