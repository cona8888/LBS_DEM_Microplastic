"""Preserved-failure successor: unchanged tests, corrected live backend binding."""
import ast
import inspect
import sys
import traceback
import verify_rigid_rotation_v1 as workflow
import rigid_rotation_v2 as repaired

api=workflow.api
FAILURE=workflow.OUT/'failure.json'
FAILED_DESIGN=workflow.DESIGN
workflow.model=repaired
workflow.BASE='bounded_rigid_rotation_runtimefix_20260921'
workflow.DESIGN=workflow.ROOT/'stage151_designs'/workflow.BASE/'design_01.json'
workflow.OUT=workflow.ROOT/'stage151_evaluations'/workflow.BASE/'qualification_01'


def prepare():
    failure=api.read(FAILURE)
    api.require('set_recovery_mode' in failure['error'],'unexpected predecessor failure')
    tree=ast.parse(inspect.getsource(workflow.prepare))
    body=tree.body[0].body
    index=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=="d['binding']")
    addition=ast.parse("""
d['runtime_repair']='Bind the generated integrator to the live Stage79 contact backend installed by the checkpoint trampoline, rather than the import-time module. No equation, acceptance criterion, timestep or initial state changed.'
d['inputs'][str(PREDECESSOR_FAILURE)]=api.sha(PREDECESSOR_FAILURE)
d['inputs'][str(PREDECESSOR_DESIGN)]=api.sha(PREDECESSOR_DESIGN)
""").body
    body[index:index]=addition;ast.fix_missing_locations(tree)
    namespace=dict(workflow.__dict__);namespace.update(PREDECESSOR_FAILURE=FAILURE,PREDECESSOR_DESIGN=FAILED_DESIGN)
    exec(compile(tree,'<Stage151:provenance-bound-runtime-repair>','exec'),namespace)
    namespace['prepare']()


if __name__=='__main__':
    try:
        if sys.argv[1]=='prepare':prepare()
        elif sys.argv[1]=='run':raise SystemExit(workflow.run())
        else:raise ValueError('unknown command')
    except Exception as exc:
        if workflow.OUT.exists() and not (workflow.OUT/'failure.json').exists():api.write(workflow.OUT/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()})
        raise
