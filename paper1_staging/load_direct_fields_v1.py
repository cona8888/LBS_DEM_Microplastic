"""Read-only CPD6 Paper1 fields; no normalization or transport authority.

The reference loader is reused. Newly solved flows require independently
evaluated field records AND the post-retirement source/input admission receipt.
"""
from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage132_staging'),str(ROOT/'stage39_staging')]
import load_cpd6_stationary_field_v1 as reference
import wall_field_v1
REGISTRY=ROOT/'paper1_designs/mechanism_feasibility_20261013/field_registry_01/results.json'
REFERENCE_PINS={str(reference.GEOMETRY):'65c0f56a4f4b1434bb96b985565cedf3f270970c480fa7cfa968b79282714d2a',
    str(reference.FIELD):'8cba5eb9857a09ba7c09bd3963db0d97855ccbdd037ea636dcca8e7961c62cad',
    str(reference.EVALUATION):'1395d28023f7157c6ed19d5178d8e638999a2ed1cdf2b7c8f2af650d78cdfc40',
    str(reference.COMPLETION):'f8f31f8bcdda1db500f43b7e601b5c7d337e31cabd1ef393689ae170884b6ace',
    str(Path(reference.__file__).resolve()):'cf8aaad3d65f33e7cc2c2c00b5fb407b21b4dc4068218437398a449a2382464f',
    str(Path(wall_field_v1.__file__).resolve()):'85e08f99dfd49e1a53edac222d252ba776d954451af24e2ff9525c52df57b1ca'}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read(path):
    with Path(path).open(encoding='utf-8') as f:return json.load(f)

def require(value,message):
    if not value:raise RuntimeError(message)

def sealed(path):
    p=Path(path);r=read(p);require(read(p.with_name('completion.json'))['results_sha256']==sha(p),'Unsealed field evidence');return r

def load(seed=2,flow_factor=1.,cpd=6):
    require(seed==2 and cpd==6 and flow_factor in (.5,1.,2.),'Outside prospective same-packing CPD6 three-flow domain')
    for path,digest in REFERENCE_PINS.items():require(sha(path)==digest,'Qualified reference field/source changed: '+path)
    if flow_factor==1.:
        field,geometry,meta=reference.load()
        meta={**meta,'flow_factor':1.,'paper1_loader':dict(path=str(Path(__file__).resolve()),sha256=sha(__file__))}
        return field,geometry,meta
    registry=sealed(REGISTRY)
    study=Path(registry['study_path']);design=Path(registry['design_path'])
    require(registry['passed'] and registry['design_sha256']==sha(design),'Qualified field registry/design absent')
    admission=sealed(study/'retirement_01/results.json')
    require(admission['passed'] and admission['all_exact_owned_identities_retired'] and admission['source_and_inputs_reauthenticated'],'Direct fields not yet retired/admitted')
    require(admission['design_sha256']==sha(design) and registry['retirement_sha256']==sha(study/'retirement_01/results.json'),'Admitted field design/retirement changed')
    d=read(design)
    require(d['geometry']['sha256']==REFERENCE_PINS[str(reference.GEOMETRY)] and d['controls']['tau']==.8 and d['controls']['nu_lu']==.1,'Same physical packing and viscosity/collision convention')
    for mapping in (d['source_files'],d['inputs']):
        for path,digest in mapping.items():require(sha(path)==digest,'Mandatory field source/input changed: '+path)
    case=next(x for x in d['cases'] if x['flow_factor']==flow_factor)
    folder=study/(case['id']+'_solve');result_path=folder/'independent_evaluation_01/results.json'
    r=sealed(result_path)
    require(r['passed'] and all(r['checks'].values()) and r['case']==case and r['design_sha256']==sha(design),'Original direct-field scientific gate absent')
    for path,digest in r['artifacts'].items():require(sha(path)==digest,'Direct field artifact changed: '+path)
    with np.load(d['geometry']['path']) as g,np.load(folder/'final_fields.npz') as f:
        geometry={k:g[k].copy() for k in g.files}
        require(np.array_equal(f['phase'],geometry['phase']),'Direct field phase drift')
        fluid=(geometry['phase']==0).transpose(2,1,0)
        velocity=f['velocity_xyz_lu'].astype(np.float64).transpose(0,3,2,1)
    dx=float(geometry['spacing_m'][0]);unit=(.001002/998.2)/(.1*dx);velocity*=unit
    mean=float(velocity[0,fluid].mean());length=float(geometry['cell_length_m'][0])
    require(np.isfinite(velocity).all() and np.all(velocity[:,~fluid]==0),'Nonphysical direct field values')
    require(abs(mean/r['mean_interstitial_velocity_m_s']-1)<2e-6,'Independent SI reconstruction drift')
    metadata=dict(case_id=case['id'],cpd=6,flow_factor=flow_factor,achieved_mean_interstitial_velocity_m_s=mean,
        target_mean_interstitial_velocity_m_s=case['target_mean_velocity_m_s'],speed_unit_m_s=unit,cell_length_m=length,
        pv_per_second=mean/length,two_pore_volume_horizon_s=2*length/mean,
        geometry=d['geometry'],field=dict(path=str(folder/'final_fields.npz'),sha256=sha(folder/'final_fields.npz')),
        evaluation=dict(path=str(result_path),sha256=sha(result_path)),completion=dict(path=str(result_path.with_name('completion.json')),sha256=sha(result_path.with_name('completion.json'))),
        admission=dict(path=str(study/'retirement_01/results.json'),sha256=sha(study/'retirement_01/results.json')),
        registry=dict(path=str(REGISTRY),sha256=sha(REGISTRY)),
        loader=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),interpolator=dict(path=str(Path(wall_field_v1.__file__).resolve()),sha256=sha(wall_field_v1.__file__)),
        normalization_to_target_applied=False,particle_transport_authorized=False,limitation='Stationary direct-field qualification only; particle transport and spatial response require separate frozen admission.')
    return wall_field_v1.WallCellField(velocity,dx,fluid),geometry,metadata
