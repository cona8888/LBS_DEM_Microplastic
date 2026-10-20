#!/usr/bin/env bash
set -euo pipefail

for root in /usr/share/doc/yade /usr/lib/python3/dist-packages/yade /usr/share/yade; do
  if [[ -d "$root" ]]; then
    find "$root" -type f \( -iname '*GridConnection*' -o -iname '*gridpfacet*' \) -print
  fi
done

example=''
for candidate in \
  /usr/share/doc/yade/examples/grids/GridConnection_Spring.py \
  /usr/share/yade/examples/grids/GridConnection_Spring.py; do
  if [[ -f "$candidate" ]]; then
    example="$candidate"
    break
  fi
done

if [[ -n "$example" ]]; then
  echo "CODEX_EXAMPLE=$example"
  sed -n '1,260p' "$example"
fi

echo 'CODEX_ALPHARK_REFERENCES'
grep -R -n --include='*.py' 'alphaKr\|GridNodeGeom6D' /usr/share/doc/yade/examples 2>/dev/null | head -120 || true

if [[ -f /usr/share/doc/yade/examples/cylinders/bendingbeams.py ]]; then
  echo 'CODEX_BENDING_BEAMS_EXAMPLE'
  sed -n '1,320p' /usr/share/doc/yade/examples/cylinders/bendingbeams.py
fi
