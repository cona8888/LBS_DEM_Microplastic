"""Non-trajectory development trials; outputs remain diagnostic, not acceptance."""
import json
from pathlib import Path
import time
import numpy as np
from mixed_contact_v1 import solve

root = Path(__file__).resolve().parents[1]
for path in sorted((root / 'stage118_runs/three_contact_diagnosis_20260916/local_probe_01').glob('*/record.json')):
    s = json.loads(path.read_text())['result']['contact_systems'][0]
    started = time.perf_counter()
    try:
        q, h = solve(*[np.asarray(s[k]) for k in ['vfree','mobility','jacobian','gaps']], s['dt_s'],s['friction'],s['tol'],s['maxiter'])
        print(path.parent.name, 'PASS', h, 'seconds',time.perf_counter()-started, flush=True)
    except Exception as e:
        print(path.parent.name,'FAIL',repr(e),'seconds',time.perf_counter()-started,flush=True)
