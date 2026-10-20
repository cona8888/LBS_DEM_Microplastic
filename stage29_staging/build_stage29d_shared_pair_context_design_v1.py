from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"C:\MATDEM_MICROPLASTIC")
STUDY="stage29d_shared_pair_context_qualification_20260825"
OUT=ROOT/"stage29_designs"/STUDY/"design_01"
SOURCES={
 "contract":ROOT/"stage29_staging"/"STAGE29D_SHARED_PAIR_CONTEXT_BLOCK_DESIGN_CONTRACT.md",
 "stage29c_failure":ROOT/"stage29_designs"/"stage29c_four_fibre_single_contact_qualification_20260825"/"candidate_geometry_01"/"failure.json",
 "stage29c_design_audit":ROOT/"stage29_evaluations"/"stage29c_four_fibre_single_contact_qualification_20260825"/"design_audit_01"/"design_audit.json",
 "stage28a_mechanics_evaluation":ROOT/"stage28_evaluations"/"stage28a_two_fibre_mechanics_hydraulics_20260824"/"mechanics_evaluation_02"/"evaluation.json",
}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canon(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def main():
 if OUT.exists(): raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
 if any(not p.is_file() for p in SOURCES.values()): raise RuntimeError("missing source")
 cases=[]
 for b in "ABC":
  cases += [
   {"case_id":f"s29d_f004_zero_contact_context_{b}","context_block":b,"base_pair":"separated_pair_shared","topology_regime":"zero_contact","expected_contact_edges":[],"context_pair_shared_within_block":True,"context_sources_distinct_between_blocks":True},
   {"case_id":f"s29d_f004_one_contact_context_{b}","context_block":b,"base_pair":"crossing_pair_shared","topology_regime":"one_contact","expected_contact_edges":[[1,2]],"context_pair_shared_within_block":True,"context_sources_distinct_between_blocks":True},
  ]
 d={"schema":"lbs.stage29d-shared-pair-context-qualification.v1","study_id":STUDY,"timestamp_utc":datetime.now(timezone.utc).isoformat(),"status":"designed_geometry_not_authorized","cases":cases,"case_matrix_sha256":canon(cases),"interpretation":"Three paired context blocks around one shared contact pair and one shared separated control pair; context blocks are not independent contact-location replicates.","hard_gates":{"four_fibres_each":True,"context_pair_exactly_shared_within_block":True,"context_sources_disjoint_between_blocks":True,"zero_contact_edges":0,"one_contact_edges":1,"all_other_pairs_minimum_centreline_distance_fibre_radii":4.0,"fixed_sand_and_cell_exact":True,"stage28a_mechanics_gates_inherited":True},"authority":{"design_generation":True,"design_audit":True,"candidate_geometry_generation":False,"geometry_acceptance":False,"runner_construction":False,"yade_execution":False,"gpu_flow":False},"source_paths":{k:str(v) for k,v in SOURCES.items()},"source_hashes":{k:sha(v) for k,v in SOURCES.items()}}
 OUT.mkdir(parents=True); p=OUT/"design_manifest.json"; p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
 c={"schema":d["schema"]+".completion","passed":True,"status":"passed_design_generation_geometry_not_authorized","design_manifest_sha256":sha(p),"next_handoff":"independent design audit"}
 (OUT/"completion.json").write_text(json.dumps(c,indent=2,sort_keys=True)+"\n"); print(json.dumps({"output":str(OUT),**c},indent=2))
if __name__=="__main__": main()
