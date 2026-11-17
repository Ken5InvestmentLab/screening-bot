"""Read-only proof for the existing once-only same-JST-day detection retry.

Only a native crash before source validation may reuse unfinished acquisition
packets. No state/locks/receipts are repaired here, and no provider fallback,
database write, publication or notification is performed.
"""
from __future__ import annotations
import hashlib,json,re,sqlite3,sys
from contextlib import closing
from pathlib import Path

NATIVE_EXIT=0xC0000005
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def check(ok,message):
    if not ok:raise ValueError('Native acquisition recovery: '+message)
def inside(root,path):
    root=Path(root).resolve();path=Path(path).resolve()
    check(path!=root and path.is_relative_to(root),'artifact escapes its original private directory')
    return path

def inspect(repo,runtime,prior,date,source_sha,*,active_run=None):
    """Return None for non-native failures; reject incomplete native evidence."""
    repo=Path(repo).resolve();runtime=inside(repo,runtime)
    check(prior.get('identity')=='WEAK_EARLY_CLOUD_DAILY_V1' and prior.get('date')==date
          and prior.get('ok') is False and prior.get('completedAt') and prior.get('stage')=='detection',
          'terminal same-day detection receipt required')
    current=read(runtime/'daily-latest.json')
    if active_run is None:
        check(current==prior,'latest terminal receipt changed')
    else:
        # The normal runner has already claimed this recovery and published its
        # own progress. Bind that precise live invocation instead of pretending
        # daily-latest still points at the preserved terminal source failure.
        started,pid=active_run
        check(current.get('identity')=='WEAK_EARLY_CLOUD_DAILY_V1'
              and current.get('startedAt')==started and current.get('pid')==pid
              and current.get('date')==date and current.get('ok') is False
              and not current.get('completedAt') and current.get('stage')=='detection'
              and current.get('originalRunId')==(prior.get('originalRunId') or prior['startedAt']),
              'active recovery invocation differs or is terminal')
        check((runtime/'daily.lock').read_text(encoding='utf8')==started,'active recovery does not own daily lock')
        active_folder=inside(runtime,runtime/('daily-'+started.replace(':','-').replace('.','-')))
        check(read(active_folder/'result.json')==current,'active progress differs from latest')
        active_invoked=read(active_folder/'invoked.json')
        check(active_invoked.get('identity')=='CLOUD_RUNNER_INVOKED_V1'
              and all(active_invoked.get(k)==current.get(k) for k in ['startedAt','pid','date','originalRunId']),
              'active invocation identity differs')
        key=re.sub(r'[^0-9TZ-]','',prior.get('originalRunId') or prior['startedAt'])
        claim=read(runtime/f'recovery-{key}.json')
        check(claim.get('priorStartedAt')==prior['startedAt'] and isinstance(claim.get('invocation'),str)
              and claim['invocation'],'immutable recovery reservation missing or different')
        check(read(runtime/f'recovery-input-{key}.json')==prior,'immutable recovery input differs')
        check(not list(active_folder.glob('detect-*.process.json')),'active detection may already have executed')
        for name in ['deployment','notifications','notificationPreview','latestSession','selectorRows','generatedCommit']:
            check(name not in current,'active downstream outcome exists or is uncertain')
    return inspect_source_evidence(repo,runtime,prior,date,source_sha)

