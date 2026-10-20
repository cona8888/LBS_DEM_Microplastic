"""Assemble the completed review evidence without modifying historical results."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REVIEW = Path(__file__).resolve().parents[1]
NAMES = (
    'contact_primitives_01', 'pgs_prefix_optional_01', 'wall_field_exact_01',
    'wall_field_trajectory_01', 'events_04', 'independent_event_review_01',
    'smoke_recovery_01', 'smoke_prefix_01', 'crossing_prefix_01',
    'saved_continuation_01', 'saved_prefix_refinement_01',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = []
    current_hashes = {}
    for name in NAMES:
        directory = REVIEW / 'evidence' / name
        path = directory / 'results.json'
        item = {'name': name, 'results_present': path.is_file()}
        if path.is_file():
            result = json.loads(path.read_text())
            item.update(results_sha256=sha(path), passed=result.get('passed'),
                        checks=result.get('checks'), keys=sorted(result))
            checked = 0
            mismatches = []
            for field, mapping in result.items():
                if 'hash' not in field or not isinstance(mapping, dict):
                    continue
                for filename, expected in mapping.items():
                    target = Path(filename)
                    if not (target.is_absolute() and isinstance(expected, str)
                            and len(expected) == 64):
                        continue
                    checked += 1
                    if filename not in current_hashes:
                        current_hashes[filename] = sha(target) if target.is_file() else None
                    if current_hashes[filename] != expected:
                        mismatches.append({'field': field, 'path': filename})
            item['recorded_hash_audit'] = {'checked': checked,
                                           'mismatches': mismatches,
                                           'passed': not mismatches}
        item['artifacts'] = {
            str(p.relative_to(REVIEW)): sha(p)
            for p in sorted(directory.rglob('*')) if p.is_file()
        }
        inventory.append(item)
    payload = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'decision': 'exact field optimization and corrected event/applicability path verified in bounded tests; analytic contact candidates unpromoted',
        'evidence': inventory,
        'recorded_hash_audit_passed': all(e.get('recorded_hash_audit', {}).get('passed', False)
                                          for e in inventory),
        'review_source_hashes': {
            str(p.relative_to(REVIEW)): sha(p)
            for p in sorted((REVIEW / 'src').glob('*.py'))
        },
        'superseded': {
            'events_01': 'initial event implementation failed; retained development evidence',
            'events_02': 'JSON serialization failed; no completed accepted result',
            'events_03': 'outlet-specific check exercised endpoint branch; use events_04',
            'smoke_01': 'event source changed afterward; use smoke_recovery_01 and smoke_prefix_01',
        },
        'scope': 'numerical implementation review; no physical or population validation',
    }
    output = REVIEW / 'evidence' / 'REVIEW_MANIFEST.json'
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(payload, indent=2))
    print(json.dumps([{'name': e['name'], 'present': e['results_present'],
                      'passed': e.get('passed')} for e in inventory], indent=2))


if __name__ == '__main__':
    main()
