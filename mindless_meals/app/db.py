"""Shared SQLAlchemy instance.

Kept in its own module so models.py, seed.py, and api.py can all import
it without circular imports back to app.py.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