def inspect_source_evidence(repo,runtime,prior,date,source_sha):
    """Read preserved source artifacts only; does not authorize a new run."""
    repo=Path(repo).resolve();runtime=inside(repo,runtime)
    check(prior.get('identity')=='WEAK_EARLY_CLOUD_DAILY_V1' and prior.get('date')==date
          and prior.get('ok') is False and prior.get('completedAt') and prior.get('stage')=='detection',
          'terminal original source receipt required')
    folder=inside(runtime,runtime/('daily-'+prior['startedAt'].replace(':','-').replace('.','-')))
    check(read(folder/'result.json')==prior,'preserved original terminal receipt differs')
    invoked=read(folder/'invoked.json')
    check(invoked.get('identity')=='CLOUD_RUNNER_INVOKED_V1' and invoked.get('date')==date
          and invoked.get('startedAt')==prior['startedAt'] and invoked.get('pid')==prior.get('pid'),
          'original invocation identity differs')
    children=sorted(folder.glob('detect-*.process.json'))
    if not children:return None
    child_file=children[-1];child=read(child_file)
    if child.get('code') not in [NATIVE_EXIT,NATIVE_EXIT-2**32]:return None
    check(child.get('identity')=='CLOUD_CHILD_PROCESS_V1' and child.get('status')=='exited'
          and child.get('completedAt') and isinstance(child.get('pid'),int),'native child is not terminal')
    check(prior.get('new_a',{}).get('entry')=='new-a-verified-daily-v1','not the approved New A entry')
    for key in ['deployment','notifications','notificationPreview','latestSession','selectorRows','generatedCommit']:
        check(key not in prior,'downstream outcome exists or is uncertain')
    check(not prior.get('fundamentals'),'downstream work exists')
    stem=child_file.name.removesuffix('.process.json')
    check(re.fullmatch(r'detect-[1-3]',stem) is not None,'unexpected detection attempt')
    check((folder/(stem+'.stdout')).stat().st_size==0,'detection output needs separate reconciliation')
    phases=[]
    for line in (folder/(stem+'.stderr')).read_text(encoding='utf-8',errors='replace').splitlines():
        try:item=json.loads(line)
        except ValueError:continue
        if isinstance(item,dict) and item.get('identity')=='CLOUD_DAILY_PHASE_V1':phases.append(item)
    check(phases and phases[-1].get('stage')=='corporate-action-normalization'
          and phases[-1].get('event')=='started','source-only native failure is unproven')
    check(not any(p.get('stage') in ['source-cache-write','cache-read-and-validation','source-quality'] for p in phases),
          'cache or pipeline may already have advanced')
    entries=prior.get('acquisitionEvidence',[]);attempt=int(stem.split('-')[1])
    selected=[e for e in entries if e.get('attempt')==attempt and e.get('directory')]
    check(len(selected)==1,'original acquisition directory is ambiguous')
    archive=inside(folder,selected[0]['directory']);check(archive==folder/f'acquisition-{attempt}','unexpected archive location')
    manifest_path=inside(archive,archive/'manifest.json');manifest=read(manifest_path)
    context=manifest.get('context',{})
    check(manifest.get('identity')=='CLOUD_ACQUISITION_V1' and manifest.get('status')=='acquiring'
          and context.get('date')==date and context.get('previousSourceSha256')==source_sha,
          'acquisition date/status/previous source changed')
    check(isinstance(context.get('tickers'),list) and context['tickers'] and len(context['tickers'])==len(set(context['tickers']))
          and isinstance(context.get('period'),str),'universe/period missing')
    source=repo/'.cache/weak_early_beta/tse_daily.csv';quality=read(source.with_suffix('.source-quality.json'))
    check(quality.get('identity')=='CLOUD_SOURCE_QUALITY_V1' and quality.get('daily_sha256')==source_sha
          and sha(source)==source_sha,'prior cache/quality changed')
    inventory=[];count=manifest.get('requests')
    check(isinstance(count,int) and 0<count<=1000,'bounded retained request count required')
    for sequence in range(1,count+1):
        receipts=list(archive.glob(f'{sequence:05d}-*.json'));check(len(receipts)==1,'missing or ambiguous receipt')
        receipt=inside(archive,receipts[0]);saved=read(receipt);request=saved.get('request')
        key=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()[:20]
        check(receipt.stem==f'{sequence:05d}-{key}','request identity changed')
        packet_sha=None
        if not saved.get('error'):
            packet=inside(archive,receipt.with_suffix('.pkl'));check(packet.is_file(),'packet is missing');packet_sha=sha(packet)
            check(packet_sha==saved.get('sha256'),'packet hash changed')
        inventory.append({'receipt':receipt.name,'receiptSha256':sha(receipt),'packetSha256':packet_sha})
    private=repo/'.cache/weak_early_beta/new-a-private';db=private/'daily-live.sqlite'
    if db.exists():
        with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as connection:
            check(connection.execute('SELECT COUNT(*) FROM runs WHERE run_key LIKE ?',(date+'|%',)).fetchone()[0]==0,
                  'same-day pipeline run already committed')
            check(connection.execute('SELECT COUNT(*) FROM symbol_days WHERE day>=?',(date,)).fetchone()[0]==0,
                  'pipeline state already advanced to target/later day')
    latest=private/'latest-run.json'
    if latest.exists():
        previous_run=read(latest);session=previous_run.get('latest_session')
        check(previous_run.get('identity')=='NEW_A_CLOUD_DAILY_V1' and previous_run.get('strategy')=='A_BASE'
              and previous_run.get('entry')=='new-a-verified-daily-v1' and isinstance(session,str)
              and re.fullmatch(r'\d{4}-\d{2}-\d{2}',session) and session<date,
              'target/later or unrecognized detection receipt exists')
    outbox=private/'notification-outbox.sqlite'
    if outbox.exists():
        with closing(sqlite3.connect(outbox.as_uri()+'?mode=ro',uri=True)) as connection:
            for (payload,) in connection.execute('SELECT payload_json FROM new_a_delivery'):
                event=json.loads(payload);day=event.get('signal_date')
                check(event.get('strategy')=='A_BASE' and isinstance(day,str)
                      and re.fullmatch(r'\d{4}-\d{2}-\d{2}',day) and day<date,
                      'target/later or unrecognized notification outcome exists')
    # A normal source-stage crash cannot have created target-day bundle/outbox.
    runs=private/'runs'
    if runs.exists():check(not any(date in p.name for p in runs.iterdir()),'target-day artifact exists')
    return {'schema':'CLOUD_NATIVE_SOURCE_REPLAY_V1','date':date,'original_run_id':prior['startedAt'],
            'directory':str(archive),'previous_source_sha256':source_sha,'requests':count,
            'manifest_sha256':sha(manifest_path),'child_receipt_sha256':sha(child_file),
            'stderr_sha256':sha(folder/(stem+'.stderr')),
            'inventory_sha256':hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'network_fallback':False,'inspection_wrote_or_sent':False,'remote_readback_required':True}

def main():
    if len(sys.argv)==7 and sys.argv[1]=='--preserved-source-evidence':
        repo,runtime,prior,date,source=sys.argv[2:]
        print(json.dumps(inspect_source_evidence(repo,runtime,read(prior),date,source),sort_keys=True));return
    if len(sys.argv) not in [6,8]:raise ValueError('expected repo runtime immutable-prior date verified-source-sha [active-start active-pid]')
    repo,runtime,prior,date,source=sys.argv[1:6]
    active=(sys.argv[6],int(sys.argv[7])) if len(sys.argv)==8 else None
    print(json.dumps(inspect(repo,runtime,read(prior),date,source,active_run=active),sort_keys=True))
if __name__=='__main__':main()
