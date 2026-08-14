"""Blindagem do banco no Supabase.

O Supabase publica automaticamente o schema `public` numa API REST (PostgREST) que os
papéis `anon` e `authenticated` acessam com a chave pública do projeto. Como quem fala com
o banco aqui é só o Django, esses papéis não podem enxergar nada: CPF, CNH, contrato social
e foto de checklist ficariam a um `curl` de distância.

Este módulo liga RLS em todas as tabelas e tira o acesso desses papéis ao schema. Roda
sozinho depois de cada `migrate` (ver `core/apps.py`) e é seguro repetir quantas vezes quiser.
"""

import logging

logger = logging.getLogger("camboriu.security")

EXPOSED_ROLES = ("anon", "authenticated")

HARDENING_SQL = """
DO $$
DECLARE
    alvo record;
    papel text;
BEGIN
    -- 1. RLS ligada em tudo. Sem policy nenhuma, o resultado é "ninguém lê", exceto os
    -- papéis com BYPASSRLS (postgres/service_role), que é justamente por onde o Django entra.
    FOR alvo IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', alvo.relname);
    END LOOP;

    -- 2. Nem chega a testar RLS: os papéis da API pública perdem o acesso ao schema.
    FOREACH papel IN ARRAY ARRAY['anon', 'authenticated']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', papel);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', papel);
            EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', papel);
            EXECUTE format('REVOKE ALL ON SCHEMA public FROM %I', papel);
            -- Vale também para as tabelas que as próximas migrações criarem.
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', papel);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', papel);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', papel);
        END IF;
    END LOOP;

    -- 3. Revogar de anon e authenticated não basta: os dois herdam de PUBLIC, que por
    -- padrão pode usar o schema e executar toda função criada nele. As extensões do
    -- Supabase moram em outros schemas, então aqui isso não atinge nada de fora.
    REVOKE ALL ON SCHEMA public FROM PUBLIC;
    REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM PUBLIC;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
END $$;
"""

AUDIT_SQL = """
SELECT
    (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public' AND c.relkind = 'r') AS tabelas,
    (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity) AS sem_rls,
    (SELECT count(*) FROM information_schema.role_table_grants
      WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated', 'PUBLIC')) AS permissoes_publicas,
    -- Herança via PUBLIC: mesmo sem grant direto, anon pode enxergar o schema e chamar funções.
    (SELECT count(*) FROM (SELECT unnest(ARRAY['anon', 'authenticated']) AS papel) p
      WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = p.papel)
        AND has_schema_privilege(p.papel, 'public', 'USAGE')) AS schema_visivel,
    (SELECT count(*) FROM pg_proc pr JOIN pg_namespace n ON n.oid = pr.pronamespace
      WHERE n.nspname = 'public'
        AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
        AND has_function_privilege('anon', pr.oid, 'EXECUTE')) AS funcoes_expostas
"""


def harden(connection):
    """Aplica a blindagem. Devolve None fora do PostgreSQL (SQLite dos testes)."""
    if connection.vendor != "postgresql":
        return None
    with connection.cursor() as cursor:
        cursor.execute(HARDENING_SQL)
    return audit(connection)


def audit(connection):
    """Conta tabelas sem RLS e permissões sobrando para os papéis da API pública."""
    if connection.vendor != "postgresql":
        return None
    with connection.cursor() as cursor:
        cursor.execute(AUDIT_SQL)
        tabelas, sem_rls, permissoes, schema_visivel, funcoes = cursor.fetchone()
    return {
        "tabelas": tabelas,
        "sem_rls": sem_rls,
        "permissoes_publicas": permissoes,
        "schema_visivel": schema_visivel,
        "funcoes_expostas": funcoes,
    }


def harden_after_migrate(sender, using=None, **kwargs):
    from django.db import connections

    connection = connections[using or "default"]
    if connection.vendor != "postgresql":
        return
    relatorio = harden(connection)
    logger.info(
        "Banco blindado: %s tabelas, %s sem RLS, %s permissões públicas, "
        "%s papéis enxergando o schema, %s funções expostas",
        relatorio["tabelas"], relatorio["sem_rls"], relatorio["permissoes_publicas"],
        relatorio["schema_visivel"], relatorio["funcoes_expostas"],
    )
