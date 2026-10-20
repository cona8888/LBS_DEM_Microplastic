"""Consume only the freshly decoded private JSON wrapper during reconstruction.

The public unpack operation still deep-copies caller-owned values. The path-
based reader receives a new, uncached JSON tree from the frozen bounded reader;
its enclosing wrapper is never exposed. Copying that whole tree again is not
needed. Every referenced-system copy, range check and original hash remains.
"""
from pathlib import Path
import ast,inspect,importlib.util,sys
ROOT=Path(__file__).resolve().parents[1]
source=Path(__file__).with_name('transaction_json_memo_v1.py')
spec=importlib.util.spec_from_file_location('_stage199_owned_decode_memo',source)
memo_storage=importlib.util.module_from_spec(spec);sys.modules[spec.name]=memo_storage;spec.loader.exec_module(memo_storage)
base,codec,instance=memo_storage.base,memo_storage.codec,memo_storage.instance
raw_bytes=memo_storage.raw_bytes
tree=ast.parse(inspect.getsource(instance.unpack));changes=0
tree.body[0].name='_consume_fresh_wrapper'
class Owned(ast.NodeTransformer):
    def visit_Assign(self,node):
        global changes
        if ast.unparse(node)=="env = copy.deepcopy(wrapper['packed_envelope'])":
            node.value=ast.parse("wrapper['packed_envelope']",mode='eval').body;changes+=1
        return self.generic_visit(node)
Owned().visit(tree)
if changes!=1:raise RuntimeError('one owned-root copy elision, no inner copy or check removed')
ast.fix_missing_locations(tree);ns={**instance.__dict__};exec(compile(tree,__file__+'::owned_fresh_json','exec'),ns)
_consume_fresh_wrapper=ns['_consume_fresh_wrapper']
fresh_reader=instance.base.read_record

def read_envelope(path,design):
    # The only call site: new JSON object owned by this stack frame, no memo or
    # producer state. No caller-supplied wrapper can enter this private path.
    return _consume_fresh_wrapper(fresh_reader(path,design))

instance.read_envelope=read_envelope;codec.base.read_record=read_envelope

def verify_bindings():
    memo_storage.verify_bindings()
    assert fresh_reader is instance.base.read_record is base.read_record
    assert instance.unpack.__code__==memo_storage.original.unpack.__code__
    assert codec.base.read_record is instance.read_envelope is read_envelope
    assert _consume_fresh_wrapper.__globals__['base'] is instance.base

def __getattr__(name):return getattr(memo_storage,name)

verify_bindings()
