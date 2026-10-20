"""Same frozen unit criteria for the bounded four-interval certificate."""
import sys
import qualify_certified_sweep_v1 as job
import certified_sweep_v2 as revised
job.candidate=revised
job.DESIGN=job.DESIGN.with_name('design_02.json')
job.OUT=job.OUT.with_name('units_02')

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:job.prepare()
    elif sys.argv[1:]==['run']:job.run()
    else:raise ValueError('prepare | run')
