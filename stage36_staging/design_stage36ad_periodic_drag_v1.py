"""Analytical and resolution feasibility for Stage36AD; no flow solve."""
import argparse, hashlib, json, math, platform
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "stage36_staging" / "STAGE36AD_PERIODIC_SPHERE_DRAG_DESIGN.md"
PARENT = ROOT / "stage36_evaluations" / "stage36ac_literature_observable_readiness_20260909" / "audit_01" / "audit.json"

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def mobility(lam, order):
    value = 1 - 2.837297 * lam
    if order >= 3: value += 4.19 * lam**3
    if order >= 7: value -= 27.4 * lam**7
    return value

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); args=ap.parse_args()
    if args.output.exists(): raise FileExistsError(f"immutable output exists: {args.output}")
    parent=json.loads(PARENT.read_text(encoding="utf-8"))
    if not parent["accounting_schema_ready"] or parent["transport_run_authorized"]: raise ValueError("invalid Stage36AC lineage state")
    lam=.125; nu=mu=.1; re=.05; U=re*nu/(2*lam); cs=1/math.sqrt(3)
    factors={str(o):mobility(lam,o) for o in (1,3,7)}
    if min(factors.values())<=0: raise ValueError("nonpositive periodic mobility")
    rows=[]
    for n in (32,48,64):
        a_lu=lam*n; U_lu=U/n
        rows.append({"N":n,"radius_lu":a_lu,"diameter_lu":2*a_lu,"U_lu_diffusive":U_lu,
                     "mach":U_lu/cs,"minimum_radius_nodes_pass":a_lu>=4,"force_conclusion_candidate":a_lu>=6})
    result={"stage":"Stage36AD","timestamp_utc":datetime.now(timezone.utc).isoformat(),"status":"analytical_design_passed_flow_not_run",
            "lambda":lam,"nu":nu,"mu":mu,"target_particle_reynolds":re,"target_velocity_physical":U,
            "mobility_ratio_by_truncation":factors,"drag_ratio_order7":1/factors["7"],
            "order1_to_order7_relative_difference":abs(factors["1"]-factors["7"])/factors["7"],
            "candidate_grids":rows,"all_health_prerequisites_pass":all(r["minimum_radius_nodes_pass"] and r["mach"]<=.03 for r in rows),
            "force_tolerance_frozen":False,"flow_executed":False,"release_qualified":False,
            "next_action":"obtain or reproduce a higher-order simple-cubic drag value at lambda=0.125, freeze tolerance, then implement N32 diagnostic and N48/N64 confirmation",
            "input_hashes":{"contract":sha(CONTRACT),"stage36ac_parent":sha(PARENT)},"python":platform.python_version()}
    args.output.mkdir(parents=True)
    (args.output/"design.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    lines=["# Stage36AD periodic-sphere drag feasibility","",f"Analytical design passed; no flow was run. At `a/L={lam}`, the order-7 mobility factor is `{factors['7']:.9f}` and the periodic drag is `{1/factors['7']:.6f}` times isolated Stokes drag.","",f"The leading-only and order-7 mobility values differ by `{100*result['order1_to_order7_relative_difference']:.3f}%`; this is not a bound on omitted terms. A higher-order/table comparator is therefore required before freezing the force-error tolerance.","","| Grid | radius (lu) | Mach | Role |","|---:|---:|---:|---|" ]
    for r in rows: lines.append(f"| {r['N']} | {r['radius_lu']:.1f} | {r['mach']:.6f} | {'confirmation candidate' if r['force_conclusion_candidate'] else 'coarse diagnostic'} |")
    lines += ["","No calibration, DEM/LBM flow, GPU job, permeability calculation or release prediction was started.",""]
    (args.output/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")

if __name__=="__main__": main()
