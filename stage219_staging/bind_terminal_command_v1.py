"""Seal only independently qualified terminal commands, not a terminal evaluation."""
from pathlib import Path
import ast,sys
import terminal_ledger_adapter_v1 as a
import run_terminal_evaluator_v2 as witness
api,job=a.api,a.job
OUT=job.OUT/'terminal_command_binding_01'
def run(expected):
    p=a.frozen.sealed(a.PROOF);api.verify_mapping(p['inputs'])
    api.require(p['passed'] and p['design_sha256']==expected and len(p['corrupt_ledgers_rejected'])==7,'qualified actual terminal accounting bridge')
    # Compare all original witness assertions exactly, after its explicit
    # campaign-name and command-only substitutions. No physics or step runs.
    original=(a.frozen.ROOT/'stage209_staging/run_terminal_evaluator_v1.py').read_text()
    def assertions(text):return [ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='require']
    api.require(assertions(original)==assertions(witness.source),'every original exclusivity/lifecycle/cutoff witness guard retained')
    fn=witness.ns['run'];api.require(str(fn.__code__.co_filename).endswith('::same_exclusive_cutoff_witness'),'actual generated witness function association')
    api.require("'evaluate','campaign'" not in witness.source.split('command=')[1].split('\n')[0]
        and 'evaluate_normal_gap_campaign_v2.py' in witness.source,'only corrected terminal command executes')
    files=[Path(__file__),Path(a.__file__),Path(witness.__file__),Path(witness.__file__).with_name('evaluate_normal_gap_campaign_v2.py'),a.PROOF,a.PROOF.parent/'completion.json',job.DESIGN,job.WORK]
    r=dict(passed=True,new_trajectory_steps=0,design_sha256=expected,original_witness_guards_exact=True,terminal_assembler_code_unchanged=True,
        frozen_v1_evaluator_and_witness_unrun_not_failed=True,inputs={str(p):api.sha(p) for p in files},claim='New versioned terminal command bound after zero-step actual ledger qualification. Live production and frozen files unchanged; evaluator/witness not launched.')
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
    print('TERMINAL_COMMAND_BOUND',api.sha(OUT/'results.json'),flush=True)
if __name__=='__main__':run(sys.argv[1])
