"""V2 fixes a helper/local-name collision; all four routing edits are retained."""
from pathlib import Path
import hashlib,types
import audit_projection_routes_v1 as prior
old=prior.old
source=prior.source
old_call='accepted_route(system,call,repair)';new_call='check_stage194_accepted_route(system,call,repair)'
if source.count(old_call)!=1:raise RuntimeError('exact helper call required')
source=source.replace(old_call,new_call)
namespace={**prior.namespace,'check_stage194_accepted_route':prior.accepted_route}
exec(compile(source,str(Path(__file__))+'::four_route_sites','exec'),namespace)
evaluate=namespace['evaluate']
STRUCTURAL_IDENTITY={**prior.STRUCTURAL_IDENTITY,'revised_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'helper_local_collision_fixed':True}
kernel_namespace={**prior.q.job.kernel.evaluate.__globals__,'association':types.SimpleNamespace(evaluate=evaluate)}
kernel=types.FunctionType(prior.q.job.kernel.evaluate.__code__,kernel_namespace,'evaluate',prior.q.job.kernel.evaluate.__defaults__,prior.q.job.kernel.evaluate.__closure__)
