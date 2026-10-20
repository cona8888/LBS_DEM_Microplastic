"""Preserve verifier-1's over-specific one-accepted-fibre assumption."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(r"C:\MATDEM_MICROPLASTIC");E=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_evaluation_01/evaluation.json";O=P/"stage26_failures/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_verification_01"
def d(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
def main():
 if O.exists():raise RuntimeError("failure exists")
 e=json.load(E.open("r",encoding="utf-8"));failed=[k for k,v in e["checks"].items() if not v];counts=[r["accepted_fibre_count"] for r in e["candidate_records"]];confirmed=failed==["all_candidate_bundles_and_ledgers_valid"] and set(counts)<={0,1} and 0 in counts and 1 in counts
 x={"schema":"lbs.stage26b-revision2-campaign-verifier-failure.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":False,"status":"failed_over_specific_accepted_fibre_count_assumption","failed_checks":failed,"observed_accepted_fibre_counts":counts,"diagnosis":"A failed two-fibre candidate may exhaust its budget before accepting any fibre or after accepting one fibre; both are valid zero-candidate outcomes.","evidence":{"evaluation_path":str(E),"evaluation_sha256":d(E)},"authority":{"corrected_reverification_authorized":confirmed,"placement_generation_authorized":False,"prefilter_yade_execution_authorized":False,"flow_execution_authorized":False},"claim_boundary":"Verifier-method failure only; campaign evidence is unchanged."};O.mkdir(parents=True);p=O/"failure.json"
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,indent=2,sort_keys=True);f.write("\n")
 print(json.dumps({"confirmed":confirmed,"failure_sha256":d(p)},sort_keys=True))
 if not confirmed:raise SystemExit(2)
if __name__=="__main__":main()
