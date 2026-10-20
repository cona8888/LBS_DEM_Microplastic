"""Refine selected one-grain MFS references without modifying prior evidence."""
import argparse, hashlib, json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage37_staging'))
import local_stokes_challenge as challenge

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def case_table():
    cases = []
    for scale in (1.0, 0.25):
        for shape in ('sphere', 'prolate'):
            a = 0.0002 / 0.000385 * scale
            b = 0.00005 / 0.000385 * scale
            axes = np.full(3, (a*b*b)**(1/3)) if shape == 'sphere' else np.array([a,b,b])
            for gap in (0.5, 0.2, 0.08):
                cases.append((scale, shape, axes, gap, np.array([0.0, 1.0+axes[1]+gap, 0.0])))
    return cases

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--ids', default='1,2,3,4,5,8,11')
    ap.add_argument('--count', type=int, default=768)
    args = ap.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    parent_path = ROOT/'stage37_evaluations/local_reference_01/results.json'
    parent = json.loads(parent_path.read_text())
    ids = [int(x) for x in args.ids.split(',')]
    rows = []
    for index in ids:
        scale,shape,axes,gap,centre = case_table()[index]
        start = time.perf_counter()
        motion,health = challenge.reference(centre,np.eye(3),axes,args.count)
        old = parent['rows'][index]
        row = {
            'id': index, 'shape': shape, 'scale': scale, 'axes': axes.tolist(),
            'gap_grain_radii': gap, 'reference': motion.tolist(), 'health': health,
            'previous_reference': old['reference'],
            'reference_change_relative': float(np.linalg.norm(motion-np.array(old['reference']))/max(np.linalg.norm(motion),0.01)),
            'reference_passed': bool(health['boundary_error'] <= 0.001 and health['force_torque_residual'] <= 1e-8),
            'seconds': time.perf_counter()-start,
        }
        rows.append(row); (out/f'case_{index:02}.json').write_text(json.dumps(row,indent=2)); print(json.dumps(row),flush=True)
    result = {
        'completed': True, 'all_references_passed': all(r['reference_passed'] for r in rows),
        'count': args.count, 'rows': rows,
        'parent': {'path': str(parent_path), 'sha256': sha(parent_path)},
        'hashes': {str(p.resolve()): sha(p) for p in (Path(__file__),Path(challenge.__file__))},
        'interpretation': 'Reference refinement only; does not validate matrix contact transport.'
    }
    (out/'results.json').write_text(json.dumps(result,indent=2)); print(json.dumps({'completed':True,'all_references_passed':result['all_references_passed']}))

if __name__ == '__main__': main()
