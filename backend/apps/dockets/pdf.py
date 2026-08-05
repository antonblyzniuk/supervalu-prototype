"""Server-side PDF rendering for docket exports.

Rendering on the server (rather than in the browser with jsPDF) means the same
bytes come out on every device — a manager exporting from an iPad gets the file
the office gets — and lets the export honour the exact same filters as the list.
"""

from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import constants
from .reports import build_summary

BRAND = colors.HexColor("#C8102E")
BRAND_DARK = colors.HexColor("#8E0B20")
BRAND_TINT = colors.HexColor("#FBE9EC")
INK = colors.HexColor("#1A1F18")
MUTED = colors.HexColor("#6B7266")
LINE = colors.HexColor("#D8DBD2")
ZEBRA = colors.HexColor("#F8F9F6")

PAGE_SIZE = landscape(A4)
PAGE_WIDTH = PAGE_SIZE[0]
MARGIN = 10 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

_styles = getSampleStyleSheet()
S_TITLE = ParagraphStyle("dTitle", parent=_styles["Title"], fontSize=15, textColor=INK, spaceAfter=2)
S_SUB = ParagraphStyle("dSub", parent=_styles["Normal"], fontSize=9, textColor=MUTED)
S_H2 = ParagraphStyle(
    "dH2", parent=_styles["Heading2"], fontSize=11, textColor=BRAND, spaceBefore=8, spaceAfter=4
)
S_BODY = ParagraphStyle("dBody", parent=_styles["Normal"], fontSize=8, textColor=INK, leading=10)
S_CELL = ParagraphStyle("dCell", parent=S_BODY, fontSize=7, leading=8.5)
S_RIGHT = ParagraphStyle("dRight", parent=S_BODY, alignment=TA_RIGHT)


def _money(value):
    return f"€{Decimal(str(value or 0)):,.2f}"


def _page_furniture(canvas, doc):
    """Brand bar on every page plus a footer with the page number."""
    canvas.saveState()
    canvas.setFillColor(BRAND)
    canvas.rect(0, PAGE_SIZE[1] - 8 * mm, PAGE_WIDTH, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(MARGIN, PAGE_SIZE[1] - 5.6 * mm, "MORIARTY GROUP · SUPERVALU")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(
        PAGE_WIDTH - MARGIN, PAGE_SIZE[1] - 5.6 * mm, doc.docket_export_subtitle
    )

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(MARGIN, 6 * mm, doc.docket_export_stamp)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 6 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _table(data, col_widths, *, align_right_from=None, zebra=True):
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
    ]
    if zebra:
        style.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]))
    if align_right_from is not None:
        style.append(("ALIGN", (align_right_from, 1), (-1, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    return table


def _totals_row_style(table, row_index):
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, row_index), (-1, row_index), BRAND_TINT),
                ("TEXTCOLOR", (0, row_index), (-1, row_index), BRAND_DARK),
                ("FONTNAME", (0, row_index), (-1, row_index), "Helvetica-Bold"),
                ("LINEABOVE", (0, row_index), (-1, row_index), 0.8, BRAND),
            ]
        )
    )
    return table


def _docket_heading(docket):
    label = docket.get_docket_type_display()
    bits = [f"<b>{label}</b> · {docket.store.name}"]
    if docket.destination_store:
        bits.append(f"→ {docket.destination_store.name}")
    if docket.reference:
        bits.append(f"Ref {docket.reference}")
    if docket.docket_number:
        bits.append(f"Docket #{docket.docket_number}")
    bits.append(str(docket.effective_date))
    return Paragraph(" &nbsp;·&nbsp; ".join(bits), S_H2)


