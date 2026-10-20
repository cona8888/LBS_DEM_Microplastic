"""Versioned Stage126 entry point: install the qualified generic-mask adapter before preflight."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage126_staging'))
import cpd6_relaxation_v1 as v1

STUDY='cpd6_bounded_relaxation_attempt02_20260916'
v1.DESIGN=ROOT/'stage126_designs'/STUDY/'design_01.json'
v1.RUN=ROOT/'stage126_runs'/STUDY/'gpu_relaxation_01'
v1.EVAL=ROOT/'stage126_evaluations'/STUDY


def prepare():
    v1.prepare()


def preflight():
    v1.s114.audit.legacy.install_generic_mask_oracle()
    v1.preflight()


def run():
    v1.run()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','preflight','run']);a=p.parse_args()
    {'prepare':prepare,'preflight':preflight,'run':run}[a.mode]()
