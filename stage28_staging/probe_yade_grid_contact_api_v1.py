#!/usr/bin/env python3
"""Read-only YADE API inventory for Stage28a grid-contact implementation."""

from __future__ import print_function

from yade import wrapper


names = sorted(
    name
    for name in dir(wrapper)
    if "GridConnection" in name or "GridNode" in name or "GridCo" in name
)
print("STAGE28A_YADE_GRID_API=" + repr(names))
