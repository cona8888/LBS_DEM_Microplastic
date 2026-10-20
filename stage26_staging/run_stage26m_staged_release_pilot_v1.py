"""Stage26m exact-fibre staged-release co-compaction development pilot."""
from __future__ import print_function
import json,math,os,sys,time
from datetime import datetime,timezone
HERE=os.path.dirname(os.path.abspath(os.environ.get("STAGE26M_SCRIPT",__file__)))
if HERE not in sys.path:sys.path.insert(0,HERE)
from yade import config
from stage26b_revision2_prefilter_common_v1 import load_json,sha256,windows_to_wsl,write_json_exclusive
from stage26h_common_v1 import diagnostic,diagonal_lengths,write_history,zero_motion
from run_stage26k_loose_cocompaction_pilot_v1 import solid_volume,enrich,gate as base_gate
from run_stage26l_mobile_cocompaction_pilot_v1 import quat,motion
START=time.time()

def authority(cfg):
 if cfg.get("status")!="authorized_stage26m_spent_development_staged_release_pilot":raise RuntimeError("not Stage26m-authorized")
 a=cfg["authority"]
 if a.get("staged_release_cocompaction_authorized") is not True or any(a.get(k,False) for k in ("heldout_execution_authorized","reserve_execution_authorized","flow_execution_authorized","deformation_authorized","production_parametric_study_authorized")):raise RuntimeError("Stage26m authority exceeded")
def bind(cfg):
 for k,v in cfg["sources"].items():
  if k.endswith("_sha256") or k=="expected_yade_version":continue
  expected=cfg["sources"].get(k+"_sha256")
  if expected is not None and sha256(windows_to_wsl(v))!=expected:raise RuntimeError("source hash mismatch: "+k)
def gates(row,cfg):
 checks=base_gate(row,cfg);g=cfg["motion_guards"];checks["bounded_translation"]=row["maximum_fibre_translation_over_D50"]<=g["maximum_nonaffine_translation_over_D50"];checks["bounded_rotation"]=row["maximum_fibre_rotation_deg"]<=g["maximum_rotation_deg"];return checks

