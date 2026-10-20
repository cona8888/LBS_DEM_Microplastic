"""Correct a bookkeeping test using exact clock recurrences, not a looser epsilon.

Preserve the original failed qualification. No new trajectories or model changes.
Every interval must obey t_next == float(t_previous + dt) bitwise; positive dt,
exact final clock, step count, and an exact rational rounding bound are required.
"""
from pathlib import Path
from fractions import Fraction
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage139_staging'))
import sphere_only_verification_v1 as parent
api = parent.api
SOURCE = ROOT/'stage148_evaluations/local_compiled_contract_20260921/qualification_01'
OUT = SOURCE.parent/'exact_clock_audit_01'


def clock_chain(t0, rows, final):
    clock = t0
    exact_sum = Fraction.from_float(t0)
    bound = Fraction(0)
    wrong = []
    positive = True
    for i, row in enumerate(rows):
        dt = row['dt_s']
        positive &= bool(math.isfinite(dt) and dt > 0)
        candidate = float(clock+dt)
        if row['time_s'] != candidate:
            wrong.append(i)
        exact_sum += Fraction.from_float(dt)
        bound += Fraction.from_float(math.ulp(candidate))/2
        clock = row['time_s']
    defect = abs(Fraction.from_float(final)-exact_sum)
    return {'passed': positive and not wrong and clock == final and defect <= bound,
            'positive_intervals': positive,'nonreproduced_clock_indices':wrong,
            'exact_final_clock':clock == final,'rational_roundoff_bound_pass':defect<=bound,
            'summation_defect_s':float(defect),'derived_half_ulp_sum_bound_s':float(bound),
            'integrated_steps':len(rows)}


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    ev = api.read(SOURCE/'results.json'); seal=api.read(SOURCE/'completion.json')
    api.require(api.sha(SOURCE/'results.json') == seal['results_sha256'],'evaluation seal')
    api.verify_mapping(ev['artifacts'])
    pp=api.read(SOURCE/'protocol.json')
    api.verify_mapping(pp['sources']);api.verify_mapping(pp['inputs'])
    protocol={'stage':'Stage148 independent exact-clock audit',
              'input_results_sha256':api.sha(SOURCE/'results.json'),
              'source_sha256':api.sha(__file__),
              'acceptance':'Every recorded t_next equals binary64(t_previous+dt) exactly. Positive intervals, exact endpoint, exact step count. Exact rational defect <= sum(half ULP of each resulting absolute clock). No simulation or state comparison tolerances changed.',
              'reason':'A fixed absolute tolerance on separately summed dt cannot correctly test repeated absolute-clock addition over varying numbers of steps.',
              'negative_controls':['one-ULP altered row clock','doubled dt','dropped interval'],
              'preserve_original_failed_evaluation':True,'simulation_dispatch':False}
    api.write(OUT/'protocol.json',protocol)
    rows=[]
    for p in sorted(SOURCE.glob('*.json')):
        rec=api.read(p)
        if 'result' not in rec or 'rows' not in rec: continue
        initial=api.read(rec['source'])['result']['checkpoint']['state']
        if p.stem=='restart_second':
            initial=api.read(SOURCE/'restart_first.json')['result']['checkpoint']['state']
        result=rec['result']; intervals=rec['rows']
        clock=clock_chain(initial['t'],intervals,result['time_s'])
        health=rec['health']['passed'] and all(c['passed'] for c in rec['certificates'])
        steps=result['steps']-initial['steps']==len(intervals)
        record_integrity=rec['checkpoint_hash_pass'] and rec['coordinate_scale_verified']
        rows.append({'file':str(p),'sha256':api.sha(p),'clock':clock,'old_clock_gate':rec['clock_closure'],
                     'physical_health':health,'step_count':steps,'passed':clock['passed'] and health and steps and record_integrity})
    rec=api.read(SOURCE/'local_factor_0.5_kappa_16.json')
    t0=api.read(rec['source'])['result']['time_s']; interval=rec['rows'][0]
    controls=[]
    for name in protocol['negative_controls']:
        import copy
        corrupt=copy.deepcopy(rec['rows'])
        if name=='one-ULP altered row clock': corrupt[10]['time_s']=math.nextafter(corrupt[10]['time_s'],math.inf)
        elif name=='doubled dt': corrupt[10]['dt_s']*=2
        else: corrupt.pop(10)
        test=clock_chain(t0,corrupt,rec['result']['time_s'])
        controls.append({'id':name,'passed':not test['passed'],'clock':test})
    refinements=[]
    base=api.read(SOURCE/'local_factor_1_kappa_16.json')
    limits=pp['acceptance']['sphere_common_clock_limits']
    for p in sorted(SOURCE.glob('local_factor_*.json')):
        rec=api.read(p)
        cmp=parent.old.prior.compare_results(base['result'],rec['result'],rec['spec'],limits)
        cmp.update(file=str(p),factor=rec['dt_factor'],kappa=rec['kappa'])
        refinements.append(cmp)
    old_pass_parts = ev['disabled_replays']+ev['fibre_exclusions']+ev['common_clock_comparisons']+ev['endpoints']+[ev['restart']]+ev['negative_controls']
    accepted = all(r['passed'] for r in rows+controls+refinements+old_pass_parts) and ev['primitive_tests_passed']==ev['primitive_tests_total']==42
    result={'stage':'Stage148','qualification_passed':accepted,'original_fixed_sum_evaluation_passed':ev['passed'],
            'all_record_clock_chains':rows,'negative_clock_controls':controls,'unchanged_physical_refinement_limits':limits,
            'refinements':refinements,'primitive_tests':42,'disabled_bitwise_replays':7,'fibre_exclusions':3,
            'contact_certificates':ev['trajectory_contact_certificates'],
            'legacy_energy_gate_violations':ev['legacy_energy_gate_violations'],
            'claim':'Sphere-only compiled numerical revision locally qualified; default-off and no fibre or inertia promotion. Full-duration sphere continuation may be the next bounded test, not a validated release population.',
            'artifacts':{str(p):api.sha(p) for p in OUT.iterdir() if p.is_file()},
            'source_evaluation_sha256':api.sha(SOURCE/'results.json')}
    api.verify_mapping(pp['sources']);api.verify_mapping(pp['inputs']);api.verify_mapping(ev['artifacts'])
    api.write(OUT/'results.json',result,raw=True)
    api.write(OUT/'completion.json',{'passed':accepted,'results_sha256':api.sha(OUT/'results.json'),
                                   'protocol_sha256':api.sha(OUT/'protocol.json')})
    print('EXACT_CLOCK_QUALIFICATION',accepted,'records',len(rows),'controls',len(controls),flush=True)
    return 0 if accepted else 4


if __name__=='__main__':
    raise SystemExit(main())
