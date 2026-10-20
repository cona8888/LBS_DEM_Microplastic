#!/usr/bin/env python3
from __future__ import annotations
import hashlib,itertools,json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(r"C:\MATDEM_MICROPLASTIC\stage28_staging")))
from stage28a_geometry_math_v1 import synchronous_distance_history
ROOT=Path(r"C:\MATDEM_MICROPLASTIC"); STUDY="stage29d_shared_pair_context_qualification_20260825"; SOURCE=ROOT/"stage29_designs"/STUDY/"candidate_geometry_01"; OUT=ROOT/"stage29_evaluations"/STUDY/"candidate_geometry_audit_01"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if OUT.exists(): raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
 p=SOURCE/"candidate_geometry.json"; cp=SOURCE/"completion.json"; d=json.loads(p.read_text()); c=json.loads(cp.read_text()); lengths=np.asarray(d["cell_dimensions_m"]); tr=np.linspace(0,d["maximum_synchronous_translation_m"],d["translation_sample_count"]); r=float(d["fibre_radius_m"]); rec={}; graphs=True
 for case in d["cases"]:
  obs=[]; mins={}
  for i,j in itertools.combinations(range(4),2):
   md=float(np.min(synchronous_distance_history(case["fibres"][i],case["fibres"][j],lengths,tr))); mins[f"{i+1}-{j+1}"]=md
   if md<=2*r: obs.append([i+1,j+1])
  exp=sorted(case["intended_predicted_contact_edges"]); obs.sort(); ok=obs==exp; graphs&=ok; rec[case["case_id"]]={"expected":exp,"observed":obs,"minimum_centreline_distance_by_pair_m":mins,"passed":ok}
 checks={"completion_passed_and_bound":c.get("passed") is True and c.get("candidate_geometry_sha256")==sha(p),"sources_bound":all(sha(Path(v["path"]))==v["sha256"] for v in d["source_bindings"].values()),"exact_six_cases":len(d["cases"])==6,"contact_graphs_recomputed_exact":graphs,"context_exactly_shared_within_blocks":all(len({tuple(x["context_source_faces"]) for x in d["cases"] if x["context_block"]==b})==1 for b in "ABC"),"context_sources_disjoint_between_blocks":len(set(sum((v["context_source_faces"] for v in d["paired_matching"].values()),[])))==6,"base_pairs_shared_but_not_called_replication":"not independent contact-location replicates" in d["interpretation"],"authority_stops_before_acceptance":d["authority"]["geometry_acceptance"] is False and d["authority"]["yade_execution"] is False}
 passed=all(checks.values()); a={"schema":d["schema"]+".audit","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":passed,"status":"passed_candidate_geometry_audit_runner_not_authorized" if passed else "failed_candidate_geometry_audit","checks":checks,"recomputed_topology":rec,"paired_matching":d["paired_matching"],"candidate_geometry_sha256":sha(p),"completion_sha256":sha(cp),"next_handoff":{"authorized":"design and independently audit a Stage29d mechanics runner/preflight derived from accepted Stage28a revision 2","not_authorized":"YADE execution, GPU flow, or permeability claims"}}
 OUT.mkdir(parents=True); ap=OUT/"geometry_audit.json"; ap.write_text(json.dumps(a,indent=2,sort_keys=True,allow_nan=False)+"\n"); (OUT/"checkpoint_manifest.json").write_text(json.dumps({"schema":d["schema"]+".checkpoint","passed":passed,"geometry_audit_sha256":sha(ap),"candidate_geometry_sha256":sha(p),"authority":a["next_handoff"]},indent=2,sort_keys=True)+"\n"); print(json.dumps({"output":str(OUT),**a},indent=2)); raise SystemExit(0 if passed else 1)
if __name__=="__main__": main()
