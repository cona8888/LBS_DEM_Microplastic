"""Hash read-only literature originals and verify repository download checksums."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "sources"
checks = []
for meta_path in sorted(SRC.glob("figshare_*.json")):
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    for item in meta.get("files", []):
        path = SRC / item["name"]
        if item.get("is_link_only") or not path.is_file():
            continue
        expected = item.get("computed_md5") or item.get("supplied_md5")
        actual = hashlib.md5(path.read_bytes()).hexdigest()
        checks.append({"file": path.name, "expected_md5": expected,
                       "actual_md5": actual, "passed": actual == expected,
                       "source": item["download_url"], "doi": meta.get("doi"),
                       "license": meta.get("license")})
zenodo = json.loads((SRC / "zenodo_14415011.json").read_text(encoding="utf-8-sig"))
for item in zenodo["files"]:
    path = SRC / item["key"]
    expected = item["checksum"].removeprefix("md5:")
    actual = hashlib.md5(path.read_bytes()).hexdigest()
    checks.append({"file": path.name, "expected_md5": expected,
                   "actual_md5": actual, "passed": actual == expected,
                   "source": item["links"]["self"]})
manifest = {
    "audited_at_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "Literature download integrity only, not scientific validation",
    "repository_checks": checks,
    "all_repository_checks_passed": all(c["passed"] for c in checks),
    "files": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size,
               "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in sorted(SRC.iterdir()) if p.is_file()],
    "additional_download_sources": {
        "ameen_2024_spheres.pdf": "https://www.tuwien.at/index.php?eID=dumpFile&f=1465746&t=f&token=857a8008509bc6bbbd73c38eb94d6f2ac0200101",
        "aminzadeh_2025_permeability.pdf": "https://www.nature.com/articles/s41598-025-30476-6.pdf",
        "rullander_2023_sand_filters.pdf": "https://research.chalmers.se/publication/537437/file/537437_Fulltext.pdf",
        "yu_thresholds_repository": "https://github.com/maramei97/ManuscriptThresholdsReanalysisYuetal.2023"
    }
}
output = ROOT / "source_manifest.json"
with output.open("x", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2)
assert manifest["all_repository_checks_passed"], "Downloaded source checksum mismatch"
print(json.dumps({"files": len(manifest["files"]), "checksum_checks": len(checks),
                  "passed": manifest["all_repository_checks_passed"]}))
