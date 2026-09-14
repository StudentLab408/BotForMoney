from decimal import Decimal

from docx import Document

from bot.services.docx_export import build_supplement_docx
from bot.services.reporting import DocRow
from bot.templates.header_template import TABLE_HEADERS


def test_build_supplement_docx_structure():
    rows = [
        DocRow(
            index=1,
            last_name="Корецкий",
            first_name="Илья",
            middle_name="Игоревич",
            group_number="10706125",
            net_amount=Decimal(150),
            basis_text="«Robo Project», лауреат",
        ),
        DocRow(
            index=2,
            last_name="Гайчук",
            first_name="Фёдор",
            middle_name="Олегович",
            group_number="10706125",
            net_amount=Decimal("28.5"),
            basis_text="Конференция «ConfX» (25 BYN); Мероприятие «EventY» (12.5 BYN)",
        ),
    ]

    buf = build_supplement_docx(2026, 9, rows)
    doc = Document(buf)

    table = doc.tables[0]
    assert [cell.text for cell in table.rows[0].cells] == TABLE_HEADERS
    assert len(table.rows) == 1 + len(rows)

    row1_cells = [c.text for c in table.rows[1].cells]
    assert row1_cells[0] == "1"
    assert row1_cells[1] == "Корецкий"
    assert row1_cells[5] == "150"

    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Белорусский национальный технический университет" in full_text
    assert "сентября 2026" in full_text


def test_build_supplement_docx_empty_rows():
    buf = build_supplement_docx(2026, 1, [])
    doc = Document(buf)
    table = doc.tables[0]
    assert len(table.rows) == 1
