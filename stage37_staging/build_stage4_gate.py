"""Read-only evidence audit; writes a new manifest, never launches a simulation."""
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    evidence = {}
    bindings = []
    for name, relative in {
        'primitives': 'stage37_evaluations/primitives_02/results.json',
        'trajectories': 'stage37_evaluations/trajectories_01/results.json',
        'applicability': 'stage37_evaluations/applicability_02/results.json',
        'local_reference': 'stage37_evaluations/local_reference_01/results.json',
    }.items():
        path = ROOT / relative
        doc = json.loads(path.read_text())
        evidence[name] = {'path': str(path), 'sha256': sha(path), 'passed': doc.get('passed') is True}
        for filename, expected in doc.get('hashes', {}).items():
            source = Path(filename)
            actual = sha(source) if source.is_file() else None
            bindings.append({'path': filename, 'expected': expected, 'actual': actual, 'passed': actual == expected})
    inputs = []
    for seed in (1, 2, 3):
        case = f's31b_n216_s{seed}_clean'
        paths = [ROOT / 'stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01' / case / 'geometry_cpd2.npz']
        base = ROOT / 'stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01' / f'stage31e_{case}_cpd2'
        paths += [base / 'record.json', base / 'final_fields.npz']
        for path in paths:
            inputs.append({'packing': seed, 'path': str(path), 'exists': path.is_file(), 'sha256': sha(path) if path.is_file() else None})
    eligible = all(v['passed'] for v in evidence.values()) and all(v['passed'] for v in bindings) and all(v['exists'] for v in inputs)
    result = {
        'stage4_execution_authorized_by_physical_gates': eligible,
        'stage4_executed': False,
        'status': 'needs_additional_qualification' if not eligible else 'requires_full_campaign_preflight',
        'evidence': evidence, 'source_bindings': bindings, 'input_inventory': inputs,
        'inventory_is_not_full_archived_lineage_audit': True,
        'remaining': [
            'Qualify finite-Re/inertial treatment for baseline PET, or explicitly adopt a smaller physical domain.',
            'Converge independent near-grain references and qualify contact/lubrication resistance in representative multi-grain poses.',
            'Qualify frozen-flow feedback and actual outlet boundary conditions.',
            'Test curved-contact rotating trajectories and representative three-level timestep convergence.',
            'Freeze weighted resident starts, sampling estimand, field scaling, finite horizon and unresolved outcomes.',
            'Profile 16 trajectories before the 384-trajectory replicated pilot; no empirical validation claim.'
        ],
        'observable_warning': 'Periodic observation-window passage is not physical column effluent release.',
        'script_sha256': sha(Path(__file__)),
    }
    (output / 'gate.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'eligible': eligible, 'bindings_checked': len(bindings), 'bindings_passed': all(v['passed'] for v in bindings), 'input_files': len(inputs), 'stage4_executed': False}))

if __name__ == '__main__':
    main()
