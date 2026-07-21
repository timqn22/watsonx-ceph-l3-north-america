"""Shared rate-limiter instance.

Kept in its own module to avoid a circular import between main.py (which
imports the API router) and api.py (which needs the limiter).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
