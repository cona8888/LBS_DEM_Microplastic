#!/usr/bin/env python3
"""Freeze Stage26k evidence and preserve downstream locks."""

from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def load(path):
    with Path(path).open("r",encoding="utf-8") as stream:return json.load(stream)


def main():
    p=argparse.ArgumentParser();p.add_argument("--evaluation",type=Path,required=True);p.add_argument("--render-manifest",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args()
    ev,render=load(a.evaluation),load(a.render_manifest)
    assert ev["passed"] is True and ev["pilot_success"] is False and ev["sand_skeleton_recovered"] is True
    assert render["passed"] is True and render["source_hashes"]["evaluation"]==sha256(a.evaluation)
    assert all(value is False for value in ev["authority"].values())
    payload={"schema":"lbs.stage26k-loose-cocompaction-pilot-checkpoint.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"passed":True,
             "status":"healthy_sand_fixed_fibre_support_failure_frozen","pilot_success":False,"sand_skeleton_recovered":True,
             "mechanics_conclusion":"Loose-state co-compaction repairs the sand network, but fixed fibre pivots prevent robust support formation.",
             "next_action":"bounded_mobile_fibre_loose_state_cocompaction_pilot","authority":ev["authority"],
             "source_hashes":{"evaluation":sha256(a.evaluation),"render_manifest":sha256(a.render_manifest),"freezer":sha256(Path(__file__))},"claim_boundary":ev["claim_boundary"]}
    a.output_dir.mkdir(parents=True,exist_ok=False);out=a.output_dir/"checkpoint_manifest.json"
    with out.open("x",encoding="utf-8",newline="\n") as stream:json.dump(payload,stream,indent=2,sort_keys=True);stream.write("\n")
    print(json.dumps({"checkpoint":str(out),"checkpoint_sha256":sha256(out)},sort_keys=True))


if __name__=="__main__":main()
