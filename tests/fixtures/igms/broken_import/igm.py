"""Fixture: raises at import time. ``discover()`` must log + skip it."""

raise RuntimeError("this IGM explodes on import")
