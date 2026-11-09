"""Separate mechanics from changes in uptake: identical reference water and gap."""
import csv,json
from .fit import HERE
from applications.rhizofield.field import DX,Mesh,seed
from applications.rhizofield.run import connected,writecsv
from applications.rhizofield.refine import refined_geometry

def main():
    base=HERE.parent/'results'; prof=json.loads((HERE/'results/profiles.json').read_text());out=[]
    with (base/'identical_grain_gap.csv').open() as f: ref=list(csv.DictReader(f))
    for sc in (1,2):
        grid=50//sc; th=prof['grain_wall_inputs_deg'][str(grid)+'um']
        for r in ref:
            if float(r['grid_um'])!=grid:continue
            lab,x=seed();
            if sc==2: lab,x=refined_geometry(lab,x)
            m=Mesh(lab,677.5e-6/DX,grain_deg=th);s=m.solve(x,float(r['near_water_mm2'])*1e-6/DX**2)
            if not connected(m,s):raise RuntimeError('Disconnected shared-volume comparison')
            out.append(dict(mode=r['mode'],grid_um=grid,gap_um=677.5,near_water_mm2=r['near_water_mm2'],legacy_attraction_N_m=float(r['attraction_N_m']),calibrated_attraction_N_m=-s.force))
    writecsv(HERE/'results/matched_inventory.csv',out)
if __name__=='__main__':main()
