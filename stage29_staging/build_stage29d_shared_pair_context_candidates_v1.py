#!/usr/bin/env python3
from __future__ import annotations
import itertools,json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(r"C:\MATDEM_MICROPLASTIC\stage29_staging")))
from build_stage29b_four_fibre_candidates_v1 import MAX_TRANSLATION,NETWORK,PATH_SEARCH,RADIUS,SAMPLES,case_features,digest,load,metrics,pair_match_score
sys.path.insert(0,str(Path(r"C:\MATDEM_MICROPLASTIC\stage28_staging")))
from stage28a_geometry_math_v1 import candidate_to_fibre
ROOT=Path(r"C:\MATDEM_MICROPLASTIC"); STUDY="stage29d_shared_pair_context_qualification_20260825"; DESIGN=ROOT/"stage29_designs"/STUDY/"design_01"/"design_manifest.json"; AUDIT=ROOT/"stage29_evaluations"/STUDY/"design_audit_01"/"design_audit.json"; PATH_HELPER=ROOT/"stage28_staging"/"stage28a_geometry_math_v1.py"; OUT=ROOT/"stage29_designs"/STUDY/"candidate_geometry_01"
def main():
 if OUT.exists(): raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
 design,audit=load(DESIGN),load(AUDIT)
 if not(audit.get("passed") and "candidate geometries" in audit["next_handoff"]["authorized"]): raise RuntimeError("audit does not authorize geometry")
 paths,network=load(PATH_SEARCH),load(NETWORK); lengths=np.asarray([network["cell_hsize_m"][i][i] for i in range(3)]); translations=np.linspace(0,MAX_TRANSLATION,SAMPLES)
 rows=[r for r in paths["candidates"] if r["first_sampled_contact_translation_m"] is None and float(r["throat_to_fibre_radius_ratio"])>=1.25 and float(r["minimum_sampled_swept_clearance_m"])>=2e-6]
 fibres=[]
 for i,r in enumerate(rows):
  f=candidate_to_fibre(r,f"candidate_{i+1}"); f.update({"archetype":"open","source":"stage26x_path_search"}); fibres.append(f)
 pair={(i,j):metrics(fibres[i],fibres[j],lengths,translations) for i,j in itertools.combinations(range(len(fibres)),2)}
 def pm(i,j): return pair[tuple(sorted((i,j)))]
 def sep(i,j): return pm(i,j)["minimum_sampled_periodic_centreline_distance_m"]>=4*RADIUS
 def cross(i,j):
  m=pm(i,j); t=m["first_predicted_contact_translation_m"]
  return m["initial_periodic_centreline_distance_m"]>=2.5*RADIUS and t is not None and .10e-3<=t<=.45e-3 and m["minimum_sampled_periodic_centreline_distance_m"]<=1.5*RADIUS
 crossings=[e for e in itertools.combinations(range(len(fibres)),2) if cross(*e)]; separated=[e for e in itertools.combinations(range(len(fibres)),2) if sep(*e)]
 solutions=[]
 for ce in crossings:
  for se in separated:
   base=set(ce+se); eligible=[i for i in range(len(fibres)) if i not in base and all(sep(i,j) for j in base)]
   extras=[e for e in itertools.combinations(eligible,2) if sep(*e)]
   triples=[]
   for tri in itertools.combinations(extras,3):
    if len(set(sum((list(e) for e in tri),[])))==6: triples.append(tri)
    if len(triples)>=25: break
   for tri in triples:
    block_scores=[]
    for ex in tri:
     cf={"features":case_features(tuple(sorted(ce+ex)),fibres,lengths)}; sf={"features":case_features(tuple(sorted(se+ex)),fibres,lengths)}
     block_scores.append(pair_match_score(sf,cf,lengths))
    solutions.append((float(np.mean([x[0] for x in block_scores])),ce,se,tri,block_scores))
 if not solutions: raise RuntimeError(f"no shared-pair three-context solution; crossing_edges={len(crossings)} separated_edges={len(separated)}")
 _,ce,se,contexts,scores=min(solutions,key=lambda x:x[0])
 cases=[]; matching={}
 for block,ex,score in zip("ABC",contexts,scores):
  for topology,base_pair in (("zero_contact",se),("one_contact",ce)):
   originals=base_pair+ex; local=[]
   for n,idx in enumerate(originals,1):
    f=dict(fibres[idx]); f["fibre_id"]=f"fibre_{n}"; local.append(f)
   cases.append({"case_id":f"s29d_f004_{topology}_context_{block}","context_block":block,"topology_regime":topology,"shared_base_pair_source_faces":[int(fibres[i]["source_face_index"]) for i in base_pair],"context_source_faces":[int(fibres[i]["source_face_index"]) for i in ex],"fibres":local,"intended_predicted_contact_edges":[] if topology=="zero_contact" else [[1,2]],"pair_metrics":{f"{i+1}-{j+1}":pm(originals[i],originals[j]) for i,j in itertools.combinations(range(4),2)},"features":case_features(tuple(sorted(originals)),fibres,lengths)})
  matching[block]={"combined_match_score":score[0],"orientation_feature_l2_mismatch":score[1],"periodic_centroid_mismatch_m":score[2],"context_source_faces":[int(fibres[i]["source_face_index"]) for i in ex]}
 checks={"source_candidate_count":len(fibres),"crossing_edge_count":len(crossings),"separated_edge_count":len(separated),"solution_count":len(solutions),"exact_six_cases":len(cases)==6,"context_sources_disjoint":len(set(sum((v["context_source_faces"] for v in matching.values()),[])))==6,"context_exactly_shared_within_block":all(len({tuple(c["context_source_faces"]) for c in cases if c["context_block"]==b})==1 for b in "ABC"),"base_pair_exactly_shared_across_blocks":all(len({tuple(c["shared_base_pair_source_faces"]) for c in cases if c["topology_regime"]==t})==1 for t in ("zero_contact","one_contact")),"predicted_graphs_exact":all(len(c["intended_predicted_contact_edges"])==(0 if c["topology_regime"]=="zero_contact" else 1) for c in cases)}
 payload={"schema":"lbs.stage29d-shared-pair-context-candidate-geometry.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":all(v for k,v in checks.items() if isinstance(v,bool)),"status":"candidate_geometry_built_independent_audit_required","cell_dimensions_m":lengths.tolist(),"fibre_radius_m":RADIUS,"maximum_synchronous_translation_m":MAX_TRANSLATION,"translation_sample_count":SAMPLES,"cases":cases,"paired_matching":matching,"checks":checks,"interpretation":design["interpretation"],"source_bindings":{"design":{"path":str(DESIGN),"sha256":digest(DESIGN)},"design_audit":{"path":str(AUDIT),"sha256":digest(AUDIT)},"path_search":{"path":str(PATH_SEARCH),"sha256":digest(PATH_SEARCH)},"network":{"path":str(NETWORK),"sha256":digest(NETWORK)},"geometry_helper":{"path":str(PATH_HELPER),"sha256":digest(PATH_HELPER)},"builder":{"path":str(Path(__file__).resolve()),"sha256":digest(Path(__file__).resolve())}},"authority":{"independent_geometry_audit":True,"geometry_acceptance":False,"runner_construction":False,"yade_execution":False,"gpu_flow":False}}
 OUT.mkdir(parents=True); p=OUT/"candidate_geometry.json"; p.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+"\n"); c={"schema":payload["schema"]+".completion","passed":payload["passed"],"status":payload["status"],"candidate_geometry_sha256":digest(p),"checks":checks,"next_handoff":{"authorized":"independent shared-pair/context geometry audit","not_authorized":"geometry acceptance, runner construction, YADE execution, or GPU flow"}}; (OUT/"completion.json").write_text(json.dumps(c,indent=2,sort_keys=True)+"\n"); print(json.dumps({"output":str(OUT),**c},indent=2))
if __name__=="__main__": main()
