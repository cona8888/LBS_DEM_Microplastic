"""V2 module alias collision fixed; preserved diagnostics and identical gates."""
from pathlib import Path
import audit_failed_preflight_v2 as previous
api,job=previous.api,previous.job
source=previous.source
before='Path(original.__file__)'
after="Path(original_module.__file__),Path(previous.__file__),job.OUT/'failed_audit_v2_prelaunch_failure_01.json'"
api.require(source.count(before)==1,'single diagnostic module alias correction')
source=source.replace(before,after)
ns=dict(previous.ns,__file__=__file__,OUT=job.OUT/'failed_preflight_independent_03',original_module=previous.original,previous=previous)
exec(compile(source,__file__+'::unchanged_independent_physical_audit','exec'),ns)
if __name__=='__main__':ns['run']()
