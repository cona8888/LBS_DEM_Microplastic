"""Read-only frozen monitor with two independently diagnosed identity/digest repairs.

Only the full terminal checkpoint digest uses the original physical checkpoint
canonical JSON convention. Administrative binding digests remain unchanged.
"""
from pathlib import Path
import ast, hashlib, importlib, json, sys
import campaign_common_v1 as c
import monitor_recovery_v3 as identity

ORIGINAL = identity.ORIGINAL
ORIGINAL_SHA256 = identity.ORIGINAL_SHA256
IDENTITY_SHA256 = '91bbe3a0ddce9a66ab1b51a5f2feef5f4c2a3ba6a5b69c7e1ed9066e244e6cb6'
PHYSICAL_DIGEST_SOURCE = c.ROOT/'stage115_staging/corrected_transport_v1.py'
PHYSICAL_DIGEST_SOURCE_SHA256 = '43af4b93b3bfc495a929b93fd047202b64ccf2a45132d7b20e42449d77cf69cd'


def canonical_checkpoint_digest(value):
    # Finite JSON is mandatory; the original default separators are retained.
    json.dumps(value, sort_keys=True, allow_nan=False)
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def validate_terminal_checkpoint(checkpoint, expected, prefix, physical_sha):
    if (type(checkpoint) is not dict or set(checkpoint) != {'contract','schema','state','state_sha256'}
            or type(checkpoint['schema']) is not int or checkpoint['schema'] != 1
            or type(checkpoint['contract']) is not str or len(checkpoint['contract']) != 64
            or type(checkpoint['state']) is not dict):
        raise ValueError('Full original checkpoint schema and contract required')
    state = checkpoint['state']
    if canonical_checkpoint_digest(state) != checkpoint['state_sha256']:
        raise ValueError('Full original checkpoint state digest mismatch')
    history = state.get('history')
    if type(history) is not list:
        raise ValueError('Full checkpoint history list required')
    packed = json.dumps(history, separators=(',',':'), allow_nan=False).encode('utf-8')
    if (prefix['design_sha256'] != physical_sha or prefix['history_length'] != len(history)
            or prefix['history_sha256'] != hashlib.sha256(packed).hexdigest()):
        raise ValueError('Complete checkpoint history/prefix association mismatch')
    actual = canonical_checkpoint_digest(checkpoint)
    if actual != expected:
        raise ValueError('Full original checkpoint digest mismatch')
    return actual


def terminal_checkpoint_digest(checkpoint, folder, expected, physical_sha):
    prefix = c.read(folder/'prefix.json')
    row = c.sealed(folder/'results.json')
    entries = row['entries']
    if not entries:
        raise ValueError('Terminal checkpoint requires accepted production ancestry')
    segment = folder/('segment_%05d' % entries[-1]['segment'])
    receipt = c.sealed(segment/'results.json')
    if (entries[-1]['results_sha256'] != c.sha(segment/'results.json')
            or receipt['output_checkpoint_sha256'] != expected
            or receipt['summary']['output_checkpoint_state_sha256'] != checkpoint['state_sha256']
            or receipt['passed'] is not True or receipt['summary']['passed'] is not True
            or row['final_checkpoint_sha256'] != expected
            or row['time_s'] != checkpoint['state']['t']
            or row['cumulative_physical_steps'] != checkpoint['state']['steps']):
        raise ValueError('Exact terminal receipt/full state/clock association required')
    raw = segment/'call.json.xz'
    seal = c.read(segment/'call.json.seal.json')
    if (Path(prefix['path']).resolve() != raw.resolve()
            or prefix['compressed_sha256'] != seal['compressed_sha256']
            or prefix['design_sha256'] != seal['design_sha256']
            or receipt['artifacts'][str(raw)] != seal['compressed_sha256']
            or c.sha(raw) != seal['compressed_sha256']):
        raise ValueError('Exact terminal raw seal/prefix association required')
    return validate_terminal_checkpoint(checkpoint, expected, prefix, physical_sha)


def corrected_run_function(original):
    tree = ast.parse(ORIGINAL.read_text(encoding='utf-8'))
    run = next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name == 'run')
    replacements = 0
    class ReplaceTerminalDigest(ast.NodeTransformer):
        def visit_Call(self, node):
            nonlocal replacements
            if (isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name)
                    and node.func.value.id == 'c' and node.func.attr == 'digest'
                    and len(node.args) == 1 and not node.keywords
                    and ast.unparse(node.args[0]) == "read(folder / 'checkpoint.json')"):
                replacements += 1
                return ast.copy_location(ast.Call(func=ast.Name(id='terminal_checkpoint_digest',ctx=ast.Load()),
                    args=[node.args[0],ast.Name(id='folder',ctx=ast.Load()),ast.Name(id='checkpoint',ctx=ast.Load()),
                          ast.Name(id='physical_sha',ctx=ast.Load())],keywords=[]),node)
            return self.generic_visit(node)
    run = ReplaceTerminalDigest().visit(run)
    if replacements != 1:
        raise RuntimeError('Exactly one frozen terminal checkpoint digest call must be repaired')
    module = ast.fix_missing_locations(ast.Module(body=[run],type_ignores=[]))
    namespace = dict(original.__dict__)
    namespace['inspect_process'] = identity.inspect_process
    namespace['terminal_checkpoint_digest'] = terminal_checkpoint_digest
    exec(compile(module,str(Path(__file__).resolve()),'exec'), namespace)
    return namespace['run']


def run():
    c.bound(); c.environment()
    for path,wanted in ((ORIGINAL,ORIGINAL_SHA256),(Path(identity.__file__),IDENTITY_SHA256),
                         (PHYSICAL_DIGEST_SOURCE,PHYSICAL_DIGEST_SOURCE_SHA256)):
        if c.sha(path) != wanted: raise RuntimeError('Frozen original monitor/digest/identity source changed')
    plan = c.read(c.DESIGNS/'transport_design_03.json')
    if plan['source_files'][str(PHYSICAL_DIGEST_SOURCE)] != PHYSICAL_DIGEST_SOURCE_SHA256:
        raise RuntimeError('Original physical digest source must remain frozen in the plan')
    if c.sha(identity.RETIREMENT) != identity.RETIREMENT_SHA256:
        raise RuntimeError('Frozen initial retirement changed')
    retirement = c.sealed(identity.RETIREMENT)
    if retirement['passed'] is not True or retirement['all_exact_launch_identities_retired'] is not True:
        raise RuntimeError('Passing sealed initial retirement mandatory')
    original = importlib.import_module('monitor_recovery_v2')
    return corrected_run_function(original)()


if __name__ == '__main__':
    if sys.argv[1:]: raise ValueError('Monitor takes no arguments')
    run()
