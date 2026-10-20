"""Private exact Stage198 codec with only canonical encoder replaced."""
from pathlib import Path
import importlib.util,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage198_staging'))
import canonical_json_tokens_v1 as canonical
source=ROOT/'stage198_staging/fast_storage_v1.py'
spec=importlib.util.spec_from_file_location('_stage199_token_storage',source)
prior=importlib.util.module_from_spec(spec);sys.modules[spec.name]=prior;spec.loader.exec_module(prior)
prior.canonical=canonical
base,original,previous,instance,codec=prior.base,prior.original,prior.previous,prior.instance,prior.codec
raw_bytes=prior.raw_bytes
def verify_bindings():
    prior.verify_bindings()
    assert prior.canonical is canonical and raw_bytes.__globals__['canonical'] is canonical
verify_bindings()
