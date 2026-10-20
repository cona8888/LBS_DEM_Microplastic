"""Verify all twelve immutable placement-search outcomes and rejection ledgers."""
import csv,gzip,hashlib,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
P=Path(r"C:\MATDEM_MICROPLASTIC");ROOT=P/"stage26_placements/stage26b_tier1_placement_stability_revision2_20260816/candidate_generation_02";CONFIG=P/"stage26_staging/stage26b_revision2_placement_generation_execution_v2.json";PRERUN=P/"stage26_checkpoints/stage26b_tier1_placement_stability_revision2_20260816/placement_generation_prerun_checkpoint_02/checkpoint_manifest.json";OUTPUT=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_campaign_evaluation_01"
def d(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def load(p):return json.load(p.open("r",encoding="utf-8-sig"))
def main():
 if OUTPUT.exists():raise RuntimeError("immutable campaign evaluation exists")
 cfg=load(CONFIG);campaign=load(ROOT/"completion.json");prerun=load(PRERUN);aggregate=Counter();records=[];all_valid=True
 with (ROOT/"candidate_index.csv").open("r",newline="",encoding="utf-8") as f:index=list(csv.DictReader(f))
 for candidate in cfg["candidates"]:
  cdir=ROOT/candidate["candidate_id"];placement=load(cdir/"placement.json");completion=load(cdir/"completion.json");count=0;decisions=Counter();last=None;closed=True
  try:
   with gzip.open(cdir/"attempts.csv.gz","rt",encoding="utf-8",newline="") as f:
    for row in csv.DictReader(f):count+=1;decisions[row["decision"]]+=1;last=row
  except EOFError:closed=False
  aggregate.update(decisions)
  valid=(closed and count==completion["attempt_count"]==placement["attempt_count"]==400000 and completion["passed"] is False and placement["passed"] is False and placement["fibre_count"]==1 and completion["placement_sha256"]==d(cdir/"placement.json") and completion["attempts_sha256"]==d(cdir/"attempts.csv.gz") and last["attempt_index"]=="400000")
  all_valid=all_valid and valid
  records.append({"candidate_id":candidate["candidate_id"],"passed":False,"attempt_count":count,"accepted_fibre_count":placement["fibre_count"],"decision_counts":dict(sorted(decisions.items())),"placement_sha256":d(cdir/"placement.json"),"attempts_sha256":d(cdir/"attempts.csv.gz"),"completion_sha256":d(cdir/"completion.json"),"valid":valid})
 checks={"campaign_completion_passed_as_budget_completion":campaign["passed"] is True and campaign["status"]=="completed_predeclared_candidate_budgets","exact_twelve_zero_passing":campaign["candidate_count"]==len(index)==12 and campaign["passing_candidate_count"]==0 and all(row["passed"]=="False" for row in index),"all_candidate_bundles_and_ledgers_valid":all_valid,"exact_total_attempt_budget":sum(row["attempt_count"] for row in records)==4800000,"campaign_index_hash_matches":campaign["candidate_index_sha256"]==d(ROOT/"candidate_index.csv"),"source_hashes_exact":campaign["source_hashes"]=={"config":d(CONFIG),"network":d(Path(cfg["sources"]["network"])),"generator":d(Path(cfg["sources"]["generator"]))},"prerun_authority_bound":prerun["passed"] is True and prerun["evidence"]["config_sha256"]==d(CONFIG) and prerun["authority"]["placement_generation_authorized"] is True,"no_yade_or_physical_authority":all(cfg["authority"][name] is False for name in cfg["authority"] if name!="placement_generation_authorized")}
 passed=all(checks.values());rejection_total=sum(v for k,v in aggregate.items() if k!="accepted");ranked=sorted(((k,v,v/rejection_total) for k,v in aggregate.items() if k!="accepted"),key=lambda x:(-x[1],x[0]))
 ev={"schema":"lbs.stage26b-revision2-placement-campaign-evaluation.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":passed,"status":"passed_verified_zero_candidate_outcome" if passed else "failed_campaign_verification","checks":checks,"outcome":{"candidate_count":12,"passing_candidate_count":0,"total_attempts":4800000,"accepted_first_fibres":aggregate["accepted"],"aggregate_decision_counts":dict(sorted(aggregate.items())),"ranked_rejection_mechanisms":[{"decision":k,"count":v,"fraction_of_rejections":f} for k,v,f in ranked],"interpretation":"No two-fibre geometry met all frozen gates. Each seed accepted one fibre, but the second fibre failed within the fixed total budget."},"candidate_records":records,"evidence":{"root":str(ROOT),"campaign_completion_path":str(ROOT/"completion.json"),"campaign_completion_sha256":d(ROOT/"completion.json"),"candidate_index_path":str(ROOT/"candidate_index.csv"),"candidate_index_sha256":d(ROOT/"candidate_index.csv"),"config_path":str(CONFIG),"config_sha256":d(CONFIG),"prerun_checkpoint_path":str(PRERUN),"prerun_checkpoint_sha256":d(PRERUN),"verifier_sha256":d(Path(__file__))},"authority":{"diagnostic_redesign_preparation_authorized":passed,"placement_generation_authorized":False,"prefilter_yade_execution_authorized":False,"two_fibre_free_release_authorized":False,"four_fibre_execution_authorized":False,"flow_execution_authorized":False},"claim_boundary":cfg["claim_boundary"]}
 OUTPUT.mkdir(parents=True);path=OUTPUT/"evaluation.json"
 with path.open("x",encoding="utf-8") as f:json.dump(ev,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
 print(json.dumps({"passed":passed,"evaluation_sha256":d(path),"top_rejections":ranked[:4]},sort_keys=True))
 if not passed:print([k for k,v in checks.items() if not v]);raise SystemExit(2)
if __name__=="__main__":main()
