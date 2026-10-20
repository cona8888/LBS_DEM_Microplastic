"""Round the constructed velocity exactly as the original physical finalizer."""
from pathlib import Path
import qualify_manufactured_two_contact_v1 as prior
text=Path(prior.__file__).read_text()
needle="oracle=held.audit(system,q,{'reactions':f});"
if text.count(needle)!=1:raise RuntimeError('one manufactured representation correction')
text=text.replace(needle,"oracle=held.audit(system,v+M@J.T@f,{'reactions':f});")
text=text.replace('manufactured_qualification_01','manufactured_qualification_02')
ns={'__name__':'_manufactured_v2','__file__':__file__}
exec(compile(text,__file__+'::original_velocity_rounding','exec'),ns)
if __name__=='__main__':ns['run']()
