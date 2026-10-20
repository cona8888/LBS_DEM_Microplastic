"""Unchanged v1 acceptance tests, v3 candidate, complete local source binding."""
from pathlib import Path
import types
import qualify_sliding_projection_v1 as old
import sliding_projection_repair_v3 as repair

namespace=dict(old.run.__globals__)
namespace.update(repair=repair,__file__=__file__,OUT=old.BASE/'sliding_qualification_03',
                 DESIGN=old.q.ROOT/'stage194_designs/evidence_repair_20260924/sliding_qualification_03.json')
run=types.FunctionType(old.run.__code__,namespace,'run',old.run.__defaults__,old.run.__closure__)

if __name__=='__main__':
    paths=[Path(__file__),Path(old.__file__),Path(repair.__file__),Path(repair.prior.__file__),Path(repair.prior.prior.__file__),Path(old.q.__file__),Path(old.q.repair.__file__)]
    sources={str(p):old.api.sha(p) for p in paths}
    closure=old.q.ROOT/'stage194_designs/evidence_repair_20260924/sliding_qualification_03_sources.json'
    old.job.commit(closure,{'source_sha256':sources,'new_trajectory_steps':0,'qualified_function_code_equal':run.__code__==old.run.__code__})
    run()
    old.api.verify_mapping(sources)
    out=namespace['OUT'];result=out/'results.json'
    old.job.commit(out/'source_closure.json',{'source_manifest_sha256':old.api.sha(closure),'results_sha256':old.api.sha(result),'sources_unchanged':True,'old_qualification_function_bytecode_unchanged':True})
