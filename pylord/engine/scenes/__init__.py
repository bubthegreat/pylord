"""Import every scene module so ``@scene(...)`` registration runs.

Anything that needs the full ``SCENES`` registry populated (the telnet
server entrypoint, tests/harness.py) should ``import pylord.engine.scenes``
before calling ``run_session``.
"""

from pylord.engine.scenes import stats, town

__all__ = ["stats", "town"]
