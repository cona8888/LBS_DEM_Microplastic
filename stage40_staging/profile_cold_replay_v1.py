"""Bind the real-state replay to robust cold-start Coulomb solves."""
import hashlib, json, sys
from pathlib import Path
import profile_cached_replay_v1 as previous
import trajectory_cold_trap_v1 as trajectory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == "__main__":
    previous.trajectory = trajectory
    output = Path(sys.argv[sys.argv.index("--output") + 1])
    try:
        previous.main()
    finally:
        if output.exists() and (output / "results.json").exists():
            manifest = {"wrapper": str(Path(__file__).resolve()), "wrapper_sha256": sha(__file__),
                        "trajectory": str(Path(trajectory.__file__).resolve()),
                        "trajectory_sha256": sha(trajectory.__file__),
                        "results_sha256": sha(output / "results.json")}
            (output / "wrapper_manifest.json").write_text(json.dumps(manifest, indent=2))
