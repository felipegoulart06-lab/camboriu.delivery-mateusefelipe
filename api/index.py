"""Compatibilidade: a Vercel resolve o Django por config/wsgi.py (WSGI_APPLICATION)."""
from config.wsgi import application

app = application
