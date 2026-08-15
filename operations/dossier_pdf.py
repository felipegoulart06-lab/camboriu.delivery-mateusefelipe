"""Dossiê cadastral em PDF: empresa, entregador e veículo, pronto para baixar."""
from io import BytesIO

from django.utils import timezone
from PIL import Image as PILImage
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from finance.pdf import LINE, STYLES, _document, _facts, texto

IMAGE_EXTS = {"jpg", "jpeg", "png", "webp"}
PHOTO_WIDTH = 78 * mm
PHOTO_HEIGHT = 58 * mm


def _blank(value):
    if value in (None, ""):
        return "—"
    return value


def _date(value):
    if not value:
        return "—"
    if hasattr(value, "hour"):
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")
    return value.strftime("%d/%m/%Y")


def _yes(value):
    return "Sim" if value else "Não"


def _file_status(field):
    if not field:
        return "pendente"
    name = (field.name or "").rsplit("/", 1)[-1]
    return f"anexado · {name}" if name else "anexado"


def _extension(name):
    return name.rsplit(".", 1)[-1].lower() if name and "." in name else ""


def _read_bytes(field):
    if not field:
        return b"", ""
    try:
        field.open("rb")
        data = field.read()
        name = field.name or ""
    except OSError:
        return b"", ""
    finally:
        try:
            field.close()
        except OSError:
            pass
    return data, name


def _photo(field, hold):
    data, name = _read_bytes(field)
    if not data or _extension(name) not in IMAGE_EXTS:
        return None
    try:
        picture = PILImage.open(BytesIO(data))
        picture.load()
        if picture.mode not in ("RGB", "L"):
            picture = picture.convert("RGB")
        encoded = BytesIO()
        picture.save(encoded, format="JPEG", quality=75, optimize=True)
        encoded.seek(0)
        hold.append(encoded)
        reader = ImageReader(encoded)
        width, height = reader.getSize()
        if not width or not height:
            return None
        scale = min(PHOTO_WIDTH / width, PHOTO_HEIGHT / height, 1)
        encoded.seek(0)
        return Image(encoded, width=width * scale, height=height * scale)
    except (OSError, ValueError):
        return None


def _header(eyebrow, title, subtitle=""):
    left = [
        Paragraph(texto(eyebrow), STYLES["eyebrow"]),
        Paragraph(texto(title), STYLES["title"]),
    ]
    if subtitle:
        left.append(Paragraph(texto(subtitle), STYLES["body"]))
    right = [
        Paragraph("<b>CAMBORIÚ DELIVERY</b>", STYLES["right"]),
        Paragraph("Dossiê cadastral", STYLES["right"]),
        Paragraph(f"Emitido em {timezone.localtime():%d/%m/%Y %H:%M}", STYLES["right"]),
    ]
    header = Table([[left, right]], colWidths=[105 * mm, 65 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, LINE),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return header


def _section(story, title, rows):
    story.append(Paragraph(f"<b>{title}</b>", STYLES["section"]))
    story.append(_facts(rows))


def _photos(story, hold, items):
    blocks = []
    for label, field in items:
        image = _photo(field, hold)
        if image is None:
            continue
        blocks.append(KeepTogether([
            Paragraph(texto(label), STYLES["cellhead"]),
            image,
            Spacer(1, 8),
        ]))
    if not blocks:
        return
    story.append(Paragraph("<b>Fotos anexadas</b>", STYLES["section"]))
    story.extend(blocks)


def _closing(story):
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Dossiê gerado pelo sistema Camboriú Delivery para arquivo da operação. "
        "Anexos em PDF continuam disponíveis nas telas de cadastro; as fotos enviadas "
        "entram neste documento.",
        STYLES["muted"],
    ))


def _build(title, story, hold):
    buffer = BytesIO()
    _document(buffer, title).build(story)
    buffer.seek(0)
    hold.clear()
    return buffer


