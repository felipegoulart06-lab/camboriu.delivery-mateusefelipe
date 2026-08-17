"""PDF do manual de integração — o mesmo texto da tela Integração."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .playbook import AUDIENCE, SECTIONS, SUBTITLE, TITLE, VERSION

INK = colors.HexColor("#1c1c1c")
TEAL = colors.HexColor("#2e2e2e")
MUTED = colors.HexColor("#6a6a6a")
LINE = colors.HexColor("#e2e2e2")
MINT = colors.HexColor("#f2f2f2")
PAGE = A4

_BASE = getSampleStyleSheet()
STYLES = {
    "cover": ParagraphStyle("cover", parent=_BASE["Title"], fontSize=18, textColor=INK, leading=22, spaceAfter=6),
    "eyebrow": ParagraphStyle("eyebrow", parent=_BASE["Normal"], fontSize=8, textColor=TEAL, leading=11, spaceAfter=4),
    "lead": ParagraphStyle("lead", parent=_BASE["Normal"], fontSize=10, textColor=INK, leading=14, spaceAfter=8),
    "h2": ParagraphStyle("h2", parent=_BASE["Normal"], fontSize=12, textColor=INK, leading=16, spaceBefore=12, spaceAfter=6),
    "body": ParagraphStyle("body", parent=_BASE["Normal"], fontSize=9, textColor=INK, leading=13, alignment=TA_JUSTIFY, spaceAfter=6),
    "muted": ParagraphStyle("muted", parent=_BASE["Normal"], fontSize=8, textColor=MUTED, leading=11),
    "item": ParagraphStyle("item", parent=_BASE["Normal"], fontSize=9, textColor=INK, leading=12.5),
    "role": ParagraphStyle("role", parent=_BASE["Normal"], fontSize=9, textColor=INK, leading=12.5),
    "photo_n": ParagraphStyle("photo_n", parent=_BASE["Normal"], fontSize=9, textColor=TEAL, leading=12, fontName="Helvetica-Bold"),
    "footer": ParagraphStyle("footer", parent=_BASE["Normal"], fontSize=7.5, textColor=MUTED, leading=10),
}


def _escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, PAGE[1] - 8 * mm, PAGE[0], 8 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, PAGE[1] - 5.4 * mm, "CAMBORIÚ DELIVERY  ·  Manual de integração")
    canvas.drawRightString(PAGE[0] - 18 * mm, PAGE[1] - 5.4 * mm, f"v{VERSION}")
    canvas.setFillColor(LINE)
    canvas.rect(0, 0, PAGE[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 5 * mm, "Uso interno e apresentação a empresas e entregadores")
    canvas.drawRightString(PAGE[0] - 18 * mm, 5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _bullets(items, bullet="•"):
    return ListFlowable(
        [ListItem(Paragraph(_escape(item), STYLES["item"]), leftIndent=8, bulletColor=TEAL) for item in items],
        bulletType="bullet",
        start=bullet,
        leftIndent=12,
        bulletFontName="Helvetica",
        bulletFontSize=9,
        spaceAfter=6,
    )


def _numbered(items):
    flow = []
    for index, item in enumerate(items, start=1):
        flow.append(Paragraph(f"<b>{index}.</b>  {_escape(item)}", STYLES["item"]))
        flow.append(Spacer(1, 3))
    flow.append(Spacer(1, 4))
    return flow


def _roles(items):
    rows = []
    for title, text in items:
        rows.append([
            Paragraph(f"<b>{_escape(title)}</b>", STYLES["role"]),
            Paragraph(_escape(text), STYLES["role"]),
        ])
    table = Table(rows, colWidths=[42 * mm, 128 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), MINT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _photos(items):
    rows = []
    for number, title, how in items:
        rows.append([
            Paragraph(number, STYLES["photo_n"]),
            Paragraph(f"<b>{_escape(title)}</b><br/>{_escape(how)}", STYLES["item"]),
        ])
    table = Table(rows, colWidths=[12 * mm, 158 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 0), (0, -1), MINT),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
    ]))
    return table


def _block(block):
    kind = block["type"]
    if kind == "p":
        return [Paragraph(_escape(block["text"]), STYLES["body"])]
    if kind == "steps":
        return _numbered(block["items"])
    if kind == "rules":
        return [_bullets(block["items"])]
    if kind == "roles":
        return [_roles(block["items"]), Spacer(1, 6)]
    if kind == "photos":
        return [_photos(block["items"]), Spacer(1, 6)]
    return []


def integration_pdf():
    """Manual completo para entregar à empresa e ao entregador na integração."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, title=TITLE, author="SC Transporte Executivo Delivery",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm,
    )
    story = [
        Paragraph("PROCEDIMENTO OPERACIONAL", STYLES["eyebrow"]),
        Paragraph(TITLE, STYLES["cover"]),
        Paragraph(_escape(SUBTITLE), STYLES["lead"]),
        Paragraph(
            f"{_escape(AUDIENCE)}  ·  Emitido em {timezone.localtime():%d/%m/%Y %H:%M}  ·  Versão {VERSION}",
            STYLES["muted"],
        ),
        Spacer(1, 8),
    ]
    for section in SECTIONS:
        pieces = [Paragraph(_escape(section["title"]), STYLES["h2"])]
        for block in section["blocks"]:
            pieces.extend(_block(block))
        story.append(KeepTogether(pieces))
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    return buffer
