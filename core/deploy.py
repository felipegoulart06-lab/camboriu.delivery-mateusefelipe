"""Ajustes de hospedagem: Vercel (serverless) e pooler do Supabase."""

from urllib.parse import urlsplit, urlunsplit


VERCEL_PREVIEW_HOST = ".vercel.app"
VERCEL_PREVIEW_ORIGIN = "https://*.vercel.app"
SUPABASE_TRANSACTION_PORT = "6543"


def on_vercel(env):
    return bool(env.get("VERCEL") or env.get("VERCEL_ENV"))


def comando_dispensa_banco(argv):
    """O collectstatic só empacota CSS/JS. Na Vercel isso roda no build, antes do runtime, sem Postgres."""
    return (argv[1] if len(argv) > 1 else "") == "collectstatic"


def inspecao_de_build(env, argv=None):
    """Build da Vercel: collectstatic e a leitura do manage.py rodam sem SECRET_KEY/DATABASE_URL.

    A Vercel marca o build com CI=1. No runtime da função isso não vem, então o pedido
    real continua exigindo as variáveis de produção.
    """
    if comando_dispensa_banco(argv or []):
        return True
    return on_vercel(env) and str(env.get("CI") or "").strip() in {"1", "true", "yes"}


def env_value(env, name, default=""):
    """Na Vercel variável definida em branco conta como ausente — o padrão do getenv não cobre isso."""
    valor = env.get(name)
    if valor is None:
        return default
    texto = str(valor).strip().strip('"').strip("'")
    return texto if texto else default


def env_flag(env, name, default=False):
    valor = env.get(name)
    if valor is None or not str(valor).strip():
        return bool(default)
    return str(valor).strip().lower() in {"1", "true", "yes", "on"}


def env_int(env, name, default):
    texto = env_value(env, name, "")
    if not texto:
        return int(default)
    return int(texto)


def env_float(env, name, default):
    texto = env_value(env, name, "")
    if not texto:
        return float(default)
    return float(texto)


def debug_default(env):
    """Na Vercel o padrão é produção (DEBUG desligado), na máquina local é o contrário."""
    return not on_vercel(env)


def extra_hosts(env):
    """Hosts que a Vercel injeta a cada deploy (produção e preview)."""
    hosts = []
    for chave in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        valor = (env.get(chave) or "").strip().removeprefix("https://").removeprefix("http://").split("/")[0]
        if valor and valor not in hosts:
            hosts.append(valor)
    if on_vercel(env) and VERCEL_PREVIEW_HOST not in hosts:
        hosts.append(VERCEL_PREVIEW_HOST)
    return hosts


def extra_origins(env):
    origens = []
    for host in extra_hosts(env):
        if host.startswith("."):
            origens.append(f"https://*{host}")
            continue
        origem = f"https://{host}"
        if origem not in origens:
            origens.append(origem)
    if on_vercel(env) and VERCEL_PREVIEW_ORIGIN not in origens:
        origens.append(VERCEL_PREVIEW_ORIGIN)
    return origens


def merge_unique(atual, extra):
    visto = {item.lower() if isinstance(item, str) else item for item in atual}
    saida = list(atual)
    for item in extra:
        chave = item.lower() if isinstance(item, str) else item
        if chave not in visto:
            saida.append(item)
            visto.add(chave)
    return saida


def serverless_database(config, env):
    """Na Vercel cada request é um processo novo: conexão persistente esgota o pooler.

    O pooler do Supabase na 5432 é modo sessão; a 6543 é modo transação, o certo
    para serverless. Se a URL ainda aponta para 5432 no host do pooler, trocamos.
    """
    if not on_vercel(env) or config.get("ENGINE", "").endswith("sqlite3"):
        return config
    ajustado = dict(config)
    opcoes = dict(ajustado.get("OPTIONS") or {})
    host = ajustado.get("HOST") or ""
    if "pooler.supabase.com" in host and str(ajustado.get("PORT")) == "5432":
        ajustado["PORT"] = SUPABASE_TRANSACTION_PORT
    ajustado["CONN_MAX_AGE"] = 0
    ajustado["CONN_HEALTH_CHECKS"] = False
    ajustado["DISABLE_SERVER_SIDE_CURSORS"] = True
    ajustado["OPTIONS"] = opcoes
    return ajustado


def database_url_for_vercel(url, env):
    """Mesma troca de porta, para quem inspeciona a URL em vez do dict do Django."""
    if not url or not on_vercel(env):
        return url
    partes = urlsplit(url)
    if "pooler.supabase.com" in (partes.hostname or "") and partes.port == 5432:
        netloc = partes.netloc.replace(":5432", f":{SUPABASE_TRANSACTION_PORT}")
        return urlunsplit((partes.scheme, netloc, partes.path, partes.query, partes.fragment))
    return url
