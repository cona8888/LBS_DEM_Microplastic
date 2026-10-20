from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(r"C:\MATDEM_MICROPLASTIC"); STUDY="stage29d_shared_pair_context_qualification_20260825"; SOURCE=ROOT/"stage29_designs"/STUDY/"design_01"; OUT=ROOT/"stage29_evaluations"/STUDY/"design_audit_01"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canon(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def main():
 if OUT.exists(): raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
 p=SOURCE/"design_manifest.json"; cp=SOURCE/"completion.json"; d=json.loads(p.read_text()); c=json.loads(cp.read_text()); cases=d["cases"]
 checks={"completion_passed_and_bound":c.get("passed") is True and c.get("design_manifest_sha256")==sha(p),"sources_bound":all(sha(Path(d["source_paths"][k]))==v for k,v in d["source_hashes"].items()),"stage29c_failure_bound":"stage29c_failure" in d["source_hashes"],"exact_six_cases":len(cases)==6 and len({x["case_id"] for x in cases})==6,"three_paired_context_blocks":all({x["topology_regime"] for x in cases if x["context_block"]==b}=={"zero_contact","one_contact"} for b in "ABC"),"shared_pairs_declared":all(x["base_pair"].endswith("_shared") for x in cases),"context_not_mislabelled_replication":"not independent contact-location replicates" in d["interpretation"],"matrix_bound":d["case_matrix_sha256"]==canon(cases),"execution_forbidden":all(d["authority"][k] is False for k in ("candidate_geometry_generation","geometry_acceptance","runner_construction","yade_execution","gpu_flow"))}
 passed=all(checks.values()); a={"schema":d["schema"]+".audit","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":passed,"status":"passed_design_audit_geometry_not_authorized" if passed else "failed_design_audit","checks":checks,"design_manifest_sha256":sha(p),"completion_sha256":sha(cp),"next_handoff":{"authorized":"build and independently audit shared-pair/context-block candidate geometries","not_authorized":"geometry acceptance, runner construction, YADE execution, or GPU flow"}}
 OUT.mkdir(parents=True); ap=OUT/"design_audit.json"; ap.write_text(json.dumps(a,indent=2,sort_keys=True)+"\n"); (OUT/"checkpoint_manifest.json").write_text(json.dumps({"schema":d["schema"]+".checkpoint","passed":passed,"design_audit_sha256":sha(ap),"design_manifest_sha256":sha(p),"authority":a["next_handoff"]},indent=2,sort_keys=True)+"\n"); print(json.dumps({"output":str(OUT),**a},indent=2)); raise SystemExit(0 if passed else 1)
if __name__=="__main__": main()
