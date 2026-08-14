"""A Vercel resolve o Django por WSGI_APPLICATION; este arquivo só reexporta."""
from config.wsgi import app, application  # noqa: F401
