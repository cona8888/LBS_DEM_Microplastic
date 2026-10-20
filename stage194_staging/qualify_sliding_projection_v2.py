"""Repeat exact v1 qualification contract for analytic-Jacobian v2 only."""
from pathlib import Path
import types
import qualify_sliding_projection_v1 as old
import sliding_projection_repair_v2 as repair

namespace=dict(old.run.__globals__)
namespace.update(repair=repair,__file__=__file__,OUT=old.BASE/'sliding_qualification_02',
                 DESIGN=old.q.ROOT/'stage194_designs/evidence_repair_20260924/sliding_qualification_02.json')
run=types.FunctionType(old.run.__code__,namespace,'run',old.run.__defaults__,old.run.__closure__)

if __name__=='__main__':run()
