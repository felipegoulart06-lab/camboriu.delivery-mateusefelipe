"""Se o deploy subiu sem SECRET_KEY ou DATABASE_URL, responde 503 em vez de derrubar a função."""
from django.conf import settings
from django.http import HttpResponse


def pagina_de_deploy(falhas):
    itens = "".join(f"<li><code>{nome}</code></li>" for nome in falhas)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Configuração pendente · Camboriú Delivery</title>
  <style>
    body {{ font-family: sans-serif; max-width: 40rem; margin: 12vh auto; padding: 0 1.5rem; line-height: 1.5; color: #102017; }}
    code {{ background: #eef3ef; padding: .1rem .35rem; border-radius: 4px; }}
    li {{ margin: .35rem 0; }}
  </style>
</head>
<body>
  <h1>Falta configurar a Vercel</h1>
  <p>O site subiu, mas a função não tem as variáveis de produção. Em
  <strong>Settings → Environment Variables</strong> cadastre:</p>
  <ul>{itens}</ul>
  <p><code>SECRET_KEY</code> é a chave longa do <code>.env</code> local.
  <code>DATABASE_URL</code> é a URI do pooler do Supabase na porta <strong>6543</strong>.</p>
  <p>Marque Production e Preview, salve e faça um novo deploy.</p>
</body>
</html>
"""


class DeployGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        falhas = getattr(settings, "FALHAS_DE_DEPLOY", [])
        if falhas:
            return HttpResponse(pagina_de_deploy(falhas), status=503, content_type="text/html; charset=utf-8")
        return self.get_response(request)
