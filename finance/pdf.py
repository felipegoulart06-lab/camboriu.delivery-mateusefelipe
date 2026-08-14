"""PDFs da operação: solicitação de entrega e fatura, sempre com o cabeçalho da empresa."""
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#13231e")
TEAL = colors.HexColor("#0f7866")
MUTED = colors.HexColor("#64736e")
LINE = colors.HexColor("#dce5e1")
MINT = colors.HexColor("#eef6f3")

_BASE = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("title", parent=_BASE["Title"], fontSize=16, textColor=INK, alignment=0, spaceAfter=2),
    "eyebrow": ParagraphStyle("eyebrow", parent=_BASE["Normal"], fontSize=7.5, textColor=TEAL, leading=10),
    "body": ParagraphStyle("body", parent=_BASE["Normal"], fontSize=9, textColor=INK, leading=13),
    "muted": ParagraphStyle("muted", parent=_BASE["Normal"], fontSize=8, textColor=MUTED, leading=11),
    "cell": ParagraphStyle("cell", parent=_BASE["Normal"], fontSize=8.5, textColor=INK, leading=11.5),
    "cellhead": ParagraphStyle("cellhead", parent=_BASE["Normal"], fontSize=7.5, textColor=MUTED, leading=10),
    "section": ParagraphStyle("section", parent=_BASE["Normal"], fontSize=10, textColor=INK, leading=14, spaceBefore=10, spaceAfter=4),
    "right": ParagraphStyle("right", parent=_BASE["Normal"], fontSize=9, textColor=INK, alignment=TA_RIGHT, leading=13),
}


def brl(value):
    text = f"{value or 0:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"


def texto(valor):
    """O ReportLab lê o parágrafo como marcação: endereço com < ou & derrubaria o PDF."""
    return escape("" if valor is None else str(valor))


def _document(buffer, title):
    return SimpleDocTemplate(
        buffer, pagesize=A4, title=title, author="Camboriú Delivery",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )


