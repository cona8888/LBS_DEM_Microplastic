"""Explicit filename correction; benchmark v1 and preparation failure preserved."""
from pathlib import Path
import benchmark_lossless_xz_v1 as prior

def run():
    protocol=prior.ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/storage_benchmark_02.json'
    work=prior.api.read(prior.WORK)
    source=prior.BASE/'diagnostic_replay_01/diagnostic.json.xz'
    paths=[prior.WORK,Path(__file__),Path(prior.__file__),source,source.with_suffix('.seal.json')]
    work.update(stage='Stage196 zero-step XZ benchmark path correction',sources_and_inputs={str(p):prior.api.sha(p) for p in paths},new_trajectory_steps=0)
    prior.job.commit(protocol,work)
    prior.WORK=protocol;prior.SOURCES[2]=source
    prior.RUN=prior.RUN.with_name('lossless_xz_02');prior.OUT=prior.OUT.with_name('lossless_xz_02')
    prior.run()
    prior.api.verify_mapping(work['sources_and_inputs'])

if __name__=='__main__':run()
