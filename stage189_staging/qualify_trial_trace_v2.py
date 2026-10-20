"""Pre-execution harness correction: capture the actual runtime `_calls` list.

Version 1 and its frozen design are retained without execution. The runtime's
call ledger is not reconstructed from observer evidence in this version.
"""
import ast
import inspect
import sys
import qualify_trial_trace_v1 as original


def build():
    tree = ast.parse(inspect.getsource(original.replay))
    changed = removed = 0
    class Correct(ast.NodeTransformer):
        def visit_Attribute(self, node):
            nonlocal changed
            if node.attr == 'calls' and ast.unparse(node.value) == 'job.parent.engine.runtime':
                node.attr = '_calls'; changed += 1
            return self.generic_visit(node)
        def visit_Assign(self, node):
            nonlocal removed
            if len(node.targets) == 1 and ast.unparse(node.targets[0]) == "record['result']['stage119_repair_calls']":
                removed += 1
                return None
            return self.generic_visit(node)
    Correct().visit(tree)
    tree.body[0].body[:0] = ast.parse('job.parent.engine.runtime._calls.clear()').body
    if changed != 1 or removed != 1:
        raise RuntimeError('expected only runtime ledger harness corrections')
    ast.fix_missing_locations(tree)
    namespace = dict(original.__dict__)
    exec(compile(tree, __file__+'::real_runtime_calls', 'exec'), namespace)
    return namespace['replay']


original.replay = build()
original.DESIGN = original.DESIGN.with_name('design_02.json')
original.OUT = original.OUT.with_name('zero_step_02')
if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']: original.prepare()
    elif sys.argv[1:] == ['run']: original.run()
    else: raise ValueError('prepare or run')