def _company_header(company, eyebrow):
    """Cabeçalho com os dados cadastrais da empresa que está solicitando."""
    left = [
        Paragraph(texto(eyebrow), STYLES["eyebrow"]),
        Paragraph(texto(company.billing_name), STYLES["title"]),
        Paragraph(texto(company.document_label), STYLES["body"]),
    ]
    if company.state_registration:
        left.append(Paragraph(f"Inscrição estadual: {texto(company.state_registration)}", STYLES["muted"]))
    if company.full_address:
        left.append(Paragraph(texto(company.full_address), STYLES["muted"]))
    contact = " · ".join(part for part in (company.contact_name, company.phone, company.email) if part)
    if contact:
        left.append(Paragraph(texto(contact), STYLES["muted"]))

    right = [
        Paragraph("<b>CAMBORIÚ DELIVERY</b>", STYLES["right"]),
        Paragraph("Transporte de itens sensíveis", STYLES["right"]),
        Paragraph(f"Emitido em {timezone.localtime():%d/%m/%Y %H:%M}", STYLES["right"]),
    ]
    header = Table([[left, right]], colWidths=[105 * mm, 65 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEAL),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return header


def _facts(rows):
    data = [
        [Paragraph(texto(label), STYLES["cellhead"]), Paragraph(texto(value or "—"), STYLES["cell"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[45 * mm, 125 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _grid(header, rows, widths, aligns=None):
    data = [[Paragraph(texto(item), STYLES["cellhead"]) for item in header]]
    data += [[Paragraph(texto(cell), STYLES["cell"]) for cell in row] for row in rows]
    table = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), MINT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    for column in aligns or []:
        style.append(("ALIGN", (column, 0), (column, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    return table


def delivery_request_pdf(delivery):
    """Solicitação de entrega com os dados cadastrais de quem pediu, para anexar ao contrato."""
    company = delivery.company
    buffer = BytesIO()
    story = [
        _company_header(company, "SOLICITAÇÃO DE ENTREGA"),
        Spacer(1, 8),
        Paragraph(f"<b>Solicitação {delivery.code}</b> · {delivery.get_status_display()}", STYLES["body"]),
        Spacer(1, 6),
        _facts([
            ("Solicitante", delivery.requester),
            ("Aberta em", timezone.localtime(delivery.created_at).strftime("%d/%m/%Y %H:%M")),
            ("Tipo de item", delivery.get_item_type_display()),
            ("Prioridade", delivery.get_priority_display()),
            ("Descrição", delivery.description),
            ("Valor declarado", brl(delivery.declared_value)),
            ("Sigiloso", "Sim" if delivery.confidential else "Não"),
            ("Prazo", timezone.localtime(delivery.deadline).strftime("%d/%m/%Y %H:%M") if delivery.deadline else "—"),
        ]),
        Paragraph("<b>Coleta</b>", STYLES["section"]),
        _facts([("Endereço", delivery.pickup_address), ("Contato", delivery.pickup_contact)]),
        Paragraph(f"<b>Destinos ({delivery.destination_count})</b>", STYLES["section"]),
        _grid(
            ["#", "Endereço", "Contato", "Observações"],
            [[stop.order, stop.address, stop.contact or "—", stop.notes or "—"] for stop in delivery.destinations],
            [10 * mm, 80 * mm, 40 * mm, 40 * mm],
        ),
    ]

    story.append(Paragraph("<b>Execução e valores</b>", STYLES["section"]))
    story.append(_facts([
        ("Entregador", delivery.driver.name if delivery.driver_id else "aguardando acionamento"),
        ("Veículo", str(delivery.vehicle) if delivery.vehicle_id else "—"),
        ("Valor da entrega", brl(delivery.price)),
        ("Fatura", delivery.invoice.number if delivery.invoice_id else "não faturada"),
        ("Checklist antifraude", "enviado com 12 fotos" if delivery.has_pickup_checklist else "pendente"),
    ]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Documento gerado pelo sistema Camboriú Delivery. Os dados cadastrais acima foram informados pela própria "
        "empresa solicitante e acompanham esta solicitação para fins de contrato de prestação de serviço.",
        STYLES["muted"],
    ))

    _document(buffer, f"Solicitacao {delivery.code}").build(story)
    buffer.seek(0)
    return buffer


def invoice_pdf(invoice):
    """Fatura das entregas do período, com a linha digitável quando o boleto já saiu."""
    company = invoice.company
    deliveries = invoice.deliveries.select_related("driver").order_by("delivered_at")
    buffer = BytesIO()
    story = [
        _company_header(company, f"FATURA {invoice.number}"),
        Spacer(1, 8),
        _facts([
            ("Situação", invoice.get_status_display()),
            ("Forma de cobrança", invoice.get_kind_display()),
            ("Vencimento", invoice.due_date.strftime("%d/%m/%Y")),
            ("Entregas faturadas", deliveries.count()),
            ("Total", brl(invoice.total)),
        ]),
        Paragraph("<b>Entregas incluídas</b>", STYLES["section"]),
        _grid(
            ["Código", "Entregue em", "Destinos", "Entregador", "Valor"],
            [
                [
                    item.code,
                    timezone.localtime(item.delivered_at).strftime("%d/%m/%Y") if item.delivered_at else "—",
                    item.destination_count,
                    item.driver.name if item.driver_id else "—",
                    brl(item.price),
                ]
                for item in deliveries
            ],
            [32 * mm, 28 * mm, 20 * mm, 55 * mm, 35 * mm],
            aligns=[4],
        ),
        Spacer(1, 6),
        Paragraph(f"<b>Total a pagar: {brl(invoice.total)}</b>", STYLES["right"]),
    ]

    if invoice.bank_slip_line:
        story.append(KeepTogether([
            Paragraph("<b>Boleto bancário</b>", STYLES["section"]),
            Paragraph(f"Linha digitável: {texto(invoice.bank_slip_line)}", STYLES["body"]),
            Paragraph("Pague em qualquer banco ou aplicativo até a data de vencimento.", STYLES["muted"]),
        ]))
    elif invoice.kind == invoice.Kind.BANK_SLIP:
        story.append(Paragraph(
            "Boleto em emissão pela Camboriú Delivery. A linha digitável aparece aqui e no painel assim que o banco emitir.",
            STYLES["muted"],
        ))
    if invoice.notes:
        story.append(Paragraph(texto(invoice.notes), STYLES["muted"]))

    _document(buffer, f"Fatura {invoice.number}").build(story)
    buffer.seek(0)
    return buffer
