"""Exact standard-library JSON with C-encoded numeric leaf lists.

Only one branch is added to the original Python encoder; all other paths use
its unchanged code. No number representation, key ordering, whitespace, NaN,
default handling or logical record schema is changed. No global monkeypatch.
"""
import ast, inspect, json, textwrap

source=inspect.getsource(json.encoder._make_iterencode)
tree=ast.parse(source);patched=0
branch=ast.parse(textwrap.dedent('''
if (_indent == '  ' and lst and type(lst) in (list, tuple)
        and all(type(v) in (int, float) for v in lst)):
    compact = _numeric_dumps(lst)
    inner = '\\n' + _indent * (_current_indent_level + 1)
    closing = '\\n' + _indent * _current_indent_level
    yield '[' + inner + compact[1:-1].replace(',', _item_separator + inner) + closing + ']'
    return
''')).body[0]
for node in ast.walk(tree):
    if isinstance(node,ast.FunctionDef) and node.name=='_iterencode_list':
        node.body.insert(0,branch);patched+=1
if patched!=1:raise RuntimeError('exactly one standard leaf-list encoder required')
ast.fix_missing_locations(tree)

def numeric_dumps(v):
    return json.dumps(v,ensure_ascii=True,allow_nan=True,separators=(',',':'))

namespace={**json.encoder.__dict__,'_numeric_dumps':numeric_dumps}
exec(compile(tree,__file__+'::numeric_leaf_only','exec'),namespace)
factory=namespace['_make_iterencode']

class Encoder(json.JSONEncoder):
    def iterencode(self,o,_one_shot=False):
        markers={} if self.check_circular else None
        enc=json.encoder.encode_basestring_ascii if self.ensure_ascii else json.encoder.encode_basestring
        def floatstr(x,allow_nan=self.allow_nan):
            if x!=x:s='NaN'
            elif x==float('inf'):s='Infinity'
            elif x==-float('inf'):s='-Infinity'
            else:return float.__repr__(x)
            if not allow_nan:raise ValueError('Out of range float values are not JSON compliant')
            return s
        # This class is private to the exact original allow_nan/indent2 format.
        if self.indent!=2 or not self.allow_nan:raise ValueError('frozen canonical format required')
        return factory(markers,self.default,enc,self.indent,floatstr,self.key_separator,self.item_separator,self.sort_keys,self.skipkeys,_one_shot)(o,0)

def dumps(value,default):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=True,default=default,cls=Encoder)+'\n').encode('utf-8')
