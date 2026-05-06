"""Payments domain (core).

Core layer is PURE: it MUST NOT perform network calls or irreversible actions.
All provider I/O is done via EffectsPort inside runtime/_internal.
"""