def company_dossier_pdf(company, users=None, include_internal=True):
    """Ficha cadastral da empresa contratante, com anexos e acessos quando o master pede."""
    hold = []
    story = [
        _header("DOSSIÊ DA EMPRESA CONTRATANTE", company.billing_name, company.document_label),
        Spacer(1, 8),
        Paragraph(
            f"{'Ativa' if company.is_active else 'Suspensa'} · "
            f"{'cadastro concluído em ' + _date(company.registered_at) if company.is_registered else 'cadastro pendente'} · "
            f"cliente desde {_date(company.created_at)}",
            STYLES["body"],
        ),
    ]
    _section(story, "Identificação", [
        ("Nome fantasia", company.name),
        ("Razão social / nome", _blank(company.legal_name)),
        ("Documento", company.document_label),
        ("Inscrição estadual", _blank(company.state_registration)),
        ("Inscrição municipal", _blank(company.municipal_registration)),
        ("Regime tributário", _blank(company.get_tax_regime_display())),
        ("Data de abertura", _date(company.founded_on)),
        ("Ramo de atividade", _blank(company.business_area)),
        ("Fatura em boleto", _yes(company.can_invoice)),
    ])
    _section(story, "Responsável", [
        ("Nome", _blank(company.contact_name)),
        ("CPF", _blank(company.contact_document)),
        ("Cargo", _blank(company.contact_role)),
        ("E-mail", _blank(company.email)),
        ("Telefone", _blank(company.phone)),
    ])
    _section(story, "Endereço", [
        ("CEP", _blank(company.zip_code)),
        ("Logradouro e número", _blank(company.address)),
        ("Complemento", _blank(company.complement)),
        ("Bairro", _blank(company.district)),
        ("Cidade / UF", " / ".join(part for part in (company.city, company.state) if part) or "—"),
        ("Endereço completo", _blank(company.full_address)),
    ])
    _section(story, "Financeiro", [
        ("E-mail do financeiro", _blank(company.billing_email)),
        ("Telefone do financeiro", _blank(company.billing_phone)),
        ("Dia de vencimento preferido", str(company.invoice_due_day)),
        ("Contato para faturamento", _blank(company.billing_contact)),
    ])
    _section(story, "Documentos", [
        (company._meta.get_field(name).verbose_name, _file_status(getattr(company, name)))
        for name in company.DOCUMENTS
    ])
    if company.missing_documents:
        story.append(Paragraph(
            f"Pendentes: {', '.join(company.missing_documents)}.",
            STYLES["muted"],
        ))
    if include_internal:
        if users is not None:
            _section(story, "Acessos da empresa", [
                (
                    account.get_full_name() or account.username,
                    f"{account.email or account.username} · {account.get_role_display()} · "
                    f"{'ativo' if account.is_active else 'inativo'}",
                )
                for account in users
            ] or [("Acessos", "nenhum acesso criado")])
        if company.notes:
            _section(story, "Observações internas", [("Notas", company.notes)])
    _photos(story, hold, [
        (company._meta.get_field(name).verbose_name, getattr(company, name))
        for name in company.DOCUMENTS
    ])
    _closing(story)
    return _build(f"Dossie empresa {company.name}", story, hold)


def driver_dossier_pdf(driver):
    """Ficha cadastral do entregador, com habilitação, repasse e fotos."""
    hold = []
    login = ""
    if driver.user_id:
        login = driver.user.email or driver.user.username
    story = [
        _header("DOSSIÊ DO ENTREGADOR", driver.name, f"CPF {driver.cpf}"),
        Spacer(1, 8),
        Paragraph(
            f"{driver.get_status_display()} · {driver.get_contract_type_display()} · "
            f"cadastrado em {_date(driver.created_at)}",
            STYLES["body"],
        ),
    ]
    _section(story, "Identificação", [
        ("Nome completo", driver.name),
        ("CPF", driver.cpf),
        ("Nascimento", _date(driver.birth_date)),
        ("RG", _blank(driver.rg)),
        ("Órgão emissor do RG", _blank(driver.rg_issuer)),
        ("Nome da mãe", _blank(driver.mother_name)),
        ("Telefone", driver.phone),
        ("Contato de emergência", _blank(driver.emergency_contact)),
        ("Telefone de emergência", _blank(driver.emergency_phone)),
        ("Login do app", _blank(login)),
        ("Empresa da frota", driver.company.name),
    ])
    _section(story, "Endereço", [
        ("CEP", _blank(driver.zip_code)),
        ("Logradouro e número", _blank(driver.address)),
        ("Bairro", _blank(driver.district)),
        ("Cidade / UF", " / ".join(part for part in (driver.city, driver.state) if part) or "—"),
        ("Endereço completo", _blank(driver.full_address)),
    ])
    _section(story, "Habilitação", [
        ("Número da CNH", driver.cnh),
        ("Categoria", driver.cnh_category),
        ("Nº de registro", _blank(driver.cnh_register)),
        ("UF da CNH", _blank(driver.cnh_state)),
        ("Emissão", _date(driver.cnh_issued_at)),
        ("Primeira habilitação", _date(driver.cnh_first_license_at)),
        ("EAR", _yes(driver.cnh_has_ear)),
        ("Vencimento da CNH", _date(driver.cnh_expires_at)),
        ("Vencimento do exame", _date(driver.medical_exam_expires_at)),
    ])
    _section(story, "Vínculo e repasse", [
        ("Vínculo", driver.get_contract_type_display()),
        ("Chave Pix", _blank(driver.pix_key)),
        ("Banco", _blank(driver.bank_name)),
        ("Agência", _blank(driver.bank_agency)),
        ("Conta", _blank(driver.bank_account)),
    ])
    _section(story, "Documentos", [
        (driver._meta.get_field(name).verbose_name, _file_status(getattr(driver, name)))
        for name in driver.DOCUMENTS
    ])
    if driver.missing_documents:
        story.append(Paragraph(
            f"Pendentes: {', '.join(driver.missing_documents)}.",
            STYLES["muted"],
        ))
    if driver.notes:
        _section(story, "Observações", [("Notas", driver.notes)])
    _photos(story, hold, [
        (driver._meta.get_field(name).verbose_name, getattr(driver, name))
        for name in driver.DOCUMENTS
    ])
    _closing(story)
    return _build(f"Dossie entregador {driver.name}", story, hold)


