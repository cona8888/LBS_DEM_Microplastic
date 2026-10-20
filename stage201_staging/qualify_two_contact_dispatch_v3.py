"""Full fixed-pose tests for the bounded primary-failure numerical ordering."""
from pathlib import Path
import qualify_two_contact_outer_v1 as prior
text=Path(prior.__file__).read_text()
text=text.replace('two_contact_scalar_repair_v1','two_contact_scalar_dispatch_v3').replace('audit_two_contact_routes_v1','audit_two_contact_dispatch_v3').replace('outer_qualification_01','dispatch_qualification_03')
needle="reports.append({'index':i,'passed':check['passed']"
replace="reference=api.read(OUT.parent/'outer_qualification_02'/('fixture_%02d.json'%i))['fixture']['rows'][0]['velocity_generalized'];api.require(answer[0].tolist()==reference,'exact previously qualified outer velocity');reports.append({'index':i,'passed':check['passed']"
if text.count(needle)!=1:raise RuntimeError('one exact extra velocity identity check')
text=text.replace(needle,replace)
ns={'__name__':'_dispatch_tests_v3','__file__':__file__};exec(compile(text,__file__+'::dispatch_v3','exec'),ns)
if __name__=='__main__':ns['run']()
