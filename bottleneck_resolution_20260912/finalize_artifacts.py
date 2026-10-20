"""Bind the finished report to its evidence without running any simulation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

package = Path(__file__).resolve().parent
workspace = package.parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

documents = [package/name for name in (
    'REPORT.md', 'README.md', 'RESEARCH_CONTRACT.md', 'CYCLE_GUARD_PROOF.md', 'NEXT_PLAN.md')]
documents.append(workspace/'CURRENT_PLAN.md')
broken = []
for document in documents:
    for target in re.findall(r'\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):
            continue
        target = target.split('#', 1)[0]
        if not (document.parent/target).exists():
            broken.append({'document':str(document), 'target':target})
if broken:
    raise RuntimeError(f'Broken artifact links: {broken}')

results = [package/'evidence'/name/'results.json' for name in (
    'local_blas_ab_01', 'crossing_blas_01', 'crossing_cycle_01', 'refinement_cycle_01',
    'compiled_numpy_blas_final_01', 'compiled_numpy_blas_final_guard_01',
    'blas_stage53_primitives_01', 'cycle_guard_01', 'cycle_period3_01')]
audits = [package/'evidence'/name/file for name,file in (
    ('local_blas_independent_audit_01','audit.json'),
    ('crossing_cycle_diagnosis_01','audit.json'),
    ('crossing_cycle_prefix_audit_01','audit.json'),
    ('final_qualification_audit_01','audit.json'),
    ('final_qualification_audit_01','guard_source_audit.json'),
    ('final_qualification_audit_01','memoization_screen.json'),
    ('refinement_blas_01','interruption.json'))]
crossing = json.loads((package/'evidence/crossing_cycle_01/results.json').read_text())
refinement = json.loads((package/'evidence/refinement_cycle_01/results.json').read_text())
source_bindings = {}
input_bindings = {}
for result in (crossing, refinement):
    for key, value in result['source_hashes'].items():
        assert source_bindings.get(key, value) == value
        source_bindings[key] = value
    input_bindings.update(result['input_hashes'])
for path, digest in {**source_bindings, **input_bindings}.items():
    assert sha(path) == digest, path
assert sha(crossing['numpy_blas']['path']) == crossing['numpy_blas']['sha256']

artifacts = documents + results + audits + [Path(__file__), package/'requirements-compiler.txt']
payload = {
    'status':'optimization_delivered_crossing_passed_refinement_not_fully_qualified',
    'created_utc':datetime.now(timezone.utc).isoformat(),
    'crossing_passed':crossing['passed'],
    'refinement_passed':refinement['passed'],
    'refinement_completed_cases':sum(row['result']['status']=='present_at_horizon'
                                     for row in refinement['rows']),
    'refinement_total_cases':len(refinement['rows']),
    'artifact_hashes':{str(path):sha(path) for path in artifacts},
    'qualified_source_hashes':source_bindings,
    'qualified_input_hashes':input_bindings,
    'environment':crossing['environment'],
    'numpy_blas':crossing['numpy_blas'],
    'checks':{'document_links_exist':True,'qualified_sources_match':True,
              'qualified_inputs_match':True,'qualified_blas_matches':True},
    'scope':'Numerical implementation and bounded qualification; no new physical validation.'}
destination = package/'FINAL_MANIFEST.json'
with destination.open('x', encoding='utf-8') as handle:
    json.dump(payload, handle, indent=2)
print(json.dumps({'checks':payload['checks'], 'sources':len(source_bindings),
                  'inputs':len(input_bindings),'artifacts':len(artifacts),
                  'refinement_completed':payload['refinement_completed_cases']}))
