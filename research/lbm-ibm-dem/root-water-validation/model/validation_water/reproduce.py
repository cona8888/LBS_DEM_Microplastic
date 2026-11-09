"""Run the full bounded validation campaign sequentially, preserving logs.
The default experimental coefficients are never re-fitted. Run from repo root.
"""
import os,subprocess,sys
from pathlib import Path
from .validate import ROOT,OUT,check_frozen

def main():
    check_frozen();OUT.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    commands=[['make','test'],['make','core-test'],
      [sys.executable,'-m','validation_water.validate','holdouts'],
      [sys.executable,'-m','validation_water.validate','field'],
      [sys.executable,'-m','validation_water.validate','hydraulics'],
      [sys.executable,'-m','validation_water.validate','pair','--scale','1'],
      [sys.executable,'-m','validation_water.validate','pair','--scale','2'],
      [sys.executable,'-m','validation_water.validate','pair','--scale','2','--steps','36','--nopen','18'],
      [sys.executable,'-m','validation_water.relax'],
      [sys.executable,'-m','validation_water.width_check'],
      [sys.executable,'-m','validation_water.summarize'],
      [sys.executable,'-m','validation_water.plot']]
    for i,cmd in enumerate(commands):
        print('RUN:',*cmd,flush=True)
        with (OUT/f'reproduce_{i:02d}.log').open('w') as f:
            subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    check_frozen()
    print('Completed. Inspect gates.csv: failed physical gates remain failed, not relabeled.')
if __name__=='__main__':main()