def _category_table(docket):
    keys = constants.category_keys(docket.docket_type)
    labels = dict(constants.CATEGORIES_BY_TYPE[docket.docket_type])
    head = ["Date", "Supplier", "Docket #"] + [labels[k] for k in keys] + ["Total", "Comments"]
    rows = [head]
    totals = {key: Decimal("0.00") for key in keys}
    grand = Decimal("0.00")

    for line in docket.lines.all():
        values = []
        for key in keys:
            raw = line.amounts.get(key)
            totals[key] += Decimal(str(raw)) if raw else Decimal("0.00")
            values.append(f"{Decimal(str(raw)):,.2f}" if raw else "")
        grand += line.total or Decimal("0.00")
        rows.append(
            [
                line.line_date.strftime("%d/%m/%y") if line.line_date else "",
                Paragraph(line.supplier or "", S_CELL),
                line.docket_number or "",
                *values,
                f"{line.total:,.2f}" if line.total else "",
                Paragraph(line.comments or "", S_CELL),
            ]
        )

    rows.append(
        ["TOTALS", "", ""]
        + [f"{totals[k]:,.2f}" if totals[k] else "" for k in keys]
        + [f"{grand:,.2f}", ""]
    )

    fixed = [16 * mm, 30 * mm, 16 * mm]
    tail = [16 * mm, 26 * mm]
    flexible = CONTENT_WIDTH - sum(fixed) - sum(tail)
    widths = fixed + [flexible / len(keys)] * len(keys) + tail
    table = _table(rows, widths, align_right_from=3)
    return _totals_row_style(table, len(rows) - 1)


def _item_table(docket):
    head = ["Qty / Units", "Description of Goods", "Cost €", "Retail €", "Total €"]
    rows = [head]
    grand = Decimal("0.00")
    for line in docket.lines.all():
        grand += line.total or Decimal("0.00")
        rows.append(
            [
                Paragraph(line.quantity or "", S_CELL),
                Paragraph(line.description or "", S_CELL),
                f"{line.cost_price:,.2f}" if line.cost_price is not None else "",
                f"{line.retail_price:,.2f}" if line.retail_price is not None else "",
                f"{line.total:,.2f}" if line.total else "",
            ]
        )
    rows.append(["TOTAL", "", "", "", f"{grand:,.2f}"])
    widths = [28 * mm, CONTENT_WIDTH - 28 * mm - 3 * 26 * mm, 26 * mm, 26 * mm, 26 * mm]
    table = _table(rows, widths, align_right_from=2)
    return _totals_row_style(table, len(rows) - 1)


