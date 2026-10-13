"""Read-only media diagnosis. Only --record/--output persist operator reports."""
from __future__ import annotations

import argparse
from datetime import datetime,timedelta,timezone
import json
import hashlib
import math
import os
from pathlib import Path
import shutil
import time

import psycopg
from psycopg.rows import dict_row
from app.media_storage import MediaConfig,MediaError,MARKER,safe_path,linked
from app.media_telemetry import read_events


def timestamp(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def bounded_hash(path,deadline):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):
            if time.monotonic()>deadline: raise TimeoutError('深度检查预算用尽')
            digest.update(chunk)
    return digest.hexdigest()


def growth(samples,now,total,free,reserve):
    selected=sorted((s for s in samples if now-timedelta(days=30)<=timestamp(s['time'])<=now),key=lambda s:s['time'])
    result={'daily_net_bytes':None,'runway_days':None,'sample_count':len(selected),'reason':'至少需要7天有效容量观测','reserve_bytes':reserve}
    if selected:
        days=(now-timestamp(selected[0]['time'])).total_seconds()/86400
        if days>=7:
            delta=(total-selected[0]['media_bytes'])/days
            result.update(daily_net_bytes=delta,period_start=selected[0]['time'],period_end=now.isoformat())
            result['reason']='增长为零或负值，无法预测耗尽日期' if delta<=0 else None
            if delta>0: result['runway_days']=max(0,free-reserve)/delta
    return result


def request_metrics(events,now,bandwidth_mbps=None):
    since=now-timedelta(hours=24)
    dates=[timestamp(e['time']) for e in events]
    complete=bool(dates) and min(dates)<=since
    result={'measurement':'server_response_completion','period_start':since.isoformat(),'period_end':now.isoformat(),
            'coverage_start':min(dates).isoformat() if dates else None,'coverage':'complete' if complete else 'partial',
            'categories':{},'bandwidth_utilization':None,'bandwidth_reason':'未提供可用带宽' if not bandwidth_mbps else '观测窗口不完整'}
    selected=[e for e in events if e.get('category') in ('upload','thumbnail','original') and since<=timestamp(e['time'])<=now]
    for category in ('upload','thumbnail','original'):
        rows=[e for e in selected if e['category']==category]
        elapsed=sorted(e['elapsed_ms'] for e in rows if e.get('result')=='complete' and 200<=e['status']<300)
        failures=sum(e['status']>=500 or e.get('result')!='complete' for e in rows)
        enough=len(rows)>=100 and complete
        result['categories'][category]={'count':len(rows),'response_bytes':sum(e['bytes'] for e in rows),
             'failures':failures,'failure_rate':failures/len(rows) if enough else None,
             'p95_ms':elapsed[math.ceil(len(elapsed)*0.95)-1] if len(elapsed)>=100 and complete else None,
             'reason':None if enough else '样本不足100或保留窗口不完整'}
    buckets={}
    for event in selected:
        key=int(timestamp(event['time']).timestamp())//300
        buckets[key]=buckets.get(key,0)+event['bytes']
    result['observed_bytes']=sum(e['bytes'] for e in selected)
    result['throughput_5min_bps']={str(k):v*8/300 for k,v in buckets.items()}
    if bandwidth_mbps and bandwidth_mbps>0 and complete:
        last=int(now.timestamp())//300-1
        rates=[buckets.get(k,0)*8/300/(bandwidth_mbps*1_000_000) for k in range(last-2,last+1)]
        result.update(bandwidth_utilization=rates,bandwidth_reason=None)
    return result


def backup_metrics(backup_root,rehearsal_root,config,now):
    result={'last_joint_backup_at':None,'backup_age_hours':None,'restore_duration_seconds':None,
            'last_restore_at':None,'database_only_backups':0,'reason':None}
    candidates=[]; restores=[]
    for root,name in ((backup_root,'manifest.json'),(rehearsal_root,'verification.json')):
        if root is None: continue
        if not root.is_dir() or linked(root): raise MediaError('指定备份或演练目录不可读或为链接')
        for directory in root.iterdir():
            if not directory.is_dir() or linked(directory): continue
            path=safe_path(root,directory.name+'/'+name)
            if not path.is_file(): continue
            try:
                data=json.loads(path.read_text(encoding='utf-8'))
                if data.get('source',{}).get('database')!=config.database: continue
                if name=='manifest.json':
                    if data.get('format')=='selflore-backup-v1': result['database_only_backups']+=1
                    if data.get('format')=='selflore-backup-v2' and data.get('snapshot_consistent') and isinstance(data.get('media'),list):
                        candidates.append(data)
                elif data.get('status')=='passed' and data.get('media_verified') is True:
                    restores.append(data)
            except (ValueError,KeyError,TypeError): continue
    if candidates:
        latest=max(candidates,key=lambda c:timestamp(c.get('completed_at',c['created_at'])))
        at=latest.get('completed_at',latest['created_at'])
        result.update(last_joint_backup_at=at,backup_age_hours=(now-timestamp(at)).total_seconds()/3600)
    if restores:
        latest=max(restores,key=lambda c:timestamp(c['restore_completed_at']))
        result.update(last_restore_at=latest['restore_completed_at'],restore_duration_seconds=latest['duration_seconds'])
    return result


