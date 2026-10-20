#!/usr/bin/env python3
"""Create the Stage26u presentation render with a fully visible claim boundary."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import matplotlib

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
SOURCE_DIR = ROOT / "stage26_renders" / "stage26u_three_grain_throat_20260820" / "render_01"
SOURCE_IMAGE = SOURCE_DIR / "stage26u_three_grain_throat.png"
SOURCE_MANIFEST = SOURCE_DIR / "render_manifest.json"
EVALUATION = ROOT / "stage26_evaluations" / "stage26u_three_grain_throat_20260820" / "throat_evaluation_01" / "evaluation.json"
OUT = ROOT / "stage26_renders" / "stage26u_three_grain_throat_20260820" / "render_02"
SCRIPT = Path(__file__).resolve()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def wrap_pixels(draw, text, font, maximum_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = word if not current else current + " " + word
        if draw.textbbox((0, 0), candidate, font=font)[2] <= maximum_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable render {OUT}")
for path in (SOURCE_IMAGE, SOURCE_MANIFEST, EVALUATION):
    if not path.is_file():
        raise RuntimeError(f"missing source {path}")
source_manifest = load(SOURCE_MANIFEST)
evaluation = load(EVALUATION)
if source_manifest.get("passed") is not True or evaluation.get("passed") is not True:
    raise RuntimeError("upstream render/evaluation is not accepted")
if source_manifest["image"]["sha256"] != sha(SOURCE_IMAGE):
    raise RuntimeError("source image hash mismatch")
if source_manifest["source_bindings"]["evaluation"]["sha256"] != sha(EVALUATION):
    raise RuntimeError("source render-to-evaluation mismatch")

image = Image.open(SOURCE_IMAGE).convert("RGB")
draw = ImageDraw.Draw(image)
font_path = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
font = ImageFont.truetype(str(font_path), 27)
boundary = (
    "Claim boundary: deterministic throat mechanism only. Not a measured Leighton Buzzard Sand "
    "pore-size distribution, polymer/contact calibration, 216-grain mixture, flow, or permeability "
    "prediction. Dashed force is prescribed load, not contact reaction."
)
blank_top = image.height - 168
draw.rectangle((0, blank_top, image.width, image.height), fill="white")
lines = wrap_pixels(draw, boundary, font, image.width - 300)
if len(lines) > 2:
    raise RuntimeError("claim boundary did not fit in two lines")
draw.multiline_text((150, blank_top + 29), "\n".join(lines), font=font, fill=(48, 48, 48), spacing=11)

OUT.mkdir(parents=True)
image_path = OUT / "stage26u_three_grain_throat.png"
image.save(image_path, format="PNG")
manifest = {
    "schema": "lbs.stage26u-three-grain-throat-render.v2",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True,
    "status": "presentation_render_verified",
    "image": {"path": str(image_path), "sha256": sha(image_path)},
    "renderer": {"path": str(SCRIPT), "sha256": sha(SCRIPT)},
    "source_bindings": {
        "render_01_image": {"path": str(SOURCE_IMAGE), "sha256": sha(SOURCE_IMAGE)},
        "render_01_manifest": {"path": str(SOURCE_MANIFEST), "sha256": sha(SOURCE_MANIFEST)},
        "evaluation": {"path": str(EVALUATION), "sha256": sha(EVALUATION)},
    },
    "modification": "Only the clipped bottom claim-boundary annotation was replaced with fully visible wrapped text; scientific panels and source pixels above the annotation band are unchanged.",
    "classifications": evaluation["classifications"],
    "claim_boundary": evaluation["claim_boundary"],
}
manifest_path = OUT / "render_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"image": str(image_path), "image_sha256": sha(image_path),
                  "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path)}, indent=2))
