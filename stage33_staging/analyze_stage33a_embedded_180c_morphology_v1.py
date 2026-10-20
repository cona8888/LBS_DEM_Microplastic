"""Exploratory audit of the annotated 180 C microscopy composite embedded in pet plastic.pptx.

This script is deliberately not a publication measurement pipeline.  It works on a
JPEG composite with baked annotations and therefore writes PRELIMINARY records only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


INPUT = Path(
    r"C:\MATDEM_MICROPLASTIC\.tmp\pet_plastic_review_20260829\unpacked\ppt\media\image7.jpeg"
)

# Tight source-pixel regions around the 11 visibly annotated objects.  These are
# review coordinates, not original microscope object selections.
OBJECTS = [
    {"id": "S2-200", "displayed_length_um": 200.0, "bbox": [448, 40, 505, 246], "seed": [475, 145], "shape_review": "straight_elongate", "morphometry_status": "eligible_exploratory"},
    {"id": "S2-077", "displayed_length_um": 77.0, "bbox": [500, 158, 568, 249], "seed": [533, 207], "shape_review": "short_straight_elongate", "morphometry_status": "eligible_exploratory"},
    {"id": "S2-155", "displayed_length_um": 155.0, "bbox": [374, 360, 496, 515], "seed": [438, 434], "shape_review": "elongate_irregular_or_split", "morphometry_status": "eligible_exploratory_with_shape_caveat"},
    {"id": "S2-086", "displayed_length_um": 86.0, "bbox": [641, 417, 708, 524], "seed": [670, 472], "shape_review": "short_straight_elongate", "morphometry_status": "eligible_exploratory"},
    {"id": "S2-076", "displayed_length_um": 76.0, "bbox": [658, 556, 771, 660], "seed": [708, 613], "shape_review": "compact_irregular", "morphometry_status": "exclude_from_rod_aspect_ratio_compact_ambiguous"},
    {"id": "S2-132", "displayed_length_um": 132.0, "bbox": [198, 537, 274, 690], "seed": [232, 617], "shape_review": "straight_elongate", "morphometry_status": "eligible_exploratory"},
    {"id": "S2-143", "displayed_length_um": 143.0, "bbox": [45, 661, 142, 817], "seed": [97, 742], "shape_review": "elongate_in_overlap_region", "morphometry_status": "exclude_overlap_or_bundle"},
    {"id": "S2-142", "displayed_length_um": 142.0, "bbox": [293, 576, 409, 746], "seed": [350, 666], "shape_review": "straight_elongate", "morphometry_status": "eligible_exploratory"},
    {"id": "S2-226", "displayed_length_um": 226.0, "bbox": [102, 647, 207, 904], "seed": [161, 780], "shape_review": "elongate_bundle_or_overlap", "morphometry_status": "exclude_overlap_or_bundle"},
    {"id": "S2-124", "displayed_length_um": 124.0, "bbox": [398, 747, 472, 904], "seed": [435, 826], "shape_review": "straight_elongate", "morphometry_status": "exclude_border_or_overlap"},
    {"id": "S2-074", "displayed_length_um": 74.0, "bbox": [708, 728, 827, 834], "seed": [770, 784], "shape_review": "short_rectangular_fragment", "morphometry_status": "eligible_exploratory"},
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def runs_1d(mask: np.ndarray):
    runs = []
    start = None
    for i, value in enumerate(mask.tolist()):
        if value and start is None:
            start = i
        if start is not None and (not value or i == len(mask) - 1):
            end = i if value and i == len(mask) - 1 else i - 1
            runs.append((start, end, end - start + 1))
            start = None
    return runs


def detect_scale_bar(rgb: np.ndarray):
    # The 100 um bar is the long white rectangle in the black footer of panel A.
    candidates = []
    for y in range(925, min(970, rgb.shape[0])):
        white = np.all(rgb[y, 720:910, :] >= 245, axis=1)
        for x0, x1, length in runs_1d(white):
            if 80 <= length <= 150:
                candidates.append((length, 720 + x0, 720 + x1, y))
    if not candidates:
        raise RuntimeError("Could not detect scale-bar run")
    length, x0, x1, y = max(candidates)
    return {
        "run_length_px_inclusive": int(length),
        "x0_px": int(x0),
        "x1_px": int(x1),
        "y_px": int(y),
        "nominal_length_um": 100.0,
        "px_per_um": float(length / 100.0),
        "um_per_px": float(100.0 / length),
    }


def dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    out = mask.copy()
    for _ in range(iterations):
        p = np.pad(out, 1, mode="constant")
        shifted = [p[1 + dy : 1 + dy + out.shape[0], 1 + dx : 1 + dx + out.shape[1]] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        out = np.logical_or.reduce(shifted)
    return out


def erode(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    out = mask.copy()
    for _ in range(iterations):
        p = np.pad(out, 1, mode="constant", constant_values=False)
        shifted = [p[1 + dy : 1 + dy + out.shape[0], 1 + dx : 1 + dx + out.shape[1]] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        out = np.logical_and.reduce(shifted)
    return out


def components(mask: np.ndarray):
    seen = np.zeros(mask.shape, dtype=bool)
    found = []
    h, w = mask.shape
    for yy in range(h):
        for xx in range(w):
            if not mask[yy, xx] or seen[yy, xx]:
                continue
            q = deque([(yy, xx)])
            seen[yy, xx] = True
            pts = []
            while q:
                y, x = q.popleft()
                pts.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not (dx or dy):
                            continue
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            q.append((ny, nx))
            found.append(np.asarray(pts, dtype=int))
    return found


def convex_hull(points_xy: np.ndarray):
    pts = sorted(set(map(tuple, points_xy.tolist())))
    if len(pts) <= 1:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def polygon_area(poly):
    if len(poly) < 3:
        return 0.0
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))) / 2.0


def segment_object(rgb_crop: np.ndarray, seed_local_xy):
    r, g, b = rgb_crop[..., 0], rgb_crop[..., 1], rgb_crop[..., 2]
    red = (r > 130) & (r > 1.35 * g) & (r > 1.35 * b)
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    dark = (gray < 145) & (~red)
    # Bridge JPEG gaps and the thin cuts left by red annotation removal.
    closed = erode(dilate(dark, 2), 2)
    comps = [c for c in components(closed) if len(c) >= 40]
    if not comps:
        raise RuntimeError("No component found")
    sx, sy = seed_local_xy

    def score(c):
        cy, cx = c.mean(axis=0)
        distance = math.hypot(cx - sx, cy - sy)
        # Seed proximity dominates, with a weak preference for substantial components.
        return distance - 0.02 * math.sqrt(len(c))

    chosen = min(comps, key=score)
    # Use the original dark mask within a 3 px halo of the selected closed component.
    selected = np.zeros(dark.shape, dtype=bool)
    selected[chosen[:, 0], chosen[:, 1]] = True
    selected = dilate(selected, 3) & dark
    pts_yx = np.argwhere(selected)
    if len(pts_yx) < 20:
        pts_yx = chosen
    return selected, pts_yx


def metrics_from_points(pts_yx: np.ndarray, scale, displayed_length_um: float):
    xy = pts_yx[:, [1, 0]].astype(float)
    center = xy.mean(axis=0)
    centered = xy - center
    cov = np.cov(centered, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    major_vec, minor_vec = vecs[:, order[0]], vecs[:, order[1]]
    major_proj = centered @ major_vec
    minor_proj = centered @ minor_vec
    major_px = float(np.percentile(major_proj, 99) - np.percentile(major_proj, 1) + 1)
    width_px = float(np.percentile(minor_proj, 99) - np.percentile(minor_proj, 1) + 1)
    area_px = int(len(xy))
    hull = convex_hull(xy.astype(int))
    hull_area = polygon_area(hull)
    solidity = float(area_px / hull_area) if hull_area > 0 else None
    width_um = width_px * scale["um_per_px"]
    return {
        "segmented_area_px": area_px,
        "segmented_major_extent_px_p01_p99": major_px,
        "segmented_width_px_p01_p99": width_px,
        "segmented_width_um_preliminary": width_um,
        "displayed_length_to_segmented_width_aspect_ratio_preliminary": displayed_length_um / width_um if width_um > 0 else None,
        "segmented_major_to_width_ratio_preliminary": major_px / width_px if width_px > 0 else None,
        "segmented_solidity_preliminary": solidity,
        "centroid_x_px": float(center[0]),
        "centroid_y_px": float(center[1]),
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_stage33a_embedded_180c_morphology_v1.py OUTPUT_DIR")
    out_dir = Path(sys.argv[1])
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"fail-closed: output directory is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    image = Image.open(INPUT).convert("RGB")
    rgb = np.asarray(image)
    scale = detect_scale_bar(rgb)

    rows = []
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    crop_tiles = []

    for obj in OBJECTS:
        x0, y0, x1, y1 = obj["bbox"]
        crop = rgb[y0:y1, x0:x1, :]
        seed_local = (obj["seed"][0] - x0, obj["seed"][1] - y0)
        mask, pts = segment_object(crop, seed_local)
        metrics = metrics_from_points(pts, scale, obj["displayed_length_um"])
        row = {**obj, **metrics, "evidence_status": "exploratory_from_annotated_jpeg_not_publication_grade"}
        rows.append(row)

        # Overlay source image with review region and selected source pixels.
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(0, 110, 255), width=2)
        draw.text((x0 + 2, y0 + 2), obj["id"], fill=(0, 70, 220), font=font)
        mask_img = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        mask_arr = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
        mask_arr[mask] = (0, 190, 255, 105)
        mask_img = Image.fromarray(mask_arr, mode="RGBA")
        overlay.paste(mask_img, (x0, y0), mask_img)

        tile = Image.fromarray(crop).resize(((x1 - x0) * 2, (y1 - y0) * 2))
        tile_mask = Image.fromarray((mask.astype(np.uint8) * 170), mode="L").resize(tile.size)
        cyan = Image.new("RGBA", tile.size, (0, 190, 255, 110))
        tile_rgba = tile.convert("RGBA")
        tile_rgba.alpha_composite(Image.composite(cyan, Image.new("RGBA", tile.size, (0, 0, 0, 0)), tile_mask))
        crop_tiles.append((obj["id"], obj["displayed_length_um"], metrics["displayed_length_to_segmented_width_aspect_ratio_preliminary"], tile_rgba.convert("RGB")))

    overlay.save(out_dir / "annotated_composite_review_overlay.png")

    # Contact sheet of source crops with selected-pixel overlay.
    cell_w, cell_h = 300, 280
    sheet = Image.new("RGB", (cell_w * 4, cell_h * 3), "white")
    sdraw = ImageDraw.Draw(sheet)
    for i, (oid, length, ar, tile) in enumerate(crop_tiles):
        row, col = divmod(i, 4)
        tile.thumbnail((cell_w - 20, cell_h - 50))
        x = col * cell_w + (cell_w - tile.width) // 2
        y = row * cell_h + 35
        sheet.paste(tile, (x, y))
        sdraw.text((col * cell_w + 8, row * cell_h + 8), f"{oid}  L={length:.0f} um  AR~{ar:.2f}", fill="black", font=font)
    sheet.save(out_dir / "object_crop_contact_sheet.png")

    csv_fields = [
        "id", "displayed_length_um", "shape_review", "morphometry_status", "segmented_width_um_preliminary",
        "displayed_length_to_segmented_width_aspect_ratio_preliminary",
        "segmented_major_to_width_ratio_preliminary", "segmented_solidity_preliminary",
        "segmented_area_px", "segmented_major_extent_px_p01_p99", "segmented_width_px_p01_p99",
        "centroid_x_px", "centroid_y_px", "evidence_status",
    ]
    with (out_dir / "exploratory_object_morphology.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows([{k: r.get(k) for k in csv_fields} for r in rows])

    eligible = [r for r in rows if r["morphometry_status"].startswith("eligible_exploratory")]
    ars = np.array([r["displayed_length_to_segmented_width_aspect_ratio_preliminary"] for r in eligible], dtype=float)
    widths = np.array([r["segmented_width_um_preliminary"] for r in eligible], dtype=float)
    manifest = {
        "schema": "pet.stage33a-embedded-180c-morphology-exploratory.v1",
        "status": "complete_exploratory_not_publication_grade",
        "source": {
            "path": str(INPUT),
            "sha256": sha256(INPUT),
            "pixel_dimensions": [image.width, image.height],
            "treatment_assignment": "180 C, 12 h, 1 g PET wool in 50 mL water; user-confirmed",
        },
        "scale_bar_detection": scale,
        "object_count": len(rows),
        "exploratory_aspect_ratio_eligible_count": len(eligible),
        "summary_preliminary": {
            "displayed_length_um_min": min(r["displayed_length_um"] for r in rows),
            "displayed_length_um_median": float(np.median([r["displayed_length_um"] for r in rows])),
            "displayed_length_um_max": max(r["displayed_length_um"] for r in rows),
            "eligible_segmented_width_um_median": float(np.median(widths)),
            "eligible_aspect_ratio_median": float(np.median(ars)),
            "eligible_aspect_ratio_min": float(np.min(ars)),
            "eligible_aspect_ratio_max": float(np.max(ars)),
        },
        "limitations": [
            "source is a JPEG composite rather than the original microscope image",
            "red brackets, labels and histogram are baked into source pixels",
            "object review regions were reconstructed manually from the displayed annotations",
            "overlap, debris, JPEG compression and annotation removal bias width, solidity and aspect ratio",
            "shape_review is qualitative and not blinded",
            "metrics are workflow-development evidence only and must not be reported as publication estimates",
        ],
        "records": rows,
    }
    with (out_dir / "exploratory_morphology_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "output_dir": str(out_dir),
        "source_sha256": manifest["source"]["sha256"],
        "scale": scale,
        "summary": manifest["summary_preliminary"],
    }, indent=2))


if __name__ == "__main__":
    main()
