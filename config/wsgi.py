"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sys
import traceback
from html import escape

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _falha_de_arranque(exc):
    traceback.print_exception(exc, file=sys.stderr)
    mensagem = escape(f"{type(exc).__name__}: {exc}")
    corpo = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Falha ao iniciar</title></head>
<body style="font-family:sans-serif;max-width:40rem;margin:12vh auto;padding:0 1.5rem">
<h1>A função não iniciou</h1>
<p>O painel caiu ao carregar o Django. Detalhe nos logs da Vercel:</p>
<pre style="white-space:pre-wrap;background:#eef3ef;padding:1rem;border-radius:8px">{mensagem}</pre>
</body></html>""".encode("utf-8")

    def application(environ, start_response):
        start_response("503 Service Unavailable", [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(corpo))),
        ])
        return [corpo]

    return application


try:
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
except Exception as exc:  # pragma: no cover - só dispara se o Django não carregar
    application = _falha_de_arranque(exc)

app = application
