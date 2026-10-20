#!/usr/bin/env python3
from __future__ import print_function

import json

collider = InsertionSortCollider([Bo1_GridConnection_Aabb()])
print(json.dumps({
    "class": collider.__class__.__name__,
    "dict": collider.dict(),
    "avoidSelfInteractionMask_doc": getattr(InsertionSortCollider, "avoidSelfInteractionMask").__doc__,
    "attributes": [name for name in dir(collider) if "self" in name.lower() or "mask" in name.lower() or "interaction" in name.lower()],
}, indent=2, sort_keys=True, default=str))