def main():
 config_path=os.path.abspath(os.environ["STAGE26M_CONFIG"]);output=os.path.abspath(os.environ["STAGE26M_OUTPUT"]);script_path=os.path.abspath(os.environ.get("STAGE26M_SCRIPT",__file__));cfg=load_json(config_path);authority(cfg);bind(cfg)
 if sha256(script_path)!=cfg["sources"]["runner_sha256"] or str(config.version)!=str(cfg["sources"]["expected_yade_version"]):raise RuntimeError("runner/version mismatch")
 if os.path.exists(output):raise RuntimeError("immutable Stage26m output exists")
 os.makedirs(output);O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]));sand_ids=sorted(int(b.id) for b in O.bodies if b is not None and isinstance(b.shape,Sphere) and not b.isClumpMember)
 if len(sand_ids)!=int(cfg["sand"]["particle_count"]):raise RuntimeError("sand count mismatch")
 radii={i:float(O.bodies[i].shape.radius) for i in sand_ids};sand_solid=solid_volume(sand_ids);old=diagonal_lengths();oldvol=float(O.cell.volume);desired=sand_solid*(1+float(cfg["preparation"]["initial_sand_skeleton_void_ratio"]));scale=(desired/oldvol)**(1/3.0);frac={i:[float(O.bodies[i].state.pos[k])/old[k] for k in range(3)] for i in sand_ids};new=[v*scale for v in old];O.cell.hSize=Matrix3(new[0],0,0,0,new[1],0,0,0,new[2])
 for i in sand_ids:O.bodies[i].state.pos=Vector3(*[frac[i][k]*new[k] for k in range(3)])
 zero_motion(sand_ids);O.step();placement=load_json(windows_to_wsl(cfg["sources"]["placement"]));mat=O.materials.append(FrictMat(young=float(cfg["fibre"]["young_pa"]),poisson=float(cfg["fibre"]["poisson"]),frictionAngle=math.atan(float(cfg["fibre"]["friction_coefficient"])),density=float(cfg["fibre"]["density_kg_m3"]),label="stage26m_f37_plastic"));parents=[];groups=[]
 for f in placement["fibres"]:
  src=[[float(v) for v in c] for c in f["member_centres_m"]];pivot=[sum(c[k] for c in src)/len(src) for k in range(3)];np=[pivot[k]*scale for k in range(3)];centres=[[np[k]+c[k]-pivot[k] for k in range(3)] for c in src];bodies=[sphere(Vector3(*c),float(cfg["fibre"]["member_radius_m"]),material=mat,color=(.85,.12,.10)) for c in centres];pid,members=O.bodies.appendClumped(bodies,20);pid=int(pid);members=[int(v) for v in members];parent=O.bodies[pid];factor=float(cfg["fibre"]["target_mass_kg"])/float(parent.state.mass);parent.state.mass=float(cfg["fibre"]["target_mass_kg"]);parent.state.inertia=Vector3(*[float(v)*factor for v in parent.state.inertia]);parent.state.blockedDOFs="xyzXYZ";parents.append(pid);groups.append(members)
 zero_motion(sand_ids+parents);O.step();triax=next(e for e in O.engines if isinstance(e,PeriTriaxController));target=float(cfg["preparation"]["target_mean_effective_stress_pa"]);triax.dead=False;triax.goal=tuple(-target for _ in range(3));triax.maxStrainRate=tuple(float(cfg["preparation"]["maximum_strain_rate_s_inv"]) for _ in range(3));triax.relStressTol=float(cfg["acceptance"]["maximum_relative_mean_stress_error"]);triax.maxUnbalanced=float(cfg["acceptance"]["maximum_unbalanced_force"])
 for e in O.engines:
  if isinstance(e,GlobalStiffnessTimeStepper):e.timestepSafetyCoefficient=float(cfg["preparation"]["timestep_safety_coefficient"])
  if isinstance(e,NewtonIntegrator):e.damping=float(cfg["preparation"]["newton_damping"]);e.gravity=Vector3(*cfg["preparation"]["gravity_m_s2"])
 initial={"cell_volume_m3":float(O.cell.volume),"sand_fractional":{str(i):[float(O.bodies[i].state.pos[k])/new[k] for k in range(3)] for i in sand_ids},"checkpoint_velocities_reset":True};supports=[[] for _ in groups];history=[];proto=cfg["release_protocol"];release_row=None
 for block in range(1,int(proto["fixed_phase_maximum_blocks"])+1):
  O.run(int(proto["steps_per_block"]),True);zero_motion(parents);row=enrich(diagnostic(block,cfg,triax,sand_ids,groups,supports,initial),cfg,sand_solid);row["phase"]="fixed_initialization_until_network_onset";row.update({"fibre_translation_m_by_fibre":[0.0,0.0],"fibre_translation_over_D50_by_fibre":[0.0,0.0],"fibre_rotation_deg_by_fibre":[0.0,0.0],"maximum_fibre_translation_over_D50":0.0,"maximum_fibre_rotation_deg":0.0});history.append(row)
  if block==1 or block%20==0:print("STAGE26M_FIXED="+json.dumps({"block":block,"void_ratio":row["sand_skeleton_void_ratio"],"stress_pa":row["mean_effective_stress_pa_compression_positive"],"sand_contacts":row["sand_sand_real_contact_count"],"fibre_contacts":row["distinct_sand_contacts_by_fibre"]},sort_keys=True),flush=True)
  if row["sand_sand_real_contact_count"]>=int(proto["minimum_sand_contact_count"]) and row["mean_effective_stress_pa_compression_positive"]>=float(proto["minimum_mean_effective_stress_pa"]):release_row=row;break
 if release_row is None:status="release_trigger_not_reached";qualified=False;checks=None;streak=0
 else:
  lengths=diagonal_lengths();poses=[{"fractional_position":[float(O.bodies[i].state.pos[k])/lengths[k] for k in range(3)],"orientation":quat(O.bodies[i])} for i in parents]
  for i in parents:O.bodies[i].state.blockedDOFs=""
  zero_motion(parents)
  for e in O.engines:
   if isinstance(e,NewtonIntegrator):e.damping=float(proto["mobile_newton_damping"])
  status="mobile_phase_resource_ceiling";qualified=False;checks=None;streak=0;release_block=int(release_row["block"])
  for local in range(1,int(proto["mobile_phase_maximum_blocks"])+1):
   O.run(int(proto["steps_per_block"]),True)
   if any(abs(float(O.bodies[i].shape.radius)-radii[i])>1e-15 for i in sand_ids):raise RuntimeError("sand radius changed")
   block=release_block+local;row=enrich(diagnostic(block,cfg,triax,sand_ids,groups,supports,initial),cfg,sand_solid);row.update(motion(parents,poses,float(cfg["sand"]["D50_m"])));row["phase"]="mobile_after_network_onset";history.append(row);checks=gates(row,cfg)
   if not checks["finite_state"] or not checks["bounded_translation"] or row["maximum_interobject_penetration_over_smaller_radius"]>.05:status="mobile_guard_failed";break
   eligible=local>=int(proto["mobile_phase_minimum_blocks"]);streak=streak+1 if eligible and all(checks.values()) else 0
   if local==1 or local%10==0 or streak>0:print("STAGE26M_MOBILE="+json.dumps({"block":block,"mobile_block":local,"stress_pa":row["mean_effective_stress_pa_compression_positive"],"sand_contacts":row["sand_sand_real_contact_count"],"fibre_contacts":row["distinct_sand_contacts_by_fibre"],"translation_D50":row["maximum_fibre_translation_over_D50"],"rotation_deg":row["maximum_fibre_rotation_deg"],"unbalanced":row["unbalanced_force"],"streak":streak},sort_keys=True),flush=True)
   if streak>=int(proto["required_consecutive_pass_blocks"]):qualified=True;status="staged_release_mobile_equilibrium_qualified";break
 hp=os.path.join(output,"staged_release_history.csv");write_history(hp,history);state_digest=None
 if qualified:
  sp=os.path.join(output,"qualified_staged_release_mobile_state.yade.gz");O.tags["stage26m_metadata_json"]=json.dumps({"schema":"lbs.stage26m-qualified-state-metadata.v1","config_sha256":sha256(config_path),"release_block":release_row["block"],"final_streak":streak},sort_keys=True,separators=(",",":"));O.save(sp);state_digest=sha256(sp)
 result={"schema":"lbs.stage26m-staged-release-pilot-result.v1","passed":True,"status":status,"qualified":qualified,"trial":cfg["trial"],"release_trigger_row":release_row,"terminal":history[-1],"terminal_checks":checks,"consecutive_pass_blocks":streak,"blocks_executed":len(history),"exact_sand_radii_unchanged":True,"exact_fibre_geometry_unchanged":True,"artifacts":{"history_sha256":sha256(hp),"state_sha256":state_digest},"source_hashes":{"config":sha256(config_path),"runner":sha256(script_path),"placement":cfg["sources"]["placement_sha256"],"stage25_checkpoint":cfg["sources"]["stage25_checkpoint_sha256"]},"claim_boundary":cfg["claim_boundary"]};rp=os.path.join(output,"result.json");write_json_exclusive(rp,result);completion={"schema":"lbs.stage26m-staged-release-pilot-completion.v1","passed":True,"status":status,"qualified":qualified,"result_sha256":sha256(rp),"state_sha256":state_digest,"timestamp_utc":datetime.now(timezone.utc).isoformat(),"wall_seconds":time.time()-START,"authority":{"heldout_execution_authorized":False,"reserve_execution_authorized":False,"flow_execution_authorized":False,"deformation_authorized":False},"claim_boundary":cfg["claim_boundary"]};cp=os.path.join(output,"completion.json");write_json_exclusive(cp,completion);print("STAGE26M_COMPLETION_SHA256="+sha256(cp),flush=True)
if __name__=="__main__":main()