def vehicle_dossier_pdf(vehicle):
    """Ficha cadastral do veículo, com documentos, seguro e fotos da frota."""
    hold = []
    story = [
        _header("DOSSIÊ DO VEÍCULO", str(vehicle), vehicle.get_kind_display()),
        Spacer(1, 8),
        Paragraph(
            f"{vehicle.get_status_display()} · cadastrado em {_date(vehicle.created_at)}",
            STYLES["body"],
        ),
    ]
    _section(story, "Identificação", [
        ("Tipo", vehicle.get_kind_display()),
        ("Placa", vehicle.plate),
        ("UF da placa", _blank(vehicle.plate_state)),
        ("RENAVAM", _blank(vehicle.renavam)),
        ("Chassi", _blank(vehicle.chassis)),
        ("Marca", vehicle.brand),
        ("Modelo", vehicle.model),
        ("Ano de fabricação", str(vehicle.year)),
        ("Ano do modelo", str(vehicle.model_year) if vehicle.model_year else "—"),
        ("Cor", _blank(vehicle.color)),
        ("Combustível", _blank(vehicle.get_fuel_display())),
        ("Quilometragem", f"{vehicle.mileage_km} km" if vehicle.mileage_km is not None else "—"),
        ("Capacidade", f"{vehicle.capacity_kg} kg" if vehicle.capacity_kg is not None else "—"),
        ("Equipamentos", _blank(vehicle.equipment)),
        ("Frota", vehicle.company.name),
    ])
    _section(story, "Propriedade e licenciamento", [
        ("Proprietário no CRLV", _blank(vehicle.owner_name)),
        ("CPF/CNPJ do proprietário", _blank(vehicle.owner_document)),
        ("Vencimento do licenciamento", _date(vehicle.crlv_expires_at)),
    ])
    _section(story, "Seguro e rastreamento", [
        ("Seguradora", _blank(vehicle.insurer)),
        ("Apólice", _blank(vehicle.insurance_policy)),
        ("Vencimento do seguro", _date(vehicle.insurance_expires_at)),
        ("Rastreador", _yes(vehicle.has_tracker)),
        ("Empresa do rastreador", _blank(vehicle.tracker_provider)),
    ])
    volume = vehicle.cargo_volume_liters
    _section(story, "Carga", [
        ("Baú (litros)", str(vehicle.top_case_liters) if vehicle.top_case_liters else "—"),
        ("Portas", str(vehicle.doors) if vehicle.doors else "—"),
        ("Carroceria", _blank(vehicle.get_body_type_display())),
        ("Peso bruto total", f"{vehicle.gross_weight_kg} kg" if vehicle.gross_weight_kg is not None else "—"),
        ("Comprimento", f"{vehicle.cargo_length_cm} cm" if vehicle.cargo_length_cm else "—"),
        ("Largura", f"{vehicle.cargo_width_cm} cm" if vehicle.cargo_width_cm else "—"),
        ("Altura", f"{vehicle.cargo_height_cm} cm" if vehicle.cargo_height_cm else "—"),
        ("Volume do compartimento", f"{volume} L" if volume else "—"),
        ("Refrigerado", _yes(vehicle.refrigerated)),
        ("Com trava", _yes(vehicle.lockable)),
    ])
    _section(story, "Documentos", [
        (vehicle._meta.get_field(name).verbose_name, _file_status(getattr(vehicle, name)))
        for name in vehicle.DOCUMENTS
    ])
    if vehicle.notes:
        _section(story, "Observações", [("Notas", vehicle.notes)])
    _photos(story, hold, [
        (vehicle._meta.get_field(name).verbose_name, getattr(vehicle, name))
        for name in vehicle.DOCUMENTS
    ])
    _closing(story)
    return _build(f"Dossie veiculo {vehicle.plate}", story, hold)
