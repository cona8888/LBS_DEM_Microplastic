"""Original exclusive witness assertions; only terminal command versioned."""
from pathlib import Path
import sys
import normal_gap_campaign_v1 as s
api,job=s.api,s.job
source=(s.ROOT/'stage209_staging/run_terminal_evaluator_v1.py').read_text()
changes={
    'import cone_feasibility_campaign_v1 as s':'import normal_gap_campaign_v1 as s',
    "command=[sys.executable,'-B','-u',str(job.SELF),'evaluate','campaign']":"command=[sys.executable,'-B','-u',str(Path(__file__).with_name('evaluate_normal_gap_campaign_v2.py')),expected]",
    "source_sha256=api.sha(job.SELF),threads=1":"source_sha256=api.sha(Path(__file__).with_name('evaluate_normal_gap_campaign_v2.py')),threads=1"
}
for before,after in changes.items():
    api.require(source.count(before)==1,'one exclusive versioned terminal command association')
    source=source.replace(before,after)
ns=dict(__name__='_stage219_terminal_witness_v2',__file__=__file__)
exec(compile(source,__file__+'::same_exclusive_cutoff_witness','exec'),ns)
if __name__=='__main__':
    b=s.sealed(job.OUT/'terminal_command_binding_01/results.json');api.verify_mapping(b['inputs'])
    api.require(b['passed'] and b['inputs'][str(Path(__file__))]==api.sha(__file__),'exact qualified exclusive witness source')
    proof=s.sealed(job.OUT/'terminal_ledger_qualification_01/results.json');api.verify_mapping(proof['inputs'])
    api.require(proof['passed'] and proof['design_sha256']==sys.argv[1],'qualified terminal-only command version')
    ns['run'](sys.argv[1])
