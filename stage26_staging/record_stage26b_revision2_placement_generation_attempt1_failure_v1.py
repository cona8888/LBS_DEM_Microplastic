"""Preserve the command-supervision timeout of placement campaign attempt 1."""

import csv, gzip, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

PROJECT=Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG=PROJECT/"stage26_staging/stage26b_revision2_placement_generation_execution_v1.json"
PRERUN=PROJECT/"stage26_checkpoints/stage26b_tier1_placement_stability_revision2_20260816/placement_generation_prerun_checkpoint_01/checkpoint_manifest.json"
ROOT=PROJECT/"stage26_placements/stage26b_tier1_placement_stability_revision2_20260816/candidate_generation_01"
LEDGER=ROOT/"stage26b_f002_revision2_candidate_01/attempts.csv.gz"
OUTPUT=PROJECT/"stage26_failures/stage26b_tier1_placement_stability_revision2_20260816/candidate_generation_attempt_01"

def digest(path):
    value=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""): value.update(block)
    return value.hexdigest()

def main():
    if OUTPUT.exists(): raise RuntimeError("immutable failure record already exists")
    rows=0; decisions={}; last=None
    with gzip.open(LEDGER,"rt",encoding="utf-8",newline="") as stream:
        for row in csv.DictReader(stream):
            rows+=1; decisions[row["decision"]]=decisions.get(row["decision"],0)+1; last=row
    confirmed=rows==400000 and last["attempt_index"]=="400000" and not (ROOT/"completion.json").exists() and not (ROOT/"stage26b_f002_revision2_candidate_01/completion.json").exists()
    failure={"schema":"lbs.stage26b-revision2-placement-generation-attempt-failure.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":False,"status":"terminated_by_command_supervision_after_candidate1_budget","failure_classification":"external_command_timeout_not_geometry_exception","partial_evidence":{"candidate_id":"stage26b_f002_revision2_candidate_01","ledger_rows":rows,"decision_counts":decisions,"last_attempt":last,"ledger_path":str(LEDGER),"ledger_sha256":digest(LEDGER)},"source_hashes":{"config":digest(CONFIG),"prerun_checkpoint":digest(PRERUN),"recorder":digest(Path(__file__))},"adaptive_decision":"Rerun the unchanged deterministic source and seeds to a new immutable output under a long-lived command supervisor; do not change search budgets or geometry gates.","authority":{"attempt2_preparation_authorized":confirmed,"placement_generation_authorized":False,"prefilter_yade_execution_authorized":False,"two_fibre_free_release_authorized":False,"four_fibre_execution_authorized":False,"flow_execution_authorized":False},"claim_boundary":"Partial offline geometry-search evidence only; no YADE or physical result."}
    OUTPUT.mkdir(parents=True); path=OUTPUT/"failure.json"
    with path.open("x",encoding="utf-8") as stream: json.dump(failure,stream,indent=2,sort_keys=True,allow_nan=False); stream.write("\n")
    print(json.dumps({"passed":False,"confirmed":confirmed,"failure_sha256":digest(path)},sort_keys=True))
    if not confirmed: raise SystemExit(2)

if __name__=="__main__": main()
