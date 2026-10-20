"""Correctly audit the immutable partial output left by attempt-1 timeout."""

import csv,gzip,hashlib,json
from datetime import datetime,timezone
from pathlib import Path

P=Path(r"C:\MATDEM_MICROPLASTIC")
ROOT=P/"stage26_placements/stage26b_tier1_placement_stability_revision2_20260816/candidate_generation_01"
C1=ROOT/"stage26b_f002_revision2_candidate_01"; C2=ROOT/"stage26b_f002_revision2_candidate_02"
FIRST=P/"stage26_failures/stage26b_tier1_placement_stability_revision2_20260816/candidate_generation_attempt_01/failure.json"
OUTPUT=P/"stage26_failures/stage26b_tier1_placement_stability_revision2_20260816/candidate_generation_attempt_01_partial_audit_02"

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def count_truncated(path):
    count=0;decisions={};truncated=False
    try:
        with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
            for row in csv.DictReader(f):count+=1;decisions[row["decision"]]=decisions.get(row["decision"],0)+1
    except EOFError: truncated=True
    return count,decisions,truncated

def main():
    if OUTPUT.exists():raise RuntimeError("immutable partial audit already exists")
    completion=json.load((C1/"completion.json").open("r",encoding="utf-8")); placement=json.load((C1/"placement.json").open("r",encoding="utf-8"))
    rows2,decisions2,truncated2=count_truncated(C2/"attempts.csv.gz")
    confirmed=(completion["passed"] is False and completion["attempt_count"]==400000 and placement["fibre_count"]==1 and rows2>0 and truncated2 and not (ROOT/"completion.json").exists())
    record={"schema":"lbs.stage26b-revision2-placement-generation-attempt-partial-audit.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":False,"status":"confirmed_external_timeout_after_candidate1_before_candidate2_completion","checks":{"candidate1_budget_completed_failed_geometry":completion["passed"] is False and completion["attempt_count"]==400000,"candidate1_hashes_match":completion["placement_sha256"]==digest(C1/"placement.json") and completion["attempts_sha256"]==digest(C1/"attempts.csv.gz"),"candidate2_partial_truncated_ledger":rows2>0 and truncated2,"campaign_completion_absent":not (ROOT/"completion.json").exists(),"first_recorder_failed_closed":json.load(FIRST.open("r",encoding="utf-8"))["authority"]["attempt2_preparation_authorized"] is False},"partial_evidence":{"candidate1_completion_path":str(C1/"completion.json"),"candidate1_completion_sha256":digest(C1/"completion.json"),"candidate1_placement_sha256":digest(C1/"placement.json"),"candidate1_ledger_sha256":digest(C1/"attempts.csv.gz"),"candidate2_partial_rows":rows2,"candidate2_decision_counts":decisions2,"candidate2_ledger_sha256":digest(C2/"attempts.csv.gz"),"first_recorder_path":str(FIRST),"first_recorder_sha256":digest(FIRST)},"adaptive_decision":"Repeat the unchanged deterministic campaign from candidate 1 at a new immutable output using a long-lived supervisor timeout; no search or physics change.","authority":{"attempt2_preparation_authorized":confirmed,"placement_generation_authorized":False,"prefilter_yade_execution_authorized":False,"two_fibre_free_release_authorized":False,"four_fibre_execution_authorized":False,"flow_execution_authorized":False},"claim_boundary":"Partial offline geometry-search audit only; no YADE or physical result."}
    OUTPUT.mkdir(parents=True);path=OUTPUT/"failure.json"
    with path.open("x",encoding="utf-8") as f:json.dump(record,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
    print(json.dumps({"confirmed":confirmed,"candidate2_rows":rows2,"failure_sha256":digest(path)},sort_keys=True))
    if not confirmed:raise SystemExit(2)

if __name__=="__main__":main()
