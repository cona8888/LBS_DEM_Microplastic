"""Independently re-audit longer v4 continuation and exact split restart."""
from pathlib import Path
import audit_polish_local_v1 as prior
text=Path(prior.__file__).read_text()
text=text.replace("OUT=BASE/'polish_local_closure_01'","OUT=BASE/'polish_extended_closure_02'")
text=text.replace("'polish_split_b_01')","'polish_split_b_01','polish_long_01','polish_long_split_a_01','polish_long_split_b_01')")
anchor="        api.require(all(comparisons.values()),'exact split restart, unchanged original successes, progress past failed local path')"
assert text.count(anchor)==1
extra="""        comparisons['long_split_all_rows_exact']=records['polish_long_01']['rows']==records['polish_long_split_a_01']['rows']+records['polish_long_split_b_01']['rows']
        comparisons['long_split_full_checkpoint_exact']=records['polish_long_01']['result']['checkpoint']==records['polish_long_split_b_01']['result']['checkpoint']
"""
text=text.replace(anchor,extra+anchor)
ns={'__name__':'_polish_extended_closure','__file__':__file__}
exec(compile(text,__file__+'::longer_same_gate_closure','exec'),ns)
if __name__=='__main__':ns['run']()
