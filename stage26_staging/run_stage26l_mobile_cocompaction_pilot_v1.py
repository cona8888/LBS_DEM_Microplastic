"""Stage26l bounded-mobile exact-fibre loose-state co-compaction pilot."""

from __future__ import print_function
import json, math, os, sys, time
from datetime import datetime, timezone

HERE=os.path.dirname(os.path.abspath(os.environ.get("STAGE26L_SCRIPT",__file__)))
if HERE not in sys.path:sys.path.insert(0,HERE)
from yade import config
from stage26b_revision2_prefilter_common_v1 import load_json,sha256,windows_to_wsl,write_json_exclusive
from stage26h_common_v1 import diagnostic,diagonal_lengths,write_history,zero_motion
from run_stage26k_loose_cocompaction_pilot_v1 import solid_volume,enrich,gate as base_gate

START=time.time()


def authority(cfg):
    if cfg.get("status")!="authorized_stage26l_spent_development_mobile_cocompaction_pilot":raise RuntimeError("configuration is not Stage26l-authorized")
    auth=cfg["authority"]
    if auth.get("mobile_cocompaction_authorized") is not True:raise RuntimeError("mobile co-compaction authority is false")
    if any(auth.get(k,False) for k in ("free_release_authorized","heldout_execution_authorized","reserve_execution_authorized","flow_execution_authorized","deformation_authorized","production_parametric_study_authorized")):raise RuntimeError("Stage26l authority exceeded")


def bind(cfg):
    for k,v in cfg["sources"].items():
        if k.endswith("_sha256") or k=="expected_yade_version":continue
        expected=cfg["sources"].get(k+"_sha256")
        if expected is not None and sha256(windows_to_wsl(v))!=expected:raise RuntimeError("source hash mismatch: "+k)


def quat(body):return tuple(float(body.state.ori[i]) for i in range(4))


def motion(parent_ids,initial_pose,d50):
    lengths=diagonal_lengths();translations=[];rotations=[]
    for i,parent_id in enumerate(parent_ids):
        body=O.bodies[parent_id]
        frac=[float(body.state.pos[k])/lengths[k] for k in range(3)]
        delta=[frac[k]-initial_pose[i]["fractional_position"][k] for k in range(3)]
        delta=[value-round(value) for value in delta]
        translations.append(math.sqrt(sum((delta[k]*lengths[k])**2 for k in range(3))))
        q=quat(body);q0=initial_pose[i]["orientation"];dot=abs(sum(q[k]*q0[k] for k in range(4)));dot=max(-1.0,min(1.0,dot))
        rotations.append(math.degrees(2.0*math.acos(dot)))
    return {"fibre_translation_m_by_fibre":translations,"fibre_translation_over_D50_by_fibre":[v/d50 for v in translations],"fibre_rotation_deg_by_fibre":rotations,"maximum_fibre_translation_over_D50":max(translations)/d50,"maximum_fibre_rotation_deg":max(rotations)}


def mobile_gate(row,cfg):
    checks=base_gate(row,cfg);g=cfg["motion_guards"]
    checks["bounded_translation"]=row["maximum_fibre_translation_over_D50"]<=g["maximum_nonaffine_translation_over_D50"]
    checks["bounded_rotation"]=row["maximum_fibre_rotation_deg"]<=g["maximum_rotation_deg"]
    return checks


