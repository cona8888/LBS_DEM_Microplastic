"""Manufactured static-state extraction; no fluid time steps or engine imports."""
import argparse
import io
import json
import math
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from body_link_extractor_v1 import extract, C, OPP, W
from verify_stage36d_wrench_transfer_v1 import AccountingTests, GeometryTests, WrenchTests, check_parent, sha, ROOT, EXTERNAL
from wrench_transfer_v1 import AttachmentMap, wrench

STAGING = ROOT/'stage36_staging'
PARENT = ROOT/'stage36_evaluations/stage36d_wrench_transfer_20260906/verification_01/verification.json'
CASE = 'sphere_D16_L4_c000_f1p0'


def scalar_reference(g, phase, owners, anchors):
    """Independent solid-centred traversal, scalar wrapping and full populations."""
    nz, ny, nx = phase.shape
    lengths = (nx, ny, nz)
    identities, force_terms, torque_terms = [], {}, {}
    for z, y, x in zip(*np.nonzero(phase)):
        owner = int(owners[z,y,x])
        for q, direction in enumerate(C.tolist()[1:], start=1):
            dx, dy, dz = direction
            dest = ((int(x)+dx)%nx, (int(y)+dy)%ny, (int(z)+dz)%nz)
            a, b, d = dest
            if phase[d,b,a] != 0:
                continue
            population = float(g[int(OPP[q]),d,b,a])+float(W[int(OPP[q])])
            force = [-2*population*v for v in direction]
            arm = []
            for coordinate, velocity, anchor, length in zip((x,y,z), direction, anchors[owner], lengths):
                r = float(coordinate)+.5+.5*velocity-float(anchor)
                arm.append(r-length*math.floor(r/length+.5))
            rx, ry, rz = arm
            fx, fy, fz = force
            torque = [ry*fz-rz*fy, rz*fx-rx*fz, rx*fy-ry*fx]
            force_terms.setdefault(owner, []).append(force)
            torque_terms.setdefault(owner, []).append(torque)
            identities.append((q, *dest, int(x), int(y), int(z), owner))
    reduced = {}
    for owner in anchors:
        reduced[owner] = [np.array([math.fsum(row[j] for row in terms.get(owner, [])) for j in range(3)])
                          for terms in (force_terms, torque_terms)]
    return sorted(identities), reduced


def identities(links):
    return sorted((int(q), *map(int,d), *map(int,s), int(o)) for q,d,s,o in
                  zip(links['q'],links['destination'],links['source'],links['owner']))


def compare(g, phase, owners, anchors):
    links, bodies = extract(g, phase, owners, anchors)
    ids, expected = scalar_reference(g, phase, owners, anchors)
    if identities(links) != ids:
        raise AssertionError('independent link identities differ')
    errors = []
    for owner, row in bodies.items():
        which = links['owner'] == owner
        full = links['shifted_force'][which]+links['baseline_force'][which]
        arm = links['midpoint'][which]-anchors[owner]
        fs = max(1., float(np.abs(full).sum()))
        ts = max(1., float(np.abs(np.cross(arm,full)).sum()))
        errors.extend([float(np.max(np.abs(row['force_lu']-expected[owner][0])))/fs,
                       float(np.max(np.abs(row['torque_lu']-expected[owner][1])))/ts])
    if max(errors) > 1e-12:
        raise AssertionError('independent extraction discrepancy')
    return links, bodies, max(errors)


def small(two=False):
    phase = np.zeros((8,8,8), dtype=np.uint8)
    owner = np.zeros_like(phase, dtype=np.int32)
    phase[2,2,2], owner[2,2,2] = 2, 7
    anchors = {7: np.array([2.5,2.5,2.5])}
    if two:
        phase[5,5,5], owner[5,5,5] = 1, 11
        anchors[11] = np.array([5.5,5.5,5.5])
    return np.zeros((19,8,8,8), dtype=np.float32), phase, owner, anchors


