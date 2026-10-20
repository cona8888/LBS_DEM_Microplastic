"""New immutable local extension using the independently qualified v4 route."""
from pathlib import Path
import sys
import bounded_contact_dispatch_extension_v3 as prior
text=Path(prior.__file__).read_text()
replacements={
    'import bounded_contact_dispatch_v3 as harness':'import bounded_contact_dispatch_polish_v4 as harness',
    "'bounded_extension_01'":"'polish_bounded_extension_02'",
    "'bounded_extension_01.json'":"'polish_bounded_extension_02.json'",
    "'local_closure_01/results.json'":"'polish_extended_closure_02/results.json'",
    "'local_closure_01/completion.json'":"'polish_extended_closure_02/completion.json'",
    "closure['window_total_accepted_steps']":"closure['window_saved_steps']",
    '30277':'38813',
    '40277':'48813',
    "'dispatch_full_01'":"'polish_long_01'",
    "'extension_call%02d_01'":"'polish_extension_call%02d_01'",
}
for before,after in replacements.items():
    assert before in text,before
    text=text.replace(before,after)
ns={'__name__':'_bounded_polish_extension','__file__':__file__}
exec(compile(text,__file__+'::v4_route_and_unique_evidence','exec'),ns)
if __name__=='__main__':
    if sys.argv[1:]==['prepare']:ns['prepare']()
    elif sys.argv[1:]==['run']:ns['run']()
    else:raise ValueError('prepare | run')