def _meta_table(docket):
    pairs = [("Store", docket.store.name), ("Date", str(docket.effective_date))]
    if docket.destination_store:
        pairs.append(("To store", docket.destination_store.name))
    if docket.supplier:
        pairs.append(("Supplier", docket.supplier))
    if docket.department:
        pairs.append(("Department", docket.department))
    if docket.reference:
        pairs.append(("Reference", docket.reference))
    if docket.docket_number:
        pairs.append(("Docket #", docket.docket_number))
    if docket.manager_name:
        pairs.append(("Manager", docket.manager_name))
    if docket.outgoing_staff_name:
        pairs.append(("Outgoing staff", docket.outgoing_staff_name))
    pairs.append(("Saved", timezone.localtime(docket.created_at).strftime("%d/%m/%Y %H:%M")))
    if docket.reason:
        pairs.append(("Reason", docket.reason))

    cells = []
    for label, value in pairs:
        cells.append(
            Paragraph(
                f'<font color="#6B7266" size="6">{label.upper()}</font><br/>{value}', S_CELL
            )
        )
    per_row = 5
    grid = [cells[i : i + per_row] for i in range(0, len(cells), per_row)]
    if grid and len(grid[-1]) < per_row:
        grid[-1] += [""] * (per_row - len(grid[-1]))
    table = Table(grid, colWidths=[CONTENT_WIDTH / per_row] * per_row, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
                ("BOX", (0, 0), (-1, -1), 0.3, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _signature_strip(docket):
    signatures = list(docket.signatures.all())
    if not signatures:
        return None
    cells, labels = [], []
    for signature in signatures:
        try:
            cells.append(Image(signature.image.path, width=42 * mm, height=15 * mm, kind="proportional"))
        except Exception:  # noqa: BLE001 - a missing file must not kill the export
            cells.append(Paragraph("<i>signature unavailable</i>", S_CELL))
        role = signature.get_role_display()
        name = f" · {signature.signed_name}" if signature.signed_name else ""
        labels.append(Paragraph(f'<font size="6" color="#6B7266">{role}{name}</font>', S_CELL))
    table = Table([cells, labels], colWidths=[48 * mm] * len(cells), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, 0), 0.3, LINE),
                ("INNERGRID", (0, 0), (-1, 0), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _photo_strip(docket):
    photos = list(docket.photos.all())
    if not photos:
        return None
    cells = []
    for photo in photos[:6]:
        try:
            cells.append(Image(photo.image.path, width=34 * mm, height=34 * mm, kind="proportional"))
        except Exception:  # noqa: BLE001
            continue
    if not cells:
        return None
    table = Table([cells], colWidths=[38 * mm] * len(cells), hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return table


def _summary_block(summary, title):
    flow = [Paragraph(title, S_H2)]

    if summary["by_store"]:
        rows = [["Store", "Dockets", "Ambient", "Chilled", "Returns", "Transfer", "Total"]]
        for entry in summary["by_store"]:
            rows.append(
                [
                    entry["store"]["name"],
                    str(entry["docket_count"]),
                    _money(entry["by_type"]["ambient"]),
                    _money(entry["by_type"]["chilled"]),
                    _money(entry["by_type"]["returns"]),
                    _money(entry["by_type"]["transfer"]),
                    _money(entry["total"]),
                ]
            )
        rows.append(
            ["ALL STORES", str(summary["docket_count"]), "", "", "", "", _money(summary["grand_total"])]
        )
        widths = [CONTENT_WIDTH * f for f in (0.24, 0.10, 0.13, 0.13, 0.13, 0.13, 0.14)]
        table = _table(rows, widths, align_right_from=1)
        flow.append(_totals_row_style(table, len(rows) - 1))
        flow.append(Spacer(1, 5 * mm))

    for bucket in summary["by_type"]:
        if not bucket["docket_count"] or not bucket["columns"]:
            continue
        head = [column["label"] for column in bucket["columns"]] + ["Total"]
        values = [_money(bucket["category_totals"][c["key"]]) for c in bucket["columns"]]
        values.append(_money(bucket["total"]))
        flow.append(
            Paragraph(
                f"<b>{bucket['label']}</b> — {bucket['docket_count']} dockets, "
                f"{bucket['line_count']} lines",
                S_BODY,
            )
        )
        flow.append(Spacer(1, 1.5 * mm))
        widths = [CONTENT_WIDTH / len(head)] * len(head)
        flow.append(_table([head, values], widths, align_right_from=0, zebra=False))
        flow.append(Spacer(1, 4 * mm))

    return flow


def render_dockets_pdf(queryset, *, title, subtitle, include_detail=True):
    """Build the export PDF: cover summary, then one block per docket."""
    dockets = list(
        queryset.select_related("store", "destination_store").prefetch_related(
            "lines", "signatures", "photos"
        )
    )
    summary = build_summary(queryset)
    stamp = timezone.localtime().strftime("Generated %d/%m/%Y %H:%M")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
        title=title,
        author="Moriarty Group",
    )
    doc.docket_export_subtitle = subtitle
    doc.docket_export_stamp = stamp

    flow = [
        Paragraph(title, S_TITLE),
        Paragraph(f"{subtitle} · {stamp}", S_SUB),
        Spacer(1, 5 * mm),
    ]
    flow += _summary_block(summary, "Summary")

    if include_detail and dockets:
        flow.append(PageBreak())
        flow.append(Paragraph("Dockets", S_H2))
        for index, docket in enumerate(dockets):
            # Keep the heading glued to the meta block; let long line tables split
            # across pages rather than pushing a whole docket to the next one.
            flow.append(
                KeepTogether(
                    [_docket_heading(docket), Spacer(1, 1.5 * mm), _meta_table(docket)]
                )
            )
            flow.append(Spacer(1, 2 * mm))
            flow.append(_category_table(docket) if docket.is_category_type else _item_table(docket))

            signatures = _signature_strip(docket)
            if signatures:
                flow += [Spacer(1, 2.5 * mm), signatures]
            photos = _photo_strip(docket)
            if photos:
                flow += [Spacer(1, 2.5 * mm), photos]

            flow.append(Spacer(1, 5 * mm))
            if index < len(dockets) - 1:
                flow.append(
                    Table(
                        [[""]],
                        colWidths=[CONTENT_WIDTH],
                        style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]),
                    )
                )
                flow.append(Spacer(1, 4 * mm))
    elif not dockets:
        flow.append(Paragraph("No dockets match this filter.", S_BODY))

    doc.build(flow, onFirstPage=_page_furniture, onLaterPages=_page_furniture)
    return buffer.getvalue()
