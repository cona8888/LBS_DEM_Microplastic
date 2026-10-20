"""Check source snapshot integrity and syntax without importing model modules."""
from pathlib import Path
import ast
import hashlib
import json

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "SOURCE_SNAPSHOT.json").read_text(encoding="utf-8"))
errors = []
python_files = 0
for entry in manifest["files"]:
    path = root / entry["path"]
    if not path.is_file():
        errors.append(f"Missing: {entry['path']}")
        continue
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        errors.append(f"Changed: {entry['path']}")
    if path.suffix == ".py":
        python_files += 1
        try:
            ast.parse(data.decode("utf-8-sig"), filename=entry["path"])
        except (SyntaxError, UnicodeError) as error:
            errors.append(f"Syntax: {entry['path']}: {error}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"PASS: {len(manifest['files'])} file hashes; {python_files} Python files parsed; no model imported or executed.")
