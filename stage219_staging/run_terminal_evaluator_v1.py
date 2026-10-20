"""Same exclusive terminal witness; newly frozen normal-gap campaign association."""
from pathlib import Path
import normal_gap_campaign_v1 as s
api,job=s.api,s.job
source=(s.ROOT/'stage209_staging/run_terminal_evaluator_v1.py').read_text()
before='import cone_feasibility_campaign_v1 as s'
api.require(source.count(before)==1,'one exclusive frozen evaluator campaign association')
source=source.replace(before,'import normal_gap_campaign_v1 as s')
ns=dict(__name__='_stage219_exclusive_evaluator',__file__=__file__)
exec(compile(source,__file__+'::same_exclusive_terminal_witness','exec'),ns)
if __name__=='__main__':
    import sys
    ns['run'](sys.argv[1])
