"""Corrected campaign verification allowing zero or one accepted fibre."""
import csv,gzip,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(r"C:\MATDEM_MICROPLASTIC");ROOT=P/"stage26_placements/stage26b_tier1_placement_stability_revision2_20260816/candidate_generation_02";FIRST=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_evaluation_01/evaluation.json";FAIL=P/"stage26_failures/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_verification_01/failure.json";OUTPUT=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_evaluation_02"
def d(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def load(p):return json.load(p.open("r",encoding="utf-8"))
def main():
 if OUTPUT.exists():raise RuntimeError("evaluation exists")
 first=load(FIRST);failure=load(FAIL);correct=[];all_ok=True
 for old in first["candidate_records"]:
  c=ROOT/old["candidate_id"];pl=load(c/"placement.json");co=load(c/"completion.json");n=0;closed=True
  try:
   with gzip.open(c/"attempts.csv.gz","rt",encoding="utf-8",newline="") as f:
    for _ in csv.DictReader(f):n+=1
  except EOFError:closed=False
  ok=closed and n==400000==pl["attempt_count"]==co["attempt_count"] and pl["passed"] is False and co["passed"] is False and pl["fibre_count"] in (0,1) and co["placement_sha256"]==d(c/"placement.json") and co["attempts_sha256"]==d(c/"attempts.csv.gz") and old["placement_sha256"]==d(c/"placement.json") and old["attempts_sha256"]==d(c/"attempts.csv.gz")
  all_ok=all_ok and ok;correct.append(dict(old,valid=ok))
 checks={"first_failure_preserved_and_narrow":failure["authority"]["corrected_reverification_authorized"] is True and [k for k,v in first["checks"].items() if not v]==["all_candidate_bundles_and_ledgers_valid"],"all_other_first_checks_passed":all(v for k,v in first["checks"].items() if k!="all_candidate_bundles_and_ledgers_valid"),"all_candidate_bundles_valid_under_correct_rule":all_ok,"zero_two_fibre_candidates_confirmed":all(r["accepted_fibre_count"] in (0,1) for r in correct) and not any(r["passed"] for r in correct),"first_evidence_files_unchanged":d(Path(first["evidence"]["campaign_completion_path"]))==first["evidence"]["campaign_completion_sha256"] and d(Path(first["evidence"]["candidate_index_path"]))==first["evidence"]["candidate_index_sha256"]}
 passed=all(checks.values());ev={"schema":"lbs.stage26b-revision2-placement-campaign-evaluation.v2","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":passed,"status":"passed_corrected_verified_zero_candidate_outcome" if passed else "failed_corrected_campaign_verification","checks":checks,"outcome":first["outcome"],"candidate_records":correct,"evidence":dict(first["evidence"],first_evaluation_path=str(FIRST),first_evaluation_sha256=d(FIRST),first_failure_path=str(FAIL),first_failure_sha256=d(FAIL),verifier_v2_sha256=d(Path(__file__))),"authority":{"diagnostic_redesign_preparation_authorized":passed,"placement_generation_authorized":False,"prefilter_yade_execution_authorized":False,"two_fibre_free_release_authorized":False,"four_fibre_execution_authorized":False,"flow_execution_authorized":False},"claim_boundary":first["claim_boundary"]};OUTPUT.mkdir(parents=True);p=OUTPUT/"evaluation.json"
 with p.open("x",encoding="utf-8") as f:json.dump(ev,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
 print(json.dumps({"passed":passed,"evaluation_sha256":d(p)},sort_keys=True))
 if not passed:print([k for k,v in checks.items() if not v]);raise SystemExit(2)
if __name__=="__main__":main()
