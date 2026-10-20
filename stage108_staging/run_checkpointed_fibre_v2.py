"""Serialization-only adapter; immutable numerical runner and bindings unchanged."""
import json,hashlib
import run_checkpointed_fibre_v1 as original
def safe_hash(state):
    return hashlib.sha256(json.dumps(state,sort_keys=True,allow_nan=True,default=original.h.json_value).encode()).hexdigest()
if __name__=='__main__':
    original.sha_state=safe_hash
    original.main()
