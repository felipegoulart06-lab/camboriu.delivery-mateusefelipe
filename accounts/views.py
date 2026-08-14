from django.contrib import messages
from django.shortcuts import redirect, render

from core.models import Notification
from core.uploads import serve as serve_document
from operations.permissions import company_profile_required

from .forms import CompanyProfileForm
from .models import Company


@company_profile_required
def company_profile(request):
    """Cadastro obrigatório da empresa: sem ele o painel não libera as demais telas."""
    company = request.user.company
    first_time = not company.is_registered
    form = CompanyProfileForm(request.POST or None, request.FILES or None, instance=company)
    if request.method == "POST" and form.is_valid():
        company = form.save()
        if first_time:
            Notification.announce(
                Notification.Kind.COMPANY_REGISTERED,
                f"{company.name} concluiu o cadastro",
                company=company,
                body=f"{company.document_label} · {company.full_address or 'endereço não informado'}",
                url=f"/plataforma/empresas/{company.pk}/",
            )
            messages.success(request, "Cadastro concluído. Agora você já pode pedir retiradas.")
            return redirect("dashboard")
        messages.success(request, "Cadastro da empresa atualizado.")
        return redirect("company_profile")
    return render(request, "accounts/company_profile.html", {
        "form": form, "company": company, "first_time": first_time,
    })


@company_profile_required
def company_own_document(request, field):
    """Contrato social e comprovantes da própria empresa, sem expor a pasta de mídia."""
    return serve_document(request.user.company, field, Company.DOCUMENTS)
