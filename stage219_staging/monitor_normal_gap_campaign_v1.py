"""Read-only original seal monitor plus exact creation identities and full seals."""
from pathlib import Path
import hashlib,json,lzma,os,sys,psutil
import normal_gap_campaign_v1 as s
api,job=s.api,s.job
SOURCE=s.ROOT/'stage200_staging/monitor_revised_campaign_v1.py'
TEMPLATE_SHA='bfa4b45d6d15e6e65c0fa7e108a7f42384b685b209b0237624ae93a1c008ac2a'
CERT=job.OUT/'launch_identity_01/results.json'

def reused(process,role,argv):
    expected=Path(argv[0]).name if argv[0].lower().endswith('.exe') else Path(sys.executable).name
    name=process.name()
    if name.lower()==expected.lower():return None
    api.require(role in {c['id'] for c in api.read(job.DESIGN)['cases']} and 'python' not in name.lower(),'only different non-Python executable for sealed old producer')
    folder=job.RUN/role;seal=api.read(folder/'completion.json');r=api.read(folder/'result.json')
    api.require(seal['design_sha256']==r['design_sha256']==api.sha(job.DESIGN) and seal['result_sha256']==api.sha(folder/'result.json'),'sealed original producer completion bound')
    return dict(role=role,pid=process.pid,alive=False,original_worker_retired=True,pid_reused_by_different_executable=True,current_name=name,old_completion_sha256=api.sha(folder/'completion.json'))

def run(expected):
    api.require(api.sha(job.DESIGN)==expected and api.sha(SOURCE)==TEMPLATE_SHA,'exact production design and original monitor template')
    d=api.read(job.DESIGN);api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    text=SOURCE.read_text()
    mapping={'stage200_runs/revised_deadline_campaign_20260927/run_01':'stage219_runs/normal_gap_campaign_20261001/run_01',
        'stage200_designs/revised_deadline_campaign_20260927/design_01.json':'stage219_designs/normal_gap_campaign_20261001/design_01.json',
        '8a973a1eee156023d00994f1476b06d69269300607b1cb2028af5bb3bfb9d923':expected,'Stage200':'Stage219'}
    for a,b in mapping.items():
        if a!='Stage200':api.require(text.count(a)==1,'one exact template target association')
        text=text.replace(a,b)
    before='p=psutil.Process(pid);cmd=p.cmdline();expected=[str(v).lower() for v in argv]'
    api.require(text.count(before)==1,'exact template executable identity site')
    text=text.replace(before,"p=psutil.Process(pid)\n            replacement=reused(p,role,argv)\n            if replacement is not None:\n                processes.append(replacement);continue\n            cmd=p.cmdline();expected=[str(v).lower() for v in argv]")
    ns=dict(__name__='_stage219_readonly_template',__file__=__file__,reused=reused)
    exec(compile(text,__file__+'::original_read_only_seal_checks','exec'),ns);r=ns['run']()
    cert=s.sealed(CERT);api.require(cert['passed'] and cert['design_sha256']==expected,'sealed supervisor birth certificate')
    launch=api.read(job.RUN/'launch.json');bound={'supervisor':cert['supervisor']}
    api.require(bound['supervisor']['launch_sha256']==api.sha(job.RUN/'launch.json'),'original supervisor launch seal')
    for path in [job.RUN/'auditor_launch.json',*sorted(job.RUN.glob('dispatch_*.json'))]:
        a=api.read(path);role=a.get('case','auditor');aff=api.read(job.RUN/(role+'.affinity.json'))
        api.require(a['design_sha256']==aff['design_sha256']==expected and a['pid']==aff['pid'],'immutable dispatch/worker identity')
        bound[role]=dict(pid=a['pid'],argv=a['argv'],created=aff['created'],affinity=aff['current_affinity'])
    for item in r['processes']:
        if not item.get('alive'):continue
        try:
            p=psutil.Process(item['pid']);b=bound[item['role']]
            exact=item['pid']==b['pid'] and p.cmdline()==b['argv'] and abs(p.create_time()-b['created'])<.001
            if item['role']!='supervisor':exact=exact and p.cpu_affinity()==b['affinity'] and p.ppid()==launch['supervisor_pid']
            item.update(created=p.create_time(),bound_active_identity=exact)
            api.require(exact,'exact active command/birth/parent/affinity binding')
        except psutil.NoSuchProcess:item['alive']=False
    seals=0;failed=[]
    for c in d['cases']:
        prior_receipt=None
        for ready in sorted((job.RUN/c['id']).glob('segment_*.ready.json')):
            m=api.read(ready);index=m['segment'];paths=job.paths(job.RUN,c['id'],index);seal=api.read(paths['raw'].with_suffix('.seal.json'))
            packed=paths['raw'].read_bytes();raw=lzma.decompress(packed)
            api.require(hashlib.sha256(packed).hexdigest()==m['raw_sha256']==seal['compressed_sha256']
                and hashlib.sha256(raw).hexdigest()==seal['uncompressed_sha256'] and len(raw)==seal['uncompressed_bytes']
                and api.sha(paths['raw'].with_suffix('.seal.json'))==m['seal_sha256'] and m['design_sha256']==expected,'all committed raw compressed/uncompressed/ready seals')
            seals+=1
            if paths['receipt'].exists():
                a=api.read(paths['receipt'])
                if a.get('status')!='independently_verified':failed.append(dict(case=c['id'],segment=index,status=a.get('status'),error=a.get('error')))
                else:
                    job.policy.verify_receipt(paths,c['id'],index,expected,d['audit_source_sha256'],m['input_checkpoint_sha256'],prior_receipt)
                    api.require(a['summary']['passed'] and a['summary']['steps']==m['steps'],'exact saved versus independent passing step declaration')
                    prior_receipt=api.sha(paths['receipt'])
    r.update(frozen_inputs_verified=True,all_committed_raw_full_seals_verified=seals,failed_receipts=failed,launch_identity_sha256=api.sha(CERT),monitor_source_sha256=api.sha(__file__),template_sha256=TEMPLATE_SHA,new_trajectory_steps=0)
    r['failure_markers']+=failed
    r['terminal_evaluators']=[]
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:
            cmd=p.cmdline()
            if cmd[-3:]==[str(job.SELF),'evaluate','campaign'] or str(Path(__file__).with_name('run_terminal_evaluator_v1.py')) in cmd:r['terminal_evaluators'].append(dict(pid=p.pid,argv=cmd,created=p.create_time()))
        except psutil.NoSuchProcess:continue
    return r

if __name__=='__main__':print(json.dumps(run(sys.argv[1]),indent=2))
