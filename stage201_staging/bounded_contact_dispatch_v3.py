"""Same bounded runner/ledger with separately qualified scalar-first ordering."""
from pathlib import Path
import sys
import bounded_contact_diagnostic_v1 as prior
text=Path(prior.__file__).read_text()
text=text.replace('two_contact_scalar_repair_v2','two_contact_scalar_dispatch_v3').replace('audit_two_contact_routes_v2','audit_two_contact_dispatch_v3')
text=text.replace("('held_qualification_01','outer_qualification_02')","('held_qualification_01','outer_qualification_02','dispatch_qualification_03','dispatch_controls_03')")
# Own-worker guard must include either bounded diagnostic implementation.
text=text.replace("'bounded_contact_diagnostic' in cmd","('bounded_contact_diagnostic' in cmd or 'bounded_contact_dispatch' in cmd)")
ns={'__name__':'_bounded_dispatch_v3','__file__':__file__};exec(compile(text,__file__+'::qualified_ordering_only','exec'),ns)
if __name__=='__main__':
    if len(sys.argv)>=4 and sys.argv[1]=='prepare':ns['prepare'](sys.argv[2],int(sys.argv[3]),sys.argv[4] if len(sys.argv)>4 else None)
    elif len(sys.argv)==3 and sys.argv[1]=='run':ns['run'](sys.argv[2])
    else:raise ValueError('prepare NAME CAP [SEED_DIAGNOSTIC] | run NAME')
