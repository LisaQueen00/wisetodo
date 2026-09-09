from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from wisetodo.files.pdf_extract import extract_pdf
from wisetodo.files.references import FileReferences


def save(tmp_path, writer):
    path = tmp_path / "book.pdf"
    with path.open("wb") as stream:
        writer.write(stream)
    refs = FileReferences([str(path)])
    return refs, refs.descriptions()[0]["file_ref"]


def test_real_metadata_outline_hierarchy_and_physical_pages(tmp_path):
    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "测试书籍"})
    parent = writer.add_outline_item("第一章 开始", 0)
    writer.add_outline_item("1.1 基础", 1, parent=parent)
    writer.add_outline_item("第二章 实践", 2)
    result = extract_pdf(*save(tmp_path, writer))
    assert result.title == "测试书籍"
    assert result.page_count == 4
    assert [(s.title, s.page, s.depth) for s in result.sections] == [
        ("第一章 开始", 1, 0),
        ("1.1 基础", 2, 1),
        ("第二章 实践", 3, 0),
    ]
    assert len(result.pages) == 3
    assert all(page.text == "" for page in result.pages)
    assert not result.outline_truncated


def test_real_text_without_outline_does_not_invent_chapters(tmp_path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 10 100 Td (Chapter One) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    result = extract_pdf(*save(tmp_path, writer))
    assert result.title is None
    assert result.sections == ()
    assert "Chapter One" in result.pages[0].text


def test_outline_limit_reported(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    for index in range(201):
        writer.add_outline_item(f"Section {index}", 0)
    result = extract_pdf(*save(tmp_path, writer))
    assert len(result.sections) == 200
    assert result.outline_truncated
