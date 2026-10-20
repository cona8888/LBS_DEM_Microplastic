"""Exact canonical leaf encoding and numeric equality factoring; private codec."""
from pathlib import Path
from types import SimpleNamespace
import ast, inspect, importlib.util, math, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage196_staging'))
import lossless_compact_xz_v1 as previous
import fast_canonical_json_v1 as canonical
base=previous.base;original=previous.original

def raw_bytes(value):
    return canonical.dumps(value,base.api.frozen.h.json_value)

def equivalent(a,b):
    if type(a) is float and type(b) is float:
        return (math.isnan(a) and math.isnan(b)) or (a==b and (a!=0. or math.copysign(1.,a)==math.copysign(1.,b)))
    if type(a) is type(b) and type(a) in (int,bool,str,type(None)):return a==b
    if type(a) in (list,tuple) and type(b) in (list,tuple):
        # Numeric matrices only; general structures retain the original exact
        # canonical comparison, including its circular/default handling.
        def numeric(x):return type(x) in (int,float) or type(x) in (list,tuple) and all(numeric(v) for v in x)
        if numeric(a) and numeric(b):return len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
    return base.raw_bytes(a)==base.raw_bytes(b)

spec=importlib.util.spec_from_file_location('_stage198_exact_fast_trial_codec',original.__file__)
instance=importlib.util.module_from_spec(spec);sys.modules[spec.name]=instance;spec.loader.exec_module(instance)
instance.base=SimpleNamespace(**vars(base));instance.base.raw_bytes=raw_bytes;instance.base.write_record=previous.write_record
tree=ast.parse(inspect.getsource(original.pack));count=0
class Edit(ast.NodeTransformer):
    def visit_Compare(self,node):
        global count
        if ast.unparse(node)=='base.raw_bytes(item[k]) == base.raw_bytes(saved[k])':
            count+=1;return ast.copy_location(ast.Call(func=ast.Name(id='_equivalent',ctx=ast.Load()),args=[ast.parse('item[k]',mode='eval').body,ast.parse('saved[k]',mode='eval').body],keywords=[]),node)
        return self.generic_visit(node)
Edit().visit(tree)
if count!=1:raise RuntimeError('one exact factoring equality replacement required')
ast.fix_missing_locations(tree);instance.__dict__['_equivalent']=equivalent
exec(compile(tree,__file__+'::exact_numeric_equality','exec'),instance.__dict__)
codec=instance.codec;codec.base.raw_bytes=raw_bytes

def verify_bindings():
    assert codec.base.write_record is instance.write_envelope and codec.base.read_record is instance.read_envelope
    assert codec.base.raw_bytes is raw_bytes and instance.base.raw_bytes is raw_bytes
    assert instance.unpack.__code__==original.unpack.__code__
    assert instance.base.write_record is previous.write_record
    for name in ('encode','decode','validate_prefix','write_record','read_record'):
        assert getattr(codec,name).__code__==getattr(original.codec,name).__code__

verify_bindings()
