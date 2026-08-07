"""Server-side PDF rendering for roster exports.

Rendered on the server for the same reason the docket exports are: the same
bytes come out on every device, and the file honours exactly the filters the
screen was showing.
"""

from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# The print palette is shared with the docket exports so both come off the
# printer looking like the same organisation.
from apps.dockets.pdf import BRAND, BRAND_DARK, BRAND_TINT, INK, LINE, MUTED, ZEBRA

PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
MARGIN = 10 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

_styles = getSampleStyleSheet()
S_TITLE = ParagraphStyle("rTitle", parent=_styles["Title"], fontSize=15, textColor=INK, spaceAfter=2)
S_SUB = ParagraphStyle("rSub", parent=_styles["Normal"], fontSize=9, textColor=MUTED)
S_H2 = ParagraphStyle(
    "rH2", parent=_styles["Heading2"], fontSize=11, textColor=BRAND, spaceBefore=8, spaceAfter=4
)
S_BODY = ParagraphStyle("rBody", parent=_styles["Normal"], fontSize=8, textColor=INK, leading=10)


def _money(value):
    return f"€{Decimal(str(value or 0)):,.2f}"


def _hours(value):
    return f"{Decimal(str(value or 0)):,.2f}"


def _page_furniture(canvas, doc):
    """Brand bar on every page plus a footer with the page number."""
    canvas.saveState()
    canvas.setFillColor(BRAND)
    canvas.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(MARGIN, PAGE_HEIGHT - 5.6 * mm, "MORIARTY GROUP · SUPERVALU")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 5.6 * mm, doc.roster_subtitle)

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(MARGIN, 6 * mm, doc.roster_stamp)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 6 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _day_headings(days):
    """"Sun 2 Aug" over two lines, so seven columns fit without shouting."""
    return [f"{day.strftime('%a')}\n{day.strftime('%-d %b')}" for day in days]


def _shift_cell(shift):
    """A rostered day as it reads on paper: the times, then what they cost."""
    if shift is None:
        return "—"
    times = f"{shift['start_time'][:5]}–{shift['end_time'][:5]}"
    detail = _hours(shift["hours"]) + "h"
    if shift["break_minutes"]:
        detail += f" · {shift['break_minutes']}m {'paid' if shift['break_paid'] else 'unpaid'}"
    return f"{times}\n{detail}"


def _department_table(group, days):
    head = ["Person", *_day_headings(days), "Hours", "Cost"]
    rows = [head]

    for entry in group["people"]:
        person = entry["person"]
        by_date = {shift["date"]: shift for shift in entry["shifts"]}
        name = person["full_name"]
        if not person.get("is_active", True):
            name += " (left)"
        rows.append(
            [
                f"{name}\n{_money(person['hourly_rate'])}/hr",
                *[_shift_cell(by_date.get(day.isoformat())) for day in days],
                _hours(entry["totals"]["hours"]) + "h",
                _money(entry["totals"]["cost"]),
            ]
        )

    rows.append(
        [
            "TOTAL",
            *[""] * len(days),
            _hours(group["totals"]["hours"]) + "h",
            _money(group["totals"]["cost"]),
        ]
    )

    name_width = 42 * mm
    tail_width = 20 * mm
    day_width = (CONTENT_WIDTH - name_width - 2 * tail_width) / len(days)
    widths = [name_width, *[day_width] * len(days), tail_width, tail_width]

    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    last = len(rows) - 1
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEADING", (0, 0), (-1, -1), 8.5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("ALIGN", (-2, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, last - 1), [colors.white, ZEBRA]),
                ("BACKGROUND", (0, last), (-1, last), BRAND_TINT),
                ("TEXTCOLOR", (0, last), (-1, last), BRAND_DARK),
                ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
                ("LINEABOVE", (0, last), (-1, last), 0.8, BRAND),
            ]
        )
    )
    return table


def _summary_table(board):
    totals = board["totals"]
    rows = [
        ["Hours rostered", "Wage bill", "Shifts", "People on"],
        [
            _hours(totals["hours"]) + "h",
            _money(totals["cost"]),
            str(totals["shift_count"]),
            f"{totals['people_rostered']} of {totals['people_total']}",
        ],
    ]
    width = CONTENT_WIDTH / 4
    table = Table(rows, colWidths=[width] * 4, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7),
                ("FONTSIZE", (0, 1), (-1, 1), 12),
                ("TEXTCOLOR", (0, 1), (-1, 1), BRAND_DARK),
                ("BACKGROUND", (0, 1), (-1, 1), BRAND_TINT),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def render_roster_pdf(board, days, *, title, subtitle):
    """One page-width table per department, under the week's totals."""
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
    doc.roster_subtitle = subtitle
    doc.roster_stamp = stamp

    flow = [
        Paragraph(title, S_TITLE),
        Paragraph(f"{subtitle} · {stamp}", S_SUB),
        Spacer(1, 4 * mm),
        _summary_table(board),
        Spacer(1, 5 * mm),
    ]

    staffed = [group for group in board["departments"] if group["people"]]
    if not staffed:
        flow.append(Paragraph("Nobody is assigned to this store yet.", S_BODY))
    for group in staffed:
        heading = Paragraph(
            f"{group['name']} &nbsp;·&nbsp; {_hours(group['totals']['hours'])}h "
            f"&nbsp;·&nbsp; {_money(group['totals']['cost'])}",
            S_H2,
        )
        # Glue the heading to the top of its table; a long department may still
        # split across pages, with the header row repeated.
        flow.append(KeepTogether([heading, Spacer(1, 1 * mm)]))
        flow.append(_department_table(group, days))
        flow.append(Spacer(1, 4 * mm))

    doc.build(flow, onFirstPage=_page_furniture, onLaterPages=_page_furniture)
    return buffer.getvalue()
