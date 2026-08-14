from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from core.db_security import harden_after_migrate

        # O sinal dispara uma vez, com todas as tabelas já criadas, então toda migração
        # nova nasce com RLS ligada e sem acesso pela API pública do Supabase.
        post_migrate.connect(harden_after_migrate, sender=self, dispatch_uid="core.harden_database")
