"""Abre as páginas dos três painéis no banco configurado e reporta o status de cada uma.

Funciona em qualquer base (demonstração, local ou produção): as contas e os registros
usados nas URLs são descobertos na hora. Telas que dependem de um registro inexistente
são puladas, então uma operação recém-criada também pode ser varrida.
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from accounts.models import Company, User  # noqa: E402
from finance.models import DriverPayout, Invoice  # noqa: E402
from operations.models import Delivery, Driver, Vehicle  # noqa: E402


def primeiro(consulta):
    return consulta.first()


empresa = primeiro(Company.objects.clients().filter(registered_at__isnull=False))
entrega = primeiro(Delivery.objects.filter(company=empresa)) if empresa else None
entrega_confirmada = (
    primeiro(Delivery.objects.filter(company=empresa, master_confirmed_at__isnull=False)) if empresa else None
)
entregador = primeiro(Driver.objects.filter(company__is_platform=True).exclude(user=None))
corrida = primeiro(Delivery.objects.filter(driver=entregador)) if entregador else None
veiculo = primeiro(Vehicle.objects.filter(company__is_platform=True))
fatura = primeiro(Invoice.objects.filter(company=empresa)) if empresa else None
repasse = primeiro(DriverPayout.objects.filter(driver=entregador)) if entregador else None
usuario_da_empresa = primeiro(User.objects.filter(company=empresa)) if empresa else None

# (nome da rota, argumentos). Um argumento None faz a linha ser pulada.
PAINEL_MASTER = [
    ("platform_home", []), ("dispatch_board", []), ("platform_deliveries", []),
    ("company_list", []), ("company_create", []),
    ("company_detail", [empresa]), ("company_dossier", [empresa]), ("company_edit", [empresa]), ("company_user_create", [empresa]),
    ("company_user_edit", [empresa, usuario_da_empresa]), ("user_password", [usuario_da_empresa]),
    ("platform_team", []), ("platform_team_create", []),
    ("platform_drivers", []), ("platform_driver_create", []), ("platform_driver_edit", [entregador]),
    ("platform_driver_dossier", [entregador]),
    ("vehicle_list", []), ("vehicle_create", []), ("vehicle_edit", [veiculo]), ("vehicle_dossier", [veiculo]),
    ("dispatch_detail", [entrega]), ("dispatch_delivery", [entrega]), ("delivery_document", [entrega]),
    ("platform_delivery_create", []),
    ("finance_dashboard", []), ("finance_pricing", []), ("delivery_price", [entrega]),
    ("invoice_list", []), ("invoice_create", [empresa]),
    ("invoice_detail", [fatura]), ("invoice_bank_slip", [fatura]), ("invoice_document", [fatura]),
    ("payout_list", []), ("payout_create", []), ("payout_detail", [repasse]),
    ("notification_list", []), ("live_alerts", []),
    ("platform_integration", []), ("platform_integration_pdf", []),
]
# A central despacha, mas não cadastra empresas: /plataforma/empresas/ é só do admin master.
PAINEL_CENTRAL = [
    ("platform_home", []), ("dispatch_board", []), ("platform_deliveries", []), ("platform_drivers", []),
    ("platform_delivery_create", []),
    ("platform_driver_dossier", [entregador]), ("vehicle_dossier", [veiculo]),
    ("dispatch_detail", [entrega]),
    ("finance_dashboard", []), ("invoice_list", []), ("payout_list", []), ("notification_list", []),
    ("live_alerts", []), ("platform_integration", []),
]
PAINEL_EMPRESA = [
    ("dashboard", []), ("delivery_list", []), ("delivery_create", []),
    ("delivery_detail", [entrega]), ("company_delivery_document", [entrega_confirmada]),
    ("company_notifications", []), ("live_alerts", []),
    ("company_profile", []), ("company_own_dossier", []), ("company_billing", []), ("company_invoice_request", []),
    ("company_invoice_detail", [fatura]), ("company_invoice_document", [fatura]),
]
PAINEL_ENTREGADOR = [
    ("driver_home", []), ("driver_jobs", []), ("driver_history", []), ("driver_profile", []),
    ("driver_job_detail", [corrida]), ("driver_job_document", [corrida]),
]

VARREDURAS = [
    ("admin master", User.objects.filter(role=User.Role.MASTER, is_active=True), PAINEL_MASTER),
    ("central de despacho", User.objects.filter(role=User.Role.DISPATCHER, is_active=True), PAINEL_CENTRAL),
    ("empresa contratante", User.objects.filter(company=empresa, is_active=True) if empresa else User.objects.none(),
     PAINEL_EMPRESA),
    ("entregador", User.objects.filter(pk=entregador.user_id) if entregador else User.objects.none(),
     PAINEL_ENTREGADOR),
]

problemas = 0
pulados = 0
for titulo, contas, paginas in VARREDURAS:
    conta = contas.order_by("pk").first()
    if conta is None:
        print(f"\n=== {titulo}: nenhuma conta encontrada, varredura pulada ===")
        continue
    cliente = Client(SERVER_NAME="127.0.0.1")
    cliente.force_login(conta)
    print(f"\n=== {titulo}: {conta.username} ({conta.get_role_display()}) ===")
    for nome, objetos in paginas:
        if any(objeto is None for objeto in objetos):
            pulados += 1
            print(f"  -- ??? {nome} (sem registro para montar a URL)")
            continue
        url = reverse(nome, args=[getattr(objeto, "pk", objeto) for objeto in objetos])
        resposta = cliente.get(url)
        destino = f" -> {resposta.headers.get('Location')}" if resposta.status_code in (301, 302) else ""
        marca = "ok " if resposta.status_code == 200 else "!! "
        problemas += resposta.status_code != 200
        print(f"  {marca}{resposta.status_code} {url}{destino}")

resumo = "TUDO OK" if not problemas else f"{problemas} página(s) com problema"
print(f"\n{resumo}" + (f" ({pulados} pulada(s) por falta de registro)" if pulados else ""))
