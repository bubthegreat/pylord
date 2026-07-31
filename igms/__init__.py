"""Bundled IGMs -- in-game modules the engine loads at startup.

A regular package, not a namespace package, so each IGM below is a real
subpackage and can be split across several modules that import each other.
See ``igms/README.md`` for the plugin contract, and
``pylord/igm_loader.py`` for how these are discovered.
"""
