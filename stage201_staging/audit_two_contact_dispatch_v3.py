"""Routing-only audit for scalar-first ordering after primary rejection."""
from pathlib import Path
import hashlib,types
import two_contact_scalar_dispatch_v3 as repair
import audit_two_contact_routes_v2 as prior
source=Path(prior.__file__).read_text()
old="require(h['original_mixed_error'] in repair.ERRORS and h['original_mixed_solver']=='stage119_scaled_active_modes','preserved original mixed-solver failure')"
new="require(h['scalar_dispatch_policy']=='after_original_primary_failure' and h['original_mixed_attempted'] is False,'explicit primary-failure scalar-first ordering')"
if source.count(old)!=1:raise RuntimeError('one exact numerical ordering provenance change')
source=source.replace('import two_contact_scalar_repair_v2 as repair','import two_contact_scalar_dispatch_v3 as repair').replace(old,new)
ns={'__name__':'_dispatch_audit_v3','__file__':__file__};exec(compile(source,__file__+'::ordering_identity_only','exec'),ns)
evaluate=ns['evaluate'];kernel=ns['kernel'];STRUCTURAL_IDENTITY=ns['STRUCTURAL_IDENTITY']
