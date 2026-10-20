"""Create-only administrative context for one newly bounded terminal verification."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, time

ROOT = Path(__file__).resolve().parents[1]
BASE = 'sample0_fibre_terminal_20261008'
DESIGNS = ROOT/'stage230_designs'/BASE
RUN = ROOT/'stage230_runs'/BASE
OUT = ROOT/'stage230_evaluations'/BASE
AUTH = DESIGNS/'authorization_01.json'
PLAN = DESIGNS/'design_01.json'

def sha(path):
    with Path(path).open('rb') as stream:
        result = hashlib.sha256()
        while data := stream.read(1024*1024):
            result.update(data)
    return result.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def commit(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')

def utc():
    return datetime.now(timezone.utc).isoformat()

def bound():
    auth = read(AUTH)
    if not datetime.fromisoformat(auth['start_utc']).timestamp() <= time.time() < datetime.fromisoformat(auth['end_utc']).timestamp():
        raise RuntimeError('Stage230 absolute work window expired')
    return auth

def environment():
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        if os.environ.get(name) != '1':
            raise RuntimeError('One computational thread required: '+name)

def verify(mapping):
    for path, expected in mapping.items():
        for attempt in range(3):
            bound()
            try:
                actual = sha(path)
            except OSError:
                if attempt == 2:
                    raise
                bound()
                time.sleep(.25)
                continue
            if actual != expected:
                raise RuntimeError('Frozen same-path hash mismatch: '+path)
            break

def sealed(path):
    path = Path(path)
    result = read(path)
    if read(path.parent/'completion.json')['results_sha256'] != sha(path):
        raise RuntimeError('Unsealed evidence: '+str(path))
    return result
