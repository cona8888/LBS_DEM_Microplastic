"""Run only a bounded CPD6 throughput/transition pilot; never export a flow field."""
import gc
import os
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import spatial_cost_v1 as job


def other_processes():
    # Read-only guard, no termination. The current Python process is excluded.
    command = ('Get-Process python*,yade*,*lbm* -ErrorAction SilentlyContinue | '
               f'Where-Object {{ $_.Id -ne {os.getpid()} }} | '
               'Select-Object Id,ProcessName | ConvertTo-Json -Compress')
    out = subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,
                         timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    # Get-Process returns code 1 for unmatched wildcard names; accept only empty stderr.
    job.require(not out.stderr.strip(), 'process inventory inaccessible')
    return out.stdout.strip()


def main():
    d = job.read(job.DESIGN); job.verify(d)
    pre = job.read(job.PREFLIGHT); predone = job.read(job.PREFLIGHT.with_name('completion.json'))
    job.require(pre['passed'] and pre['pilot_authorized'] and pre['design']['sha256']==job.sha(job.DESIGN)
                and predone['results_sha256']==job.sha(job.PREFLIGHT), 'preflight missing/drift')
    job.require(not job.RUN.exists(), 'immutable output exists')
    processes = other_processes()
    job.require(not processes, 'other possible simulation process present: '+processes)
    before = job.gpu_snapshot(); ram = job.available_ram(); controls=d['pilot']
    job.require(before['free_bytes']>=d['cost_model']['device_bytes']+controls['gpu_reserve_bytes'], 'insufficient free GPU memory')
    job.require(before['temperature_C']<=controls['maximum_start_temperature_C'], 'GPU too hot')
    job.require(ram['available_bytes']>=controls['minimum_available_ram_bytes'], 'insufficient host RAM')
    job.RUN.mkdir(parents=True)
    job.write(job.RUN/'manifest.json',{'design':job.bind(job.DESIGN),'preflight':job.bind(job.PREFLIGHT),
        'pid':os.getpid(),'command':sys.argv,'python':sys.version,'platform':platform.platform(),
        'gpu_before':before,'ram_before':ram,'other_simulation_processes':processes,
        'source_geometry':d['bindings']['geometry_cpd6'],'purpose':'nonsteady cost pilot, no field export'})
    driver=session=None
    start=time.perf_counter()
    try:
        with np.load(d['geometry']['path']) as g: phase=g['phase']
        initial=np.zeros((19,*phase.shape),dtype=np.float32)
        initial_hash=job.digest_array(initial)
        legacy=job.prior.audit.legacy
        legacy.install_generic_mask_oracle()
        adapter={'lineage':{'cuda_source':d['bindings']['cuda_source']['path'],
                            'qualified_ptx_sha256':d['qualified_ptx_sha256']}}
        driver,build=legacy.create_driver(adapter,job.Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin'),0)
        case=job.prior.probe.case_for(phase,controls['acceleration_lu'],'stage125_cpd6_cost_only')
        session=legacy.stage13.CudaCandidateSession(driver,initial,phase,case,tau=.8,threads=256,maximum_steps=417)
        allocation=session.device_allocation_bytes
        job.require(allocation==d['cost_model']['device_bytes'],'allocation mismatch')
        del initial;gc.collect()
        step=0;blocks=[]
        for block_id,count in enumerate([32,128,128,128]):
            begin=time.perf_counter();kernel_before=session.kernel_wall_time_seconds
            for _ in range(count):
                step+=1;session.step(step)
                if step%32==0:
                    driver.synchronize();session._collect_timing()
                    job.require(time.perf_counter()-start<controls['wall_budget_s'],'cooperative pilot budget exhausted')
                    job.require(session.health_code()==0,'GPU numerical health nonzero')
            driver.synchronize();session._collect_timing()
            snapshot=job.gpu_snapshot()
            job.require(snapshot['temperature_C']<=controls['maximum_run_temperature_C'],'GPU temperature gate')
            row={'block':block_id,'role':'warmup' if block_id==0 else 'timed','steps':count,
                 'end_step':step,'wall_s':time.perf_counter()-begin,
                 'kernel_s':session.kernel_wall_time_seconds-kernel_before,'gpu':snapshot,
                 'health_code':session.health_code()}
            blocks.append(row);job.write(job.RUN/f'block_{block_id:02d}.json',row)
            print('BLOCK',block_id,'steps',step,'kernel_s',row['kernel_s'],flush=True)
        state=session.copy_current();state_hash=job.digest_array(state)
        fluid=np.flatnonzero(phase.ravel()==0)
        selected=fluid[np.linspace(0,len(fluid)-1,controls['cpu_transition_nodes'],dtype=int)]
        nodes=np.array(np.unravel_index(selected,phase.shape)).T
        pulled=np.empty((len(nodes),19),dtype=np.float32)
        directions=legacy.stage13.DIRECTIONS_I64; opposite=legacy.stage13.OPPOSITE
        for i,node in enumerate(nodes):
            for q,c in enumerate(directions):
                src=tuple((node-c[::-1])%np.array(phase.shape))
                pulled[i,q]=state[int(opposite[q])][tuple(node)] if phase[src]!=0 else state[q][src]
        state_finite=bool(np.isfinite(state).all())
        solid_zero=all(not np.any(state[q][phase!=0]) for q in range(19))
        del state;gc.collect()
        session.step(417);final=session.copy_current()
        after=np.array([final[(slice(None),)+tuple(node)] for node in nodes])
        final_hash=job.digest_array(final)
        final_finite=bool(np.isfinite(final).all())
        final_solid_zero=all(not np.any(final[q][phase!=0]) for q in range(19))
        health=session.health_code();kernel_total=session.kernel_wall_time_seconds
        session.close();session=None;driver.close();driver=None
        del final;gc.collect()
        np.savez_compressed(job.RUN/'transition_samples.npz',nodes_zyx=nodes,precollision=pulled,next_stored=after)
        job.verify(d)
        result={'status':'cost_pilot_complete_pending_evaluation','design_sha256':job.sha(job.DESIGN),
            'manifest_sha256':job.sha(job.RUN/'manifest.json'),'steps_completed':417,
            'initial_state_array_sha256':initial_hash,'state416_array_sha256':state_hash,
            'state417_array_sha256':final_hash,'health_code':health,'finite_states':state_finite and final_finite,
            'solid_populations_zero':solid_zero and final_solid_zero,'device_allocation_bytes':allocation,
            'blocks':blocks,'kernel_total_s':kernel_total,'wall_total_s':time.perf_counter()-start,
            'build':build,'transition_samples':job.bind(job.RUN/'transition_samples.npz'),
            'gpu_after':job.gpu_snapshot(),'steady_state':False,'mean_matched':False,
            'flow_field_exported':False,'transport_authorized':False}
        job.write(job.RUN/'result.json',result)
        job.write(job.RUN/'completion.json',{'status':result['status'],'results_sha256':job.sha(job.RUN/'result.json'),
            'artifacts':{str(p):job.sha(p) for p in job.RUN.iterdir() if p.is_file()}})
        print('PILOT COMPLETE wall_s',result['wall_total_s'],flush=True)
    except Exception as exc:
        job.write(job.RUN/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
    finally:
        if session is not None: session.close()
        if driver is not None: driver.close()


if __name__=='__main__': main()
