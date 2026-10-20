"""Read-only input audit; never executes downloaded code or repairs observations."""
import hashlib, json, math, zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'stage36_evaluations/literature_extraction_20260909'
out = base / 'export_audit_01'
out.mkdir(exist_ok=False)
archive = base / 'raw/Comparison.zip'
with zipfile.ZipFile(archive) as z:
    lines = z.read('Comparison/concFIT_export.txt').decode().splitlines()
start = next(i for i,s in enumerate(lines) if s.strip().startswith('t \t'))
names = lines[start].split()
rows = [[float(x) for x in s.split()] for s in lines[start+1:] if s.strip()]
assert all(len(r)==11 for r in rows)
assert all(b[0]>a[0] for a,b in zip(rows,rows[1:]))
result = {'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
          'row_count':len(rows),'time_range_s':[rows[0][0],rows[-1][0]],
          'classification':'unqualified export; no physical fitting', 'columns':[]}
for j in range(1,11):
    finite = [(r[0],r[j]) for r in rows if math.isfinite(r[j])]
    extreme = [(t,v) for t,v in finite if abs(v)>1e6]
    result['columns'].append({'name':names[j], 'nan_count':sum(math.isnan(r[j]) for r in rows),
        'zero_censored_count':sum(r[j]==0 for r in rows),
        'max_finite':max(v for t,v in finite),'extreme_count':len(extreme),
        'extreme_time_range_s':[extreme[0][0],extreme[-1][0]] if extreme else None})
result['extreme_threshold_note']='1e6 s^-1 is an audit flag, not a valid-data cutoff; no clipping applied.'
(out/'audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