def main():
    config_path=os.path.abspath(os.environ["STAGE26L_CONFIG"]);output=os.path.abspath(os.environ["STAGE26L_OUTPUT"]);script_path=os.path.abspath(os.environ.get("STAGE26L_SCRIPT",__file__))
    cfg=load_json(config_path);authority(cfg);bind(cfg)
    if sha256(script_path)!=cfg["sources"]["runner_sha256"]:raise RuntimeError("runner hash mismatch")
    if str(config.version)!=str(cfg["sources"]["expected_yade_version"]):raise RuntimeError("unexpected YADE version")
    if os.path.exists(output):raise RuntimeError("immutable Stage26l output exists")
    os.makedirs(output);O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    sand_ids=sorted(int(b.id) for b in O.bodies if b is not None and isinstance(b.shape,Sphere) and not b.isClumpMember)
    if len(sand_ids)!=int(cfg["sand"]["particle_count"]):raise RuntimeError("sand count mismatch")
    radii={i:float(O.bodies[i].shape.radius) for i in sand_ids};sand_solid=solid_volume(sand_ids)
    old=diagonal_lengths();old_volume=float(O.cell.volume);desired=sand_solid*(1.0+float(cfg["preparation"]["initial_sand_skeleton_void_ratio"]));scale=(desired/old_volume)**(1.0/3.0)
    frac={i:[float(O.bodies[i].state.pos[k])/old[k] for k in range(3)] for i in sand_ids};new=[x*scale for x in old]
    O.cell.hSize=Matrix3(new[0],0,0,0,new[1],0,0,0,new[2])
    for i in sand_ids:O.bodies[i].state.pos=Vector3(*[frac[i][k]*new[k] for k in range(3)])
    zero_motion(sand_ids);O.step()
    placement=load_json(windows_to_wsl(cfg["sources"]["placement"]))
    mat=O.materials.append(FrictMat(young=float(cfg["fibre"]["young_pa"]),poisson=float(cfg["fibre"]["poisson"]),frictionAngle=math.atan(float(cfg["fibre"]["friction_coefficient"])),density=float(cfg["fibre"]["density_kg_m3"]),label="stage26l_f37_plastic"))
    parents=[];groups=[]
    for f in placement["fibres"]:
        source=[[float(v) for v in c] for c in f["member_centres_m"]];pivot=[sum(c[k] for c in source)/len(source) for k in range(3)];newpivot=[pivot[k]*scale for k in range(3)]
        centres=[[newpivot[k]+c[k]-pivot[k] for k in range(3)] for c in source]
        bodies=[sphere(Vector3(*c),float(cfg["fibre"]["member_radius_m"]),material=mat,color=(.85,.12,.10)) for c in centres]
        parent_id,members=O.bodies.appendClumped(bodies,20);parent_id=int(parent_id);members=[int(v) for v in members];parent=O.bodies[parent_id]
        factor=float(cfg["fibre"]["target_mass_kg"])/float(parent.state.mass);parent.state.mass=float(cfg["fibre"]["target_mass_kg"]);parent.state.inertia=Vector3(*[float(v)*factor for v in parent.state.inertia]);parent.state.blockedDOFs=""
        parents.append(parent_id);groups.append(members)
    zero_motion(sand_ids+parents);O.step()
    triax=next(e for e in O.engines if isinstance(e,PeriTriaxController));target=float(cfg["preparation"]["target_mean_effective_stress_pa"]);triax.dead=False;triax.goal=tuple(-target for _ in range(3));triax.maxStrainRate=tuple(float(cfg["preparation"]["maximum_strain_rate_s_inv"]) for _ in range(3));triax.relStressTol=float(cfg["acceptance"]["maximum_relative_mean_stress_error"]);triax.maxUnbalanced=float(cfg["acceptance"]["maximum_unbalanced_force"])
    for e in O.engines:
        if isinstance(e,GlobalStiffnessTimeStepper):e.timestepSafetyCoefficient=float(cfg["preparation"]["timestep_safety_coefficient"])
        if isinstance(e,NewtonIntegrator):e.damping=float(cfg["preparation"]["newton_damping"]);e.gravity=Vector3(*cfg["preparation"]["gravity_m_s2"])
    initial={"cell_volume_m3":float(O.cell.volume),"sand_fractional":{str(i):[float(O.bodies[i].state.pos[k])/new[k] for k in range(3)] for i in sand_ids},"checkpoint_velocities_reset":True}
    poses=[{"fractional_position":[float(O.bodies[i].state.pos[k])/new[k] for k in range(3)],"orientation":quat(O.bodies[i])} for i in parents]
    supports=[[] for _ in groups];insertion=enrich(diagnostic(0,cfg,triax,sand_ids,groups,supports,initial),cfg,sand_solid);insertion.update(motion(parents,poses,float(cfg["sand"]["D50_m"])));insertion["phase"]="loose_mobile_exact_geometry_mixture"
    if insertion["maximum_interobject_penetration_over_smaller_radius"]>.02 or insertion["fibre_fibre_real_interaction_count"] or insertion["intraclump_real_interaction_count"]:raise RuntimeError("invalid loose-state insertion")
    history=[];streak=0;qualified=False;status="resource_ceiling_without_mobile_qualification";checks=None
    for block in range(1,int(cfg["preparation"]["maximum_check_blocks"])+1):
        O.run(int(cfg["preparation"]["steps_per_check_block"]),True)
        if any(abs(float(O.bodies[i].shape.radius)-radii[i])>1e-15 for i in sand_ids):raise RuntimeError("sand radius changed")
        row=enrich(diagnostic(block,cfg,triax,sand_ids,groups,supports,initial),cfg,sand_solid);row.update(motion(parents,poses,float(cfg["sand"]["D50_m"])));row["phase"]="bounded_mobile_loose_state_cocompaction";history.append(row);checks=mobile_gate(row,cfg)
        if not checks["finite_state"] or not checks["bounded_translation"] or not checks["bounded_rotation"] or row["maximum_interobject_penetration_over_smaller_radius"]>.05:status="mobile_guard_failed";break
        eligible=block>=int(cfg["preparation"]["minimum_check_blocks"]);streak=streak+1 if eligible and all(checks.values()) else 0
        if block==1 or block%20==0 or streak>0:print("STAGE26L="+json.dumps({"block":block,"void_ratio":row["sand_skeleton_void_ratio"],"stress_pa":row["mean_effective_stress_pa_compression_positive"],"unbalanced":row["unbalanced_force"],"sand_contacts":row["sand_sand_real_contact_count"],"fibre_contacts":row["distinct_sand_contacts_by_fibre"],"translation_D50":row["maximum_fibre_translation_over_D50"],"rotation_deg":row["maximum_fibre_rotation_deg"],"streak":streak},sort_keys=True),flush=True)
        if streak>=int(cfg["preparation"]["required_consecutive_pass_blocks"]):qualified=True;status="mobile_loose_cocompaction_qualified";break
    hp=os.path.join(output,"mobile_cocompaction_history.csv");write_history(hp,history);state_digest=None
    if qualified:
        sp=os.path.join(output,"qualified_mobile_fibre_cocompacted_state.yade.gz");O.tags["stage26l_metadata_json"]=json.dumps({"schema":"lbs.stage26l-qualified-state-metadata.v1","config_sha256":sha256(config_path),"trial":cfg["trial"],"final_streak":streak},sort_keys=True,separators=(",",":"));O.save(sp);state_digest=sha256(sp)
    result={"schema":"lbs.stage26l-mobile-cocompaction-pilot-result.v1","passed":True,"status":status,"qualified":qualified,"trial":cfg["trial"],"insertion":insertion,"terminal":history[-1],"terminal_checks":checks,"consecutive_pass_blocks":streak,"blocks_executed":len(history),"exact_sand_radii_unchanged":True,"exact_fibre_geometry_unchanged":True,"artifacts":{"history_sha256":sha256(hp),"state_sha256":state_digest},"source_hashes":{"config":sha256(config_path),"runner":sha256(script_path),"placement":cfg["sources"]["placement_sha256"],"stage25_checkpoint":cfg["sources"]["stage25_checkpoint_sha256"]},"claim_boundary":cfg["claim_boundary"]}
    rp=os.path.join(output,"result.json");write_json_exclusive(rp,result)
    completion={"schema":"lbs.stage26l-mobile-cocompaction-pilot-completion.v1","passed":True,"status":status,"qualified":qualified,"result_sha256":sha256(rp),"state_sha256":state_digest,"timestamp_utc":datetime.now(timezone.utc).isoformat(),"wall_seconds":time.time()-START,"authority":{"free_release_authorized":False,"heldout_execution_authorized":False,"reserve_execution_authorized":False,"flow_execution_authorized":False,"deformation_authorized":False},"claim_boundary":cfg["claim_boundary"]}
    cp=os.path.join(output,"completion.json");write_json_exclusive(cp,completion);print("STAGE26L_COMPLETION_SHA256="+sha256(cp),flush=True)


if __name__=="__main__":main()
