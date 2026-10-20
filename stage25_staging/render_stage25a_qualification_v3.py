"""Stage25a renderer wrapper with corrected runpy global binding and writable aspect."""

import hashlib
import json
import runpy
from pathlib import Path

import numpy as np


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE_RENDERER = PROJECT / "stage25_staging" / "render_stage25a_qualification_v1.py"
OUTPUT = PROJECT / "stage25_renders" / "stage25a_pure_sand_mechanics_20260813" / "render_03"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


original_diag = np.diag
np.diag = lambda value, k=0: np.array(original_diag(value, k=k), dtype=float, copy=True)
namespace = runpy.run_path(str(BASE_RENDERER), run_name="stage25_render_base")
render_main = namespace["main"]
render_main.__globals__["OUTPUT"] = OUTPUT
render_main.__globals__["SCRIPT"] = Path(__file__)
render_main()

manifest_path = OUTPUT / "render_manifest.json"
with manifest_path.open("r", encoding="utf-8") as stream:
    manifest = json.load(stream)
manifest["source_hashes"]["renderer_base_sha256"] = digest(BASE_RENDERER)
temporary = OUTPUT / "render_manifest.json.tmp"
with temporary.open("x", encoding="utf-8") as stream:
    json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
temporary.replace(manifest_path)
print(json.dumps({"render_manifest_sha256": digest(manifest_path), "renderer_base_sha256": digest(BASE_RENDERER)}, sort_keys=True))