class LinkTests(unittest.TestCase):
    def test_01_zero_reference_closed_body(self):
        g,p,o,a = small()
        links, bodies, _ = compare(g,p,o,a)
        self.assertEqual(len(links['q']),18)
        np.testing.assert_array_equal(bodies[7]['force_lu'], 0)
        np.testing.assert_array_equal(bodies[7]['torque_lu'], 0)

    def test_02_single_pulse_sign(self):
        g,p,o,a = small()
        g[2,2,2,3] = np.float32(.001)
        _, bodies, _ = compare(g,p,o,a)
        np.testing.assert_array_equal(bodies[7]['force_lu'],[-2*float(g[2,2,2,3]),0,0])

    def test_03_two_body_ownership(self):
        g,p,o,a = small(True)
        g[2,2,2,3] = np.float32(.001)
        _, bodies, _ = compare(g,p,o,a)
        self.assertEqual(set(bodies), {7,11})
        np.testing.assert_array_equal(bodies[11]['force_lu'],0)
        self.assertNotEqual(bodies[7]['force_lu'][0],0)

    def test_04_periodic_seam(self):
        g,p,o,a = small()
        g[2,2,2,3] = np.float32(.001)
        base = compare(g,p,o,a)[1]
        shifted = compare(np.roll(g,5,axis=3),np.roll(p,5,axis=2),np.roll(o,5,axis=2),{7:a[7]+[5,0,0]})[1]
        np.testing.assert_array_equal(base[7]['force_lu'], shifted[7]['force_lu'])
        np.testing.assert_array_equal(base[7]['torque_lu'], shifted[7]['torque_lu'])

    def test_05_seeded_nonuniform_reference(self):
        g,p,o,a = small(True)
        g[:] = np.random.default_rng(3605).uniform(-.001,.001,g.shape).astype(np.float32)
        g[:,p!=0] = 0
        compare(g,p,o,a)

    def test_06_global_origin_and_nodal_transfer(self):
        g,p,o,a = small()
        g[:] = np.random.default_rng(5).uniform(-.001,.001,g.shape).astype(np.float32)
        g[:,p!=0] = 0
        links,bodies,_ = compare(g,p,o,a)
        # Arbitrary algebraic length/force scales, NOT a physical fluid calibration.
        dx, fs = 1e-6, 1e-9
        positions = links['midpoint']*dx
        nodes = np.array([a[7]+[-1,0,0],a[7]+[1,0,0]])*dx
        m = AttachmentMap(nodes,positions,np.tile([0,1],(len(positions),1)),np.full(len(positions),.5),accepts_nodal_couples=True)
        load = (links['shifted_force']+links['baseline_force'])*fs
        result = m.transfer(load,np.zeros_like(load))
        force, torque = wrench(nodes,result.forces_N,result.couples_Nm,[0,0,0])
        expected_t = (bodies[7]['torque_lu']+np.cross(a[7],bodies[7]['force_lu']))*dx*fs
        self.assertLessEqual(np.max(np.abs(force-bodies[7]['force_lu']*fs))/fs,1e-12)
        self.assertLessEqual(np.max(np.abs(torque-expected_t))/(fs*dx),1e-12)

    def test_07_reversal(self):
        g,p,o,a = small()
        g[2,2,2,3] = .001
        plus, minus = compare(g,p,o,a)[1],compare(-g,p,o,a)[1]
        np.testing.assert_array_equal(plus[7]['force_lu'],-minus[7]['force_lu'])

    def test_08_invalid_owner(self):
        g,p,o,a = small()
        for mutated in [np.zeros_like(o),np.ones_like(o),o.astype(float)]:
            with self.assertRaises(ValueError): extract(g,p,mutated,a)
        with self.assertRaises(ValueError): extract(g,p,o,{9:a[7]})

    def test_09_invalid_states(self):
        g,p,o,a = small()
        for value in [float('nan'),float('inf'),-1.]:
            bad = g.copy(); bad[1,0,0,0]=value
            with self.assertRaises(ValueError): extract(bad,p,o,a)
        bad=g.copy();bad[1,p!=0]=.001
        with self.assertRaises(ValueError): extract(bad,p,o,a)
        with self.assertRaises(ValueError): extract(g.astype(float),p,o,a)

    def test_10_invalid_boundary_phase_resource(self):
        g,p,o,a = small()
        with self.assertRaises(ValueError): extract(g,p,o,a,boundary='open')
        bad=p.copy();bad[2,2,2]=3
        with self.assertRaises(ValueError): extract(g,bad,o,a)
        with self.assertRaises(ValueError): extract(g,np.zeros((65,65,65),np.uint8),o,a)

    def test_11_ambiguous_periodic_anchor(self):
        g,p,o,a = small()
        with self.assertRaises(ValueError): extract(g,p,o,{7:np.array([6.,2.5,2.5])})

    def test_12_direction_opposite_consistency(self):
        np.testing.assert_array_equal(C[OPP],-C)
        np.testing.assert_array_equal(W[OPP],W)
        self.assertEqual(len(set(map(tuple,C))),19)


