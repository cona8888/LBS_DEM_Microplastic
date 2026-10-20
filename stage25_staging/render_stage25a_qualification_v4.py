"""Final Stage25a renderer: isolate Matplotlib box-aspect normalization from data."""

import hashlib
import json
import runpy
from pathlib import Path

import numpy as np
from mpl_toolkits.mplot3d.axes3d import Axes3D


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
BASE_RENDERER = PROJECT / "stage25_staging" / "render_stage25a_qualification_v1.py"
OUTPUT = PROJECT / "stage25_renders" / "stage25a_pure_sand_mechanics_20260813" / "render_04"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


original_set_box_aspect = Axes3D.set_box_aspect


def isolated_set_box_aspect(self, aspect, *args, **kwargs):
    return original_set_box_aspect(self, np.array(aspect, dtype=float, copy=True), *args, **kwargs)


Axes3D.set_box_aspect = isolated_set_box_aspect
namespace = runpy.run_path(str(BASE_RENDERER), run_name="stage25_render_base")
render_main = namespace["main"]
render_main.__globals__["OUTPUT"] = OUTPUT
render_main.__globals__["SCRIPT"] = Path(__file__)
render_main()

manifest_path = OUTPUT / "render_manifest.json"
with manifest_path.open("r", encoding="utf-8") as stream:
    manifest = json.load(stream)
manifest["source_hashes"]["renderer_base_sha256"] = digest(BASE_RENDERER)
manifest["correction"] = "Box-aspect normalization receives a private writable copy, preserving the verified physical cell dimensions used in annotations and minimum-image geometry."
temporary = OUTPUT / "render_manifest.json.tmp"
with temporary.open("x", encoding="utf-8") as stream:
    json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
temporary.replace(manifest_path)
print(json.dumps({"render_manifest_sha256": digest(manifest_path), "renderer_base_sha256": digest(BASE_RENDERER)}, sort_keys=True))