def inspect(config,rows,*,now=None,deep=False,history=None,events=None,backups=None,rehearsals=None,
            bandwidth_mbps=None,max_files=100000,timeout=30,thresholds=None):
    now=now or datetime.now(timezone.utc); root=config.check(); issues=[]
    thresholds={**{'disk_warn':70,'disk_critical':80,'runway_warn':90,'runway_critical':30,
                   'p95_ms':1000,'failure_rate':0.01,'backup_hours':24,'restore_seconds':7200},**(thresholds or {})}
    def problem(level,code,message,entity=None):
        issues.append({'level':level,'code':code,'message':message,**({'attachment_id':str(entity)} if entity else {})})
    files={}; pending=[root]; complete=True; deadline=time.monotonic()+timeout
    while pending:
        directory=pending.pop()
        for path in directory.iterdir():
            if path.name==MARKER: continue
            if linked(path): raise MediaError('扫描遇到链接或重解析点，未跟随')
            if path.is_dir(): pending.append(path)
            else: files[path.relative_to(root).as_posix()]=path.stat().st_size
            if len(files)>=max_files or time.monotonic()>deadline:
                complete=False; pending=[]; break
    if not complete: problem('unknown','scan_partial','扫描预算用尽，容量及完整性检查仅部分完成')
    expected={r[v+'_key'] for r in rows if r['status']=='ready' for v in ('original','thumbnail')}
    originals=0; thumbnails=0; states={}; orphan_ready=0; original_count=0
    uploaded=sum((r.get('original_bytes') or 0)+(r.get('thumbnail_bytes') or 0) for r in rows if r['status']=='ready' and r.get('created_at') and timestamp(str(r['created_at']))>=now-timedelta(days=30))
    for row in rows:
        if time.monotonic()>deadline:
            complete=False
            problem('unknown','integrity_partial','完整性检查预算用尽，剩余附件未检查')
            break
        states[row['status']]=states.get(row['status'],0)+1
        if row['status']!='ready':
            if timestamp(str(row['updated_at']))<now-timedelta(hours=24): problem('warn','stale_upload','未完成上传超过24小时，请排查或显式重试',row['id'])
            continue
        if not row.get('reference_count'):
            orphan_ready+=1; problem('warn','unreferenced_ready','已完成图片未被引用；保留而非自动删除',row['id'])
        for variant in ('original','thumbnail'):
            key=row[variant+'_key']; expected.add(key); path=safe_path(root,key)
            if not path.is_file():
                problem('critical' if variant=='original' and row.get('reference_count') else 'warn','missing_'+variant,'登记图片文件缺失',row['id']); continue
            size=path.stat().st_size
            if variant=='original': originals+=size; original_count+=1
            else: thumbnails+=size
            try:
                matches=not deep or bounded_hash(path,deadline)==row[variant+'_sha256']
            except TimeoutError:
                complete=False; matches=None
                problem('unknown','integrity_partial','深度校验预算用尽，该文件未完成核验',row['id'])
            if size!=row[variant+'_bytes'] or matches is False:
                problem('critical' if variant=='original' and row.get('reference_count') else 'warn','corrupt_'+variant,'登记图片大小或校验值不符',row['id'])
    unknown_files=set(files)-expected
    if unknown_files: problem('warn','unregistered_files','发现未登记文件（可能为上传暂态）；不自动删除')
    disk=shutil.disk_usage(root); usage=(disk.total-disk.free)/disk.total*100
    reserve=max(disk.total*0.10,5*1024**3)
    if usage>=thresholds['disk_warn']: problem('critical' if usage>=thresholds['disk_critical'] else 'warn','disk_usage','磁盘使用率高，请评估扩容或对象存储')
    if disk.free<=reserve: problem('critical','disk_reserve','可用空间低于预留空间，请尽快扩容')
    total=sum(files.values())
    prediction=growth(history or [],now,total,disk.free,reserve) if complete else {'daily_net_bytes':None,'runway_days':None,'reason':'扫描不完整'}
    if prediction['runway_days'] is None: problem('unknown','growth_unknown',prediction['reason'])
    elif prediction['runway_days']<thresholds['runway_warn']: problem('critical' if prediction['runway_days']<thresholds['runway_critical'] else 'warn','runway','预计可支撑天数较短，请评估扩容或迁移')
    if total>=50*1024**3: problem('info','capacity_review','图片达到50 GiB，建议评估备份与成本；不是强制迁移门槛')
    inode=None
    if hasattr(os,'statvfs'):
        stats=os.statvfs(root)
        if stats.f_files:
            inode={'total':stats.f_files,'available':stats.f_favail,'used_percent':(stats.f_files-stats.f_favail)/stats.f_files*100}
            if inode['used_percent']>=thresholds['disk_warn']: problem('critical' if inode['used_percent']>=thresholds['disk_critical'] else 'warn','inode_usage','inode剩余不足，请检查文件量')
    metrics=request_metrics(events or [],now,bandwidth_mbps)
    for category,value in metrics['categories'].items():
        if value['reason']: problem('unknown','request_samples_'+category,value['reason'])
        if category=='thumbnail' and value['p95_ms'] is not None and value['p95_ms']>thresholds['p95_ms']: problem('warn','thumbnail_latency','服务端缩略图P95偏慢，排查磁盘及带宽')
        if value['failure_rate'] is not None and value['failure_rate']>thresholds['failure_rate']: problem('warn','request_failure_'+category,'服务端请求失败率偏高')
    rates=metrics['bandwidth_utilization']
    if rates is None: problem('unknown','bandwidth_unknown',metrics['bandwidth_reason'])
    elif all(rate>0.5 for rate in rates): problem('warn','bandwidth_pressure','连续三个完整5分钟桶超过配置带宽50%，评估分发方式')
    backup=backup_metrics(backups,rehearsals,config,now)
    if backup['backup_age_hours'] is None: problem('unknown','backup_unknown','没有已完成联合备份记录')
    elif backup['backup_age_hours']>thresholds['backup_hours']: problem('warn','backup_stale','联合备份超过新鲜度目标，请先备份')
    if backup['restore_duration_seconds'] is None: problem('unknown','restore_unknown','没有带图片的成功恢复演练记录')
    elif backup['restore_duration_seconds']>thresholds['restore_seconds']: problem('warn','restore_slow','完整恢复超过目标耗时')
    exit_code=2 if any(i['level']=='critical' for i in issues) else 1 if any(i['level'] in ('warn','unknown') for i in issues) else 0
    return {'schema_version':1,'time':now.isoformat(),'environment':config.environment,'database':config.database,
            'scope':{'deep':deep,'scan_complete':complete,'scanned_files':len(files)},'limits':config.limits(),
            'storage':{'media_bytes':total,'original_bytes':originals,'thumbnail_bytes':thumbnails,'original_count':original_count,
                       'states':states,'unreferenced_ready':orphan_ready,'unregistered_files':len(unknown_files),'uploaded_last_30_days_bytes':uploaded},
            'disk':{'total_bytes':disk.total,'available_bytes':disk.free,'used_percent':usage,'reserve_bytes':reserve,'inode':inode},
            'growth':prediction,'requests':metrics,'backup':backup,'thresholds':thresholds,'issues':issues,'exit_code':exit_code}


