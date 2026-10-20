"""Material lossless-storage qualification on sealed early and mature evidence."""
from pathlib import Path
import sys, json, time, shutil, hashlib, copy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cost_screen_v1 as screen
import numeric_archive_v1 as adapter
ROOT=screen.ROOT;OUT=ROOT/'paper1_runs/storage_qualification_20261013'
old=screen.q.job.codec;new=adapter.build(old,preset=9)


def run():
    screen.environment();assert not (OUT/'results.json').exists()
    fixtures=[('early9',ROOT/'paper1_runs/initial_cost_screen_20261013/records/case_11/cost',None),
              ('mature9',ROOT/'stage245_evaluations/guard_tail_20261013/records/production_00070',
               ROOT/'stage245_evaluations/guard_tail_20261013/records/production_00069')]
    receipts=[];inputs={};sources={str(Path(__file__).resolve()):screen.sha(__file__),
        str(Path(adapter.__file__).resolve()):screen.sha(adapter.__file__),
        str(Path(adapter.token.__file__).resolve()):screen.sha(adapter.token.__file__)}
    for label,folder,parent in fixtures:
        original_gate=screen.fields.sealed(folder/'guard_completion/results.json')
        assert original_gate['passed'];screen.api.verify_mapping(original_gate['artifacts'])
        prefix=before=None
        if parent:
            gate=screen.fields.sealed(parent/'guard_completion/results.json');assert gate['passed'];screen.api.verify_mapping(gate['artifacts'])
            ref=screen.read(parent/'prefix.json');before=screen.read(parent/'full_checkpoint.json')
            prefix=old.HistoryState(**ref,history_bytes=old.packed_history(before['state']['history']))
        source=folder/'call.json.xz';design=screen.read(source.with_suffix('.seal.json'))['design_sha256']
        record,history=old.read_record(source,design,prefix);original_digest=screen.api.digest(record)
        start=time.perf_counter();path=OUT/(label+'.json.xz')
        seal,produced=new.write_record(path,record,prefix)
        reconstructed,restored=new.read_record(path,design,prefix)
        assert screen.api.digest(reconstructed)==original_digest==screen.api.digest(record)
        assert restored.history_bytes==history.history_bytes==produced.history_bytes
        assert reconstructed['result']['checkpoint']==record['result']['checkpoint']
        assert new.base.read_bytes(path,design)==old.base.read_bytes(source,design)
        # Re-run the actual original independent physical and guard consumers.
        meta=record['spec']['field_metadata']
        with np.load(meta['geometry']['path']) as geometry:
            geom=screen.api.frozen.h.geometry_exact_v1.GrainGeometry(geometry['sand_centres_m'],geometry['sand_radii_m'],meta['cell_length_m'])
        if parent:
            kernel=screen.q.baseline.kernel
        else:
            kernel=screen.make_context().baseline.kernel
        # The stored effective binding has the original rigid suffix. Obtain
        # the independently declared physical binding from its sealed receipt.
        row=screen.fields.sealed(folder/'results.json')
        summary=kernel(reconstructed,record['spec'],row['original_binding'],before,geom,design,record['minimum_gap_semantics'])
        assert summary['passed'];guard=screen.q.guard.audit(reconstructed)
        receipts.append(dict(label=label,source_path=str(source),source_sha256=screen.sha(source),new_path=str(path),
            new_sha256=screen.sha(path),original_bytes=source.stat().st_size,new_bytes=path.stat().st_size,
            ratio=path.stat().st_size/source.stat().st_size,scoped_seconds=time.perf_counter()-start,
            exact_original_wire=True,exact_record=True,exact_full_checkpoint=True,exact_history=True,
            original_physical_audit=summary,original_guard_audit=guard))
        inputs.update({str(p):screen.sha(p) for p in (source,source.with_suffix('.seal.json'),folder/'results.json',
            folder/'completion.json',folder/'guard_completion/results.json',folder/'guard_completion/completion.json')})
        print('NUMERIC_ARCHIVE_FIXTURE_PASSED',label,receipts[-1]['ratio'],flush=True)
    path=Path(receipts[0]['new_path']);seal=screen.read(path.with_suffix('.seal.json'));bad=[]
    for label,kind in [('bitflip','bytes'),('trailing','trailing'),('raw_sha','raw_sha'),('resource','resource'),('design','design')]:
        dest=OUT/(label+'.json.xz');body=path.read_bytes();manifest=copy.deepcopy(seal)
        if kind=='bytes':body=body[:30]+bytes([body[30]^1])+body[31:]
        if kind=='trailing':
            body+=b'x';manifest['compressed_bytes']=len(body);manifest['compressed_sha256']=hashlib.sha256(body).hexdigest()
        if kind=='raw_sha':manifest['uncompressed_sha256']='0'*64
        if kind=='resource':manifest['uncompressed_bytes']=old.base.MAX_RAW+1
        if kind=='design':manifest['design_sha256']='0'*64
        with dest.open('xb') as stream:stream.write(body)
        screen.commit(dest.with_suffix('.seal.json'),manifest)
        try:new.read_record(dest,seal['design_sha256'])
        except (ValueError,RuntimeError):bad.append(label)
        else:raise RuntimeError('Corrupted archive accepted: '+label)
    assert len(bad)==5
    screen.api.verify_mapping(inputs);screen.api.verify_mapping(sources)
    screen.seal(OUT,dict(passed=True,source_files=sources,inputs=inputs,fixtures=receipts,corruption_controls=bad,
        new_transport_steps=0,installed_in_transport=False,physics_changes=[],accuracy_gate_changes=[],
        compression_preset=9,original_memory_size_crc_and_exclusive_write_gates_retained=True,utc=screen.utc(),
        artifacts={str(p):screen.sha(p) for p in OUT.glob('*') if p.is_file()}))
    print('NUMERIC_ARCHIVE_QUALIFIED',screen.sha(OUT/'results.json'),flush=True)


if __name__=='__main__':run()
