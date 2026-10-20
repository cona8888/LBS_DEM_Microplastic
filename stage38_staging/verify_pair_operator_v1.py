import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import pair_operator_mfs_v1 as pair

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--n',type=int,default=384);args=ap.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False);axes=np.array([.0002,.00005,.00005])/.000385
    rows=[]; started=time.perf_counter()
    for degrees in (0,45,90):
        R,h=pair.solve(axes,.2,np.deg2rad(degrees),args.n); np.save(out/f'operator_{degrees:02}.npy',R)
        checks={'boundary_error':h['boundary_error_max']<=.002,
                'reciprocity':h['reciprocity_residual']<=.002,'positive_dissipation':h['minimum_symmetric_eigenvalue']>0}
        row={'angle_degrees':degrees,'n':args.n,'health':h,'checks':checks,'passed':all(checks.values()),'operator_sha256':sha(out/f'operator_{degrees:02}.npy')};rows.append(row);print(json.dumps(row),flush=True)
    sources=[Path(__file__),Path(pair.__file__)]
    result={'completed':True,'passed':all(r['passed'] for r in rows),'rows':rows,'runtime_seconds':time.perf_counter()-started,
            'scope':'reference pair operators only; no lubrication interpolation or trajectory promotion',
            'hashes':{str(p.resolve()):sha(p) for p in sources}}
    (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'seconds':result['runtime_seconds']}))
if __name__=='__main__':main()
