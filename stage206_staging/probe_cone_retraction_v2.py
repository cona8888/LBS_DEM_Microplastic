"""Bound the sorted diagnostic candidate inventory; preserve v1 false-negative."""
from pathlib import Path
text=Path(__file__).with_name('probe_cone_retraction_v1.py').read_text()
changes={
    "for c in api.read(report)['finalizer_candidates']:":"for c in sorted(api.read(report)['finalizer_candidates'],key=lambda c:c['residual']):",
    "api.require(0<len(unique)<=4,'bounded near-feasible candidates')":"unique=unique[:4]\n    api.require(0<len(unique)<=4,'bounded near-feasible candidates')",
    "cone_feasibility_01'":"cone_feasibility_02'",
}
for old,new in changes.items():
    if text.count(old)!=1:raise RuntimeError('exact bounded harness replacement')
    text=text.replace(old,new)
ns={'__name__':'_stage206_cone_probe_v2','__file__':__file__}
exec(compile(text,__file__+'::bounded_inventory','exec'),ns)
if __name__=='__main__':ns['run']()
