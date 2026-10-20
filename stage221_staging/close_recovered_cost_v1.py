"""Close recorded physical-trajectory cost using sealed successor provenance."""
from pathlib import Path
import copy, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage222_staging'))
import overnight_campaign_v1 as n


def run():
    basepath=ROOT/'stage221_evaluations/cost_review_20261007/snapshot_01/results.json'
    base=n.sealed(basepath);proof=n.sealed(n.PREREQUISITE)
    n.api.require(proof['passed'],'Completed passing reference successor')
    old_prefix=str(n.old.RUN)
    authenticated=0
    for path,digest in base['evidence'].items():
        if path.startswith(old_prefix):
            n.api.require(proof['artifacts'][path]==digest,'Original cost ready/audit hashes authenticated by complete successor')
            authenticated+=1
    n.api.require(authenticated==2*5112,'All original ready/audit cost sources covered')
    recovery=n.inherited.sealed(n.inherited.RUN/'production_01/results.json')
    rows=[];new_evidence={}
    for oldrow in base['cases']:
        row={k:copy.deepcopy(oldrow[k]) for k in ('case','shape','sample_id','timestep_factor','horizon_s','original')}
        total=copy.deepcopy(row['original'])
        if row['case']==n.inherited.NAME:
            extra={k:0 for k in total}
            for entry in recovery['entries']:
                path=n.inherited.RUN/'production_01'/f"segment_{entry['segment']:05d}"/'results.json'
                result=n.inherited.sealed(path);digest=n.api.sha(path)
                n.api.require(digest==entry['results_sha256']==proof['artifacts'][str(path)],'Sealed continuation cost source authenticated by successor')
                summary=result['summary'];n.api.require(result['passed'] and summary['passed'],'Passing physical segment')
                values=dict(steps=result['new_saved_steps'],producer_transaction_seconds=result['transaction_seconds'],
                    physics_audit_seconds=summary['audit_seconds'],certified_sweeps=summary['certified_sweeps'],
                    fallback_force_systems=summary['fallback_force_systems'],segments=1)
                for key,value in values.items():extra[key]+=value
                new_evidence[str(path)]=digest
            n.api.require(extra['steps']==recovery['new_saved_steps']==1998369,'Exact complete recovery step accounting')
            row['recovery']=extra
            for key,value in extra.items():total[key]+=value
        observation=next(c for p in proof['placements'] for c in p['cases'] if c['case_id']==row['case'])
        n.api.require(observation['complete_observation'] and observation['steps']==total['steps'],'Cost covers exact complete physical observation')
        row.update(combined=total,status=observation['status'],stop_s=observation['stop_s'],
                   producer_hours=total['producer_transaction_seconds']/3600,
                   physics_audit_hours=total['physics_audit_seconds']/3600)
        rows.append(row)
    totals={key:sum(row['combined'][key] for row in rows) for key in rows[0]['combined']}
    n.api.require(totals['steps']==proof['physical_trajectory_steps']==46699819,'Full complete reference ledger')
    result=dict(passed=True,utc=n.job.utc().isoformat(),new_trajectory_steps=0,cases=rows,totals=totals,
        source_sha256=n.api.sha(__file__),original_cost_snapshot_sha256=n.api.sha(basepath),successor_evaluation_sha256=n.api.sha(n.PREREQUISITE),
        original_ready_audit_hashes_authenticated=authenticated,new_receipt_hashes=new_evidence,
        timing_scope=base['timing_scope'],excluded_costs=base['excluded_costs'],
        claim='Recorded complete reference-trajectory task cost only. Not elapsed campaign time, a population cost distribution or a linear longer-horizon extrapolation.')
    out=ROOT/'stage221_evaluations/cost_review_20261007/complete_reference_02'
    n.job.commit(out/'results.json',result);n.job.commit(out/'completion.json',dict(passed=True,results_sha256=n.api.sha(out/'results.json')))
    print('COMPLETE_COST',[(r['case'],r['producer_hours'],r['physics_audit_hours']) for r in rows],totals,flush=True)


if __name__=='__main__':run()