def archive():
    cfg_path = ROOT/'stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/resolved_config.json'
    cfg=json.loads(cfg_path.read_text())
    bindings={str(cfg_path):sha(cfg_path)}
    for key in ['stage13_execution_manifest','stage13_qualification','stage13_runner','cuda_source']:
        entry=cfg['lineage'][key]
        if sha(entry['path']) != entry['sha256']: raise ValueError('frozen lineage mismatch '+key)
        bindings[entry['path']]=entry['sha256']
    manifest_path=Path(cfg['lineage']['stage13_execution_manifest']['path'])
    manifest=json.loads(manifest_path.read_text())
    qual=json.loads(Path(cfg['lineage']['stage13_qualification']['path']).read_text())
    if manifest['status']!='evidence_complete' or qual['passed'] is not True: raise ValueError('unaccepted archive')
    entry=manifest['artifacts'][CASE]
    for key in ['record','mask','audit_csv','audit_npz']:
        p=manifest_path.parent/entry[key+'_path']
        if sha(p)!=entry[key+'_sha256']: raise ValueError('case artifact mismatch '+key)
        bindings[str(p)]=entry[key+'_sha256']
    record=json.loads((manifest_path.parent/entry['record_path']).read_text())
    if record['status']!='complete' or record['dimensions_lu']!=[64,64,64]: raise ValueError('case shape/status')
    phase=np.fromfile(manifest_path.parent/entry['mask_path'],dtype=np.uint8).reshape(64,64,64)
    owners=(phase!=0).astype(np.int32)
    anchors={1:np.array([32.,32.,32.])}
    return phase,owners,anchors,bindings,record


def encode(value):
    if isinstance(value,np.ndarray): return value.tolist()
    if isinstance(value,np.generic): return value.item()
    raise TypeError(type(value).__name__)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    parent=check_parent(PARENT)
    phase,owners,anchors,bindings,record=archive()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (AccountingTests,GeometryTests,WrenchTests,LinkTests))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    g=np.zeros((19,*phase.shape),dtype=np.float32)
    reference_links,reference_bodies,error=compare(g,phase,owners,anchors)
    count=len(reference_links['q'])
    sphere_checks={'archived_link_count':count==4704==record['metrics']['fluid_solid_link_count'],
                   'zero_reference_force':bool(np.all(reference_bodies[1]['force_lu']==0)),
                   'zero_reference_torque':bool(np.all(reference_bodies[1]['torque_lu']==0))}
    pulse_index=int(np.flatnonzero(np.all(reference_links['destination']==[24,31,31],axis=1))[0]) if np.any(np.all(reference_links['destination']==[24,31,31],axis=1)) else 0
    q=int(reference_links['q'][pulse_index]);x,y,z=reference_links['destination'][pulse_index]
    amplitude=np.float32(.001);g[OPP[q],z,y,x]=amplitude
    links,bodies,pulse_error=compare(g,phase,owners,anchors)
    expected_f=-2*float(amplitude)*C[q]
    expected_t=np.cross(links['midpoint'][pulse_index]-anchors[1],expected_f)
    sphere_checks['pulse_force']=bool(np.all(bodies[1]['force_lu']==expected_f))
    sphere_checks['pulse_torque']=bool(np.all(bodies[1]['torque_lu']==expected_t))
    np.savez_compressed(output/'manufactured_pulse_links.npz',**links)
    np.savez_compressed(output/'manufactured_pulse_state.npz',shifted_state=g,phase=phase,owners=owners)
    example={'case_id':CASE,'role':'manufactured pulse on archived static geometry, not original flow replay',
             'link_count':count,'zero_reference':reference_bodies,'pulse':bodies,'pulse_q':q,'pulse_destination_xyz':[int(x),int(y),int(z)],
             'pulse_amplitude':float(amplitude),'expected_force_lu':expected_f,'expected_torque_lu':expected_t,
             'maximum_independent_scaled_discrepancy':max(error,pulse_error),'checks':sphere_checks}
    (output/'sphere_manufactured_checks.json').write_text(json.dumps(example,default=encode,indent=2),encoding='utf-8')
    sources=[Path(__file__).resolve(),STAGING/'body_link_extractor_v1.py',STAGING/'STAGE36E_LINK_EXTRACTION_CONTRACT.md',PARENT]
    report={'passed':result.wasSuccessful() and all(sphere_checks.values()),'tests_run':result.testsRun,
            'new_extractor_tests':12,'regression_tests':61,'failures':len(result.failures),'errors':len(result.errors),
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'numpy':np.__version__,
            'command_argv':sys.argv,'cwd':str(Path.cwd()),'parent_binding_checks':parent,'archive_bindings':bindings,
            'source_hashes':{str(p):sha(p) for p in sources},'artifact_hashes':{str(p):sha(p) for p in output.iterdir()},
            'scope':'static halfway bounce link extraction from manufactured shifted FP32 states',
            'original_sphere_flow_replayed':False,'moving_boundary_verified':False,'transport_physics_verified':False,
            'physics_simulations_started':0,'soil_pilot_execution_authorized':False}
    (output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['passed','tests_run','failures','errors']},indent=2))
    print(json.dumps(example,default=encode,indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__': main()
