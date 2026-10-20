"""Correct the read-only diagnostic backend selection; v1 failure is retained."""
import sys
import diagnose_impacts_v1 as job

sys.path.insert(0,str(job.ROOT/'stage79_staging'))
import inertial_contact_within_pose_reuse_v1 as contact

job.backend=contact
FAILED_DESIGN=job.DESIGN
FAILED_OUT=job.OUT
job.DESIGN=job.DESIGN.with_name('design_02.json')
job.OUT=job.OUT.with_name('diagnosis_02')


def prepare():
    original=job.api.write
    def with_failure_lineage(path,value,*args,**kwargs):
        if path==job.DESIGN:
            value['diagnostic_backend']='Stage79 cold-within-pose contact backend, with the inherited compiled PGS/SOR and failure-only Stage119 repair scopes. Every sampled q must reproduce the archived application q within 1e-8 U.'
            value['retained_dispatch_failure']=str(FAILED_OUT/'failure.json')
            for p in [FAILED_DESIGN,*FAILED_OUT.iterdir()]:
                if p.is_file(): value['inputs'][str(p)]=job.api.sha(p)
            value['binding']=job.api.digest({k:v for k,v in value.items() if k!='binding'})
        return original(path,value,*args,**kwargs)
    job.api.write=with_failure_lineage
    try: job.prepare()
    finally: job.api.write=original


if __name__=='__main__':
    if sys.argv[1:]==['prepare']: prepare()
    elif sys.argv[1:]==['run']: job.run()
    else: raise ValueError('Use prepare or run')
