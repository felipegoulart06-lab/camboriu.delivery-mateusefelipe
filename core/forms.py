"""Peças compartilhadas pelos formulários longos de cadastro."""
from django import forms

from .uploads import ALLOWED_EXTENSIONS

ACCEPT = ",".join(f".{extension}" for extension in ALLOWED_EXTENSIONS)


class DateInput(forms.DateInput):
    input_type = "date"


class SectionedFormMixin:
    """Divide um formulário grande em blocos com título, para caber na tela sem virar uma parede de campos."""

    SECTIONS = ()
    WIDE_WIDGETS = (forms.Textarea,)

    def field_css(self, bound):
        widget = bound.field.widget
        if isinstance(widget, forms.CheckboxInput):
            return "check"
        if isinstance(widget, self.WIDE_WIDGETS):
            return "wide"
        if isinstance(widget, forms.FileInput):
            return "file"
        return ""

    def document_url(self, name):
        """Endereço protegido do anexo já salvo. Cada formulário aponta para a rota do seu painel."""
        return ""

    def _item(self, bound):
        is_document = bound.name in getattr(self, "DOCUMENT_FIELDS", ())
        saved = getattr(self.instance, bound.name, None) if is_document and hasattr(self, "instance") else None
        return {
            "field": bound,
            "css": self.field_css(bound),
            "saved": saved or None,
            "saved_url": self.document_url(bound.name) if saved else "",
        }

    @property
    def sections(self):
        blocks, used = [], set()
        for title, description, names in self.SECTIONS:
            items = [self._item(self[name]) for name in names if name in self.fields]
            if not items:
                continue
            used.update(item["field"].name for item in items)
            blocks.append({"title": title, "description": description, "items": items})
        leftovers = [self._item(bound) for bound in self if bound.name not in used and not bound.is_hidden]
        if leftovers:
            blocks.append({"title": "Outras informações", "description": "", "items": leftovers})
        return blocks


class DocumentUploadMixin:
    """Anexos: obrigatórios no primeiro cadastro e mantidos quando o formulário é reaberto para edição."""

    DOCUMENT_FIELDS = ()
    REQUIRED_DOCUMENTS = ()

    def setup_documents(self):
        for name in self.DOCUMENT_FIELDS:
            field = self.fields.get(name)
            if not field:
                continue
            field.widget.attrs.setdefault("accept", ACCEPT)
            field.required = False

    def validate_documents(self, required=None):
        """Cobra o anexo apenas quando ainda não existe arquivo salvo."""
        for name in required if required is not None else self.REQUIRED_DOCUMENTS:
            if name not in self.fields:
                continue
            if self.cleaned_data.get(name) or getattr(self.instance, name, None):
                continue
            self.add_error(name, "Envie este documento para concluir o cadastro.")


def mark_required(form, names):
    for name in names:
        if name in form.fields:
            form.fields[name].required = True
