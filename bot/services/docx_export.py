import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, Twips

from bot.services.reporting import DocRow
from bot.templates.header_template import COLUMN_WIDTHS_TWIPS, INSTITUTION_LINES, PURPOSE_TEMPLATE, TABLE_HEADERS
from bot.utils.time import month_name_genitive


def _set_cell_width(cell, width_twips: int) -> None:
    cell.width = Twips(width_twips)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.makeelement(qn("w:tcW"), {qn("w:w"): str(width_twips), qn("w:type"): "dxa"})
    tc_pr.append(tc_w)


def build_supplement_docx(year: int, month: int, rows: list[DocRow]) -> io.BytesIO:
    doc = Document()

    for line in INSTITUTION_LINES:
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.bold = True
        run.font.size = Pt(12)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    purpose = PURPOSE_TEMPLATE.format(month_name=month_name_genitive(month), year=year)
    purpose_p = doc.add_paragraph(purpose)
    purpose_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph()

    table = doc.add_table(rows=1, cols=len(TABLE_HEADERS))
    table.style = "Table Grid"

    header_cells = table.rows[0].cells
    for i, header in enumerate(TABLE_HEADERS):
        header_cells[i].text = header
        for p in header_cells[i].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.bold = True
        _set_cell_width(header_cells[i], COLUMN_WIDTHS_TWIPS[i])

    for row in rows:
        cells = table.add_row().cells
        values = [
            str(row.index),
            row.last_name,
            row.first_name,
            row.middle_name,
            row.group_number,
            str(row.net_amount),
            row.basis_text,
        ]
        for i, value in enumerate(values):
            cells[i].text = value
            _set_cell_width(cells[i], COLUMN_WIDTHS_TWIPS[i])

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
