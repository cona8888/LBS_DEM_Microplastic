"""Repeat immutable outer qualification for corrected explicit provenance."""
from pathlib import Path
import qualify_two_contact_outer_v1 as prior
text=Path(prior.__file__).read_text()
text=text.replace('two_contact_scalar_repair_v1','two_contact_scalar_repair_v2').replace('audit_two_contact_routes_v1','audit_two_contact_routes_v2').replace('outer_qualification_01','outer_qualification_02')
ns={'__name__':'_outer_v2','__file__':__file__}
exec(compile(text,__file__+'::provenance_v2','exec'),ns)
if __name__=='__main__':ns['run']()
