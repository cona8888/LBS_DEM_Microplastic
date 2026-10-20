"""Same frozen canonical tests; native whitespace implementation only."""
from pathlib import Path
from types import FunctionType
import qualify_canonical_tokens_v1 as tests
import native_storage_v1 as candidate
DESIGN=tests.DESIGN.with_name('canonical_native_01.json');OUT=tests.OUT.with_name('canonical_native_01')
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
main=FunctionType(tests.main.__code__,ns,tests.main.__name__,tests.main.__defaults__,tests.main.__closure__)
if __name__=='__main__':main()
