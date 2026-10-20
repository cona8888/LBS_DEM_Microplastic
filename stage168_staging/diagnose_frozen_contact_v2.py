"""Fixed-pose capture with the runner's exact buoyant-load arithmetic order.

Version 1 multiplied density before constructing volume, unlike the frozen
integrator. Its failed replay remains preserved. No integration is called.
"""
import ast
import inspect
import sys
import diagnose_frozen_contact_v1 as capture


def exact_replay():
    tree=ast.parse(inspect.getsource(capture.diag.replay))
    matches=0
    class ExactLoad(ast.NodeTransformer):
        def visit_Assign(self,node):
            nonlocal matches
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='load':
                matches+=1
                return ast.parse('volume = 4 * np.pi * a * b * b / 3\nload = np.r_[(rhop-rhof) * volume * core.mechanics.finite(cfg["gravity_m_s2"]), np.zeros(3)]').body
            return self.generic_visit(node)
    ExactLoad().visit(tree)
    if matches!=1:raise RuntimeError('replay load structure changed')
    ast.fix_missing_locations(tree)
    namespace=dict(capture.diag.__dict__)
    exec(compile(tree,'<Stage168:exact_frozen_volume_order>','exec'),namespace)
    return namespace['replay']


capture.diag.replay=exact_replay()
capture.DESIGN=capture.DESIGN.with_name('design_02.json')
capture.OUT=capture.OUT.with_name('capture_02')
if __name__=='__main__':
    if sys.argv[1:]==['prepare']:capture.prepare()
    elif sys.argv[1:]==['run']:capture.run()
    else:raise ValueError('prepare or run')
