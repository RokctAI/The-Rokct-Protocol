#!/usr/bin/env python3
"""
factory call_jules — thin redirect to The-Rokct-Protocol shared implementation.
"""
import os, sys

_here = os.path.dirname(os.path.abspath(__file__))
_rock_root = os.path.dirname(os.path.dirname(os.path.dirname(_here)))   # .rokct/
_workspace_parent = os.path.dirname(_rock_root)                       # parent of factory/

_candidates = [
    os.path.join(_workspace_parent, "The-Rokct-Protocol", "core",
                 "skills", "agent_delegation", "scripts"),
]

_search = os.path.dirname(_here)
for _ in range(5):
    _candidates.append(os.path.join(_search, "The-Rokct-Protocol", "core",
                                    "skills", "agent_delegation", "scripts"))
    _p = os.path.dirname(_search)
    if _p == _search: break
    _search = _p

_shared_dir = next((c for c in _candidates if os.path.isdir(c)), None)
if not _shared_dir:
    print("Error: The-Rokct-Protocol/core/skills/agent_delegation/scripts not found",
          file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, _shared_dir)
import delegate_to_agent   # shared canonical implementation
sys.exit(delegate_to_agent.main())
