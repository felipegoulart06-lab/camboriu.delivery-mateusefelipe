"""Anexos dos cadastros: caminhos, limites e entrega protegida dos arquivos."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.utils.deconstruct import deconstructible

ALLOWED_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "pdf")


def _extension(filename):
    return filename.rsplit(".", 1)[-1].lower()[:5] if "." in filename else "bin"


@deconstructible
class document_path:  # noqa: N801 - usado como upload_to, precisa ser serializável nas migrações
    """Guarda cada anexo na pasta da empresa dona do cadastro."""

    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        owner = getattr(instance, "company_id", None) or instance.pk or "novos"
        return f"documentos/{self.folder}/{owner}/{uuid.uuid4().hex[:10]}.{_extension(filename)}"

    def __eq__(self, other):
        return isinstance(other, document_path) and self.folder == other.folder

    def __hash__(self):
        return hash(self.folder)


def company_document_path(instance, filename):
    return f"documentos/empresas/{instance.slug or instance.pk or 'novas'}/{uuid.uuid4().hex[:10]}.{_extension(filename)}"


def validate_document_file(value):
    """Aceita foto ou PDF dentro do limite configurado."""
    if not value:
        return value
    name = getattr(value, "name", "")
    if _extension(name) not in ALLOWED_EXTENSIONS:
        raise ValidationError("Envie uma foto (JPG, PNG ou WEBP) ou um PDF.")
    size = getattr(value, "size", 0)
    limit = settings.CHECKLIST_MAX_PHOTO_MB * 1024 * 1024
    if size > limit:
        raise ValidationError(f"O arquivo deve ter no máximo {settings.CHECKLIST_MAX_PHOTO_MB} MB.")
    return value


def serve(instance, field_name, allowed):
    """Entrega o anexo só depois de conferir o acesso na view que chamou."""
    if field_name not in allowed:
        raise Http404("Documento desconhecido.")
    document = getattr(instance, field_name, None)
    if not document:
        raise Http404("Documento não enviado.")
    return FileResponse(document.open("rb"), filename=document.name.rsplit("/", 1)[-1])