def main(argv=None):
    parser=argparse.ArgumentParser(description='SelfLore只读图片存储排查')
    parser.add_argument('--json',action='store_true'); parser.add_argument('--deep',action='store_true')
    parser.add_argument('--details',action='store_true',help='显示附件ID；默认按问题代码聚合数量')
    parser.add_argument('--record',action='store_true'); parser.add_argument('--output',type=str)
    parser.add_argument('--expected-port',type=int,default=6171)
    parser.add_argument('--backup-root',type=Path); parser.add_argument('--rehearsal-root',type=Path)
    parser.add_argument('--bandwidth-mbps',type=float); parser.add_argument('--max-files',type=int,default=100000)
    parser.add_argument('--timeout',type=float,default=30)
    for name,default in [('disk-warn',70),('disk-critical',80),('runway-warn',90),('runway-critical',30),('p95-ms',1000),('failure-rate',0.01),('backup-hours',24),('restore-seconds',7200)]:
        parser.add_argument('--'+name,type=float,default=default)
    args=parser.parse_args(argv)
    stage='configuration'
    try:
        if args.max_files<1 or args.timeout<=0 or (args.bandwidth_mbps is not None and args.bandwidth_mbps<=0): raise MediaError('扫描预算和可用带宽必须为正数')
        config=MediaConfig.load(); config.check(); ops=config.check(ops=True)
        dsn=os.environ.get('SELFLORE_DATABASE_URL','')
        if not dsn: raise MediaError('必须显式提供诊断数据库配置')
        if not 0<args.disk_warn<args.disk_critical<=100 or not 0<args.runway_critical<args.runway_warn or not 0<=args.failure_rate<=1:
            raise MediaError('预警阈值顺序或范围不合法')
        stage='database'
        with psycopg.connect(dsn,connect_timeout=5,row_factory=dict_row) as db:
            db.execute('SET TRANSACTION READ ONLY')
            actual=db.execute('SELECT current_database() AS db,current_user AS role,inet_server_port() AS port').fetchone()
            if actual!={'db':config.database,'role':config.database+'_app','port':args.expected_port}: raise MediaError('诊断数据库身份或端口与显式预期不符')
            rows=db.execute('''SELECT a.*,(SELECT count(*) FROM app.card_attachments ca WHERE ca.owner_id=a.owner_id AND ca.attachment_id=a.id) AS reference_count FROM app.attachments a''').fetchall()
        stage='records'
        sample_path=safe_path(ops,'capacity.jsonl')
        history=[json.loads(line) for line in sample_path.read_text(encoding='utf-8').splitlines()] if sample_path.exists() else []
        try: events=read_events(config)
        except (MediaError,OSError): events=[]
        thresholds={name.replace('-','_'):getattr(args,name.replace('-','_')) for name in ('disk-warn','disk-critical','runway-warn','runway-critical','p95-ms','failure-rate','backup-hours','restore-seconds')}
        stage='scan'
        report=inspect(config,rows,deep=args.deep,history=history,events=events,backups=args.backup_root,rehearsals=args.rehearsal_root,
                       bandwidth_mbps=args.bandwidth_mbps,max_files=args.max_files,timeout=args.timeout,thresholds=thresholds)
        if not args.details:
            grouped={}
            for issue in report['issues']:
                key=(issue['level'],issue['code'],issue['message'])
                if key not in grouped: grouped[key]={k:issue[k] for k in ('level','code','message')} | {'count':0}
                grouped[key]['count']+=1
            report['issues']=list(grouped.values())
        stage='report'
        if args.record and report['scope']['scan_complete']:
            with sample_path.open('a',encoding='utf-8') as stream: stream.write(json.dumps({'time':report['time'],'media_bytes':report['storage']['media_bytes']})+'\n')
        if args.output:
            path=safe_path(ops,args.output)
            if path.exists(): raise MediaError('报告文件已存在，请使用新文件名')
            with path.open('x',encoding='utf-8') as stream: json.dump(report,stream,ensure_ascii=False,indent=2)
        if args.json: print(json.dumps(report,ensure_ascii=False,indent=2))
        else:
            print(f"SelfLore媒体排查 {timestamp(report['time']).astimezone(timezone(timedelta(hours=8))).isoformat()} / {report['environment']}")
            print(f"图片 {report['storage']['media_bytes']} bytes；卷使用 {report['disk']['used_percent']:.1f}%；可支撑天数 {report['growth']['runway_days']}")
            print('请求耗时为服务端测量；未知指标不是0；未执行清理或迁移。')
            for issue in report['issues']: print(f"[{issue['level']}] {issue['code']}: {issue['message']}"+ (f" (数量 {issue['count']})" if 'count' in issue else f" (附件 {issue['attachment_id']})" if 'attachment_id' in issue else ''))
            print(f"退出码 {report['exit_code']}")
        return report['exit_code']
    except (MediaError,psycopg.Error,OSError,ValueError,KeyError,TypeError) as error:
        message=str(error) if isinstance(error,MediaError) else '数据库连接／权限失败' if isinstance(error,psycopg.Error) else '文件访问或权限失败' if isinstance(error,OSError) else '记录格式无效'
        report={'schema_version':1,'exit_code':3,'issues':[{'level':'error','code':'check_incomplete','check':stage,'message':message+'；检查未完成，未输出凭据'}]}
        print(json.dumps(report,ensure_ascii=False) if args.json else report['issues'][0]['message'])
        return 3


if __name__=='__main__': raise SystemExit(main())
