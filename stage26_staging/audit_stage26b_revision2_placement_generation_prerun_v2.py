"""Audit the long-supervision retry without changing search inputs."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
P=Path(r"C:\MATDEM_MICROPLASTIC"); CONFIG=P/"stage26_staging/stage26b_revision2_placement_generation_execution_v2.json"; OUTPUT=P/"stage26_evaluations/stage26b_tier1_placement_stability_revision2_20260816/placement_generation_prerun_evaluation_02"
def digest(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def load(path):return json.load(path.open("r",encoding="utf-8-sig"))
def main():
 if OUTPUT.exists():raise RuntimeError("immutable retry audit exists")
 cfg=load(CONFIG); old=load(Path(cfg["sources"]["attempt1_config"])); failure=load(Path(cfg["sources"]["attempt1_partial_audit"])); paths={n:Path(v) for n,v in cfg["sources"].items() if not n.endswith("_sha256")}
 checks={"all_source_hashes_match":all(digest(v)==cfg["sources"][n+"_sha256"] for n,v in paths.items()),"partial_timeout_audit_authorizes_retry":failure["authority"]["attempt2_preparation_authorized"] is True,"source_contract_candidates_unchanged":cfg["generator_contract"]==old["generator_contract"] and cfg["candidates"]==old["candidates"],"only_output_and_supervision_retry":cfg["execution"]["output"].endswith("candidate_generation_02") and cfg["execution"]["required_command_supervision_timeout_seconds"]==3600 and not Path(cfg["execution"]["output"]).exists(),"same_generator_and_network":cfg["sources"]["generator_sha256"]==old["sources"]["generator_sha256"] and cfg["sources"]["network_sha256"]==old["sources"]["network_sha256"],"narrow_offline_authority":cfg["authority"]["placement_generation_authorized"] is True and all(v is False for n,v in cfg["authority"].items() if n!="placement_generation_authorized")}
 passed=all(checks.values()); ev={"schema":"lbs.stage26b-revision2-placement-generation-prerun-evaluation.v2","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":passed,"status":"passed_long_supervision_unchanged_campaign_retry" if passed else "failed_campaign_retry_audit","checks":checks,"evidence":{"config_path":str(CONFIG),"config_sha256":digest(CONFIG),"generator_path":str(paths["generator"]),"generator_sha256":digest(paths["generator"]),"network_path":str(paths["network"]),"network_sha256":digest(paths["network"]),"partial_failure_path":str(paths["attempt1_partial_audit"]),"partial_failure_sha256":digest(paths["attempt1_partial_audit"]),"auditor_sha256":digest(Path(__file__))},"frozen_execution":cfg["execution"],"authority":{"placement_generation_authorized":passed,"prefilter_yade_execution_authorized":False,"two_fibre_free_release_authorized":False,"four_fibre_execution_authorized":False,"flow_execution_authorized":False},"claim_boundary":cfg["claim_boundary"]}
 OUTPUT.mkdir(parents=True);path=OUTPUT/"evaluation.json"
 with path.open("x",encoding="utf-8") as f:json.dump(ev,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
 print(json.dumps({"passed":passed,"evaluation_sha256":digest(path)},sort_keys=True))
 if not passed:print([n for n,v in checks.items() if not v]);raise SystemExit(2)
if __name__=="__main__":main()
