"""Namespace-corrected adapter for Stage26o layered-pluviation Design 03."""
from __future__ import print_function

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(os.environ.get("STAGE26O_MIXTURE_SCRIPT", __file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ADAPTER_PATH = os.path.join(HERE, "run_stage26o_layered_two_fibre_mixture_v2.py")
SPEC = importlib.util.spec_from_file_location("stage26o_layered_adapter_v2", ADAPTER_PATH)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)

# YADE injects O and wrapper classes into this top-level script.  Propagate the
# live namespace through every imported layer before entering the v1 state
# machine.  The v2 failure omitted the two nested targets below.
targets = [adapter.mixture, adapter.mixture.control, adapter.mixture.core]
for target in targets:
    for symbol, value in list(globals().items()):
        if not symbol.startswith("__") and symbol not in {"adapter", "SPEC", "target", "targets"}:
            target.__dict__.setdefault(symbol, value)

if __name__ == "__main__":
    if os.environ.get("STAGE26O_NAMESPACE_SMOKE") == "1":
        status = {
            "mixture_has_O": hasattr(adapter.mixture, "O"),
            "control_has_O": hasattr(adapter.mixture.control, "O"),
            "core_has_O": hasattr(adapter.mixture.core, "O"),
        }
        if not all(status.values()):
            raise RuntimeError("YADE namespace propagation smoke failed: " + repr(status))
        print("STAGE26O_NAMESPACE_SMOKE=" + repr(status), flush=True)
    else:
        adapter.mixture.main()
