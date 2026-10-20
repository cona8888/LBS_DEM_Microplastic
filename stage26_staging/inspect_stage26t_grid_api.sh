#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import inspect
from pathlib import Path
p=Path('/usr/lib/x86_64-linux-gnu/yade-double/py/yade/gridpfacet.py')
print(p)
text=p.read_text()
for name in ('def gridNode','def gridConnection','def cylinderConnection'):
    i=text.index(name)
    print(text[i:i+2600])
PY
grep -R -n --include='*.py' 'ScGridCoGeom_FrictPhys\|extMaterial' /usr/share/doc/yade/examples 2>/dev/null | head -160 || true
