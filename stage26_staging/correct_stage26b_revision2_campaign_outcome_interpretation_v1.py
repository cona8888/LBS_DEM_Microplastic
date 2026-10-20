"""Correct the zero-candidate outcome wording without changing any counts."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(r"C:\MATDEM_MICROPLASTIC");E=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_evaluation_02/evaluation.json";OLD=P/"stage26_checkpoints/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_checkpoint_01/checkpoint_manifest.json";OUT=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_evaluation_03"
def d(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
def main():
 if OUT.exists():raise RuntimeError("correction exists")
 e=json.load(E.open("r",encoding="utf-8"));old=json.load(OLD.open("r",encoding="utf-8"));counts=[r["accepted_fibre_count"] for r in e["candidate_records"]];corrected=dict(e["outcome"]);corrected["seeds_accepting_zero_fibres"]=counts.count(0);corrected["seeds_accepting_one_fibre"]=counts.count(1);corrected["interpretation"]="No seed produced two admissible fibres: 5 seeds accepted one fibre before exhausting the remaining budget, and 7 seeds accepted none."
 checks={"numeric_outcome_unchanged":corrected["total_attempts"]==4800000 and corrected["passing_candidate_count"]==0 and corrected["accepted_first_fibres"]==5,"per_seed_counts_exact":corrected["seeds_accepting_zero_fibres"]==7 and corrected["seeds_accepting_one_fibre"]==5,"old_wording_is_incorrect":old["outcome"]["interpretation"]=="No two-fibre geometry met all frozen gates. Each seed accepted one fibre, but the second fibre failed within the fixed total budget.","all_v2_checks_passed":e["passed"] is True and all(e["checks"].values())}
 passed=all(checks.values());x={"schema":"lbs.stage26b-revision2-placement-campaign-evaluation.v3","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":passed,"status":"passed_semantically_corrected_verified_zero_candidate_outcome" if passed else "failed_semantic_correction","checks":checks,"outcome":corrected,"candidate_records":e["candidate_records"],"evidence":dict(e["evidence"],evaluation_v2_path=str(E),evaluation_v2_sha256=d(E),superseded_checkpoint_path=str(OLD),superseded_checkpoint_sha256=d(OLD),corrector_sha256=d(Path(__file__))),"authority":e["authority"],"claim_boundary":e["claim_boundary"]};OUT.mkdir(parents=True);p=OUT/"evaluation.json"
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
 print(json.dumps({"passed":passed,"evaluation_sha256":d(p)},sort_keys=True))
 if not passed:raise SystemExit(2)
if __name__=="__main__":main()
