"""Tests for document editing operations and formatting preservation."""

import pytest
from pathlib import Path
from docx import Document

from src.document import (
    analyze,
    replace_text,
    insert_paragraph,
    remove_paragraph,
    compare,
    _replace_in_paragraph,
)
from create_sample import create_sample_input


@pytest.fixture
def sample_path(tmp_path):
    path = str(tmp_path / "input.docx")
    create_sample_input(path)
    return path


@pytest.fixture
def doc(sample_path):
    return Document(sample_path)


class TestAnalyze:
    def test_contains_paragraphs(self, sample_path):
        result = analyze(sample_path)
        assert "[P0|Heading 1]" in result
        assert "Quarterly Report" in result

    def test_contains_table(self, sample_path):
        result = analyze(sample_path)
        assert "[Table 0]" in result
        assert "Active Users" in result

    def test_shows_formatting(self, sample_path):
        result = analyze(sample_path)
        assert "[B]" in result or "[BI]" in result


class TestReplaceText:
    def test_simple_replace(self, doc):
        ok = replace_text(doc, "strong growth", "moderate growth")
        assert ok
        full = " ".join(p.text for p in doc.paragraphs)
        assert "moderate growth" in full
        assert "strong growth" not in full

    def test_preserves_other_paragraphs(self, sample_path):
        original = Document(sample_path)
        modified = Document(sample_path)
        replace_text(modified, "strong growth", "moderate growth")

        for i, (op, mp) in enumerate(zip(original.paragraphs, modified.paragraphs)):
            if "growth" not in op.text:
                assert op.text == mp.text, f"Paragraph {i} changed unexpectedly"

    def test_preserves_formatting_on_untouched(self, sample_path):
        original = Document(sample_path)
        modified = Document(sample_path)
        replace_text(modified, "strong growth", "moderate growth")

        for i, (op, mp) in enumerate(zip(original.paragraphs, modified.paragraphs)):
            if op.text == mp.text and len(op.runs) == len(mp.runs):
                for j, (or_, mr) in enumerate(zip(op.runs, mp.runs)):
                    assert or_.bold == mr.bold, f"P{i}R{j} bold changed"
                    assert or_.italic == mr.italic, f"P{i}R{j} italic changed"
                    assert or_.underline == mr.underline, f"P{i}R{j} underline changed"

    def test_replace_in_table(self, doc):
        ok = replace_text(doc, "1,250", "1,300")
        assert ok
        found = any(
            "1,300" in cell.text
            for table in doc.tables
            for row in table.rows
            for cell in row.cells
        )
        assert found

    def test_not_found_returns_false(self, doc):
        assert not replace_text(doc, "nonexistent text xyz", "anything")

    def test_empty_old_returns_false(self, doc):
        assert not replace_text(doc, "", "anything")


class TestCrossRunReplace:
    def test_replace_spanning_two_runs(self):
        doc = Document()
        p = doc.add_paragraph()
        r1 = p.add_run("Hello ")
        r1.bold = True
        p.add_run("World")

        ok = _replace_in_paragraph(p, "Hello World", "Hi Earth")
        assert ok
        assert "".join(r.text for r in p.runs) == "Hi Earth"
        assert p.runs[0].bold

    def test_replace_within_single_run(self):
        doc = Document()
        p = doc.add_paragraph()
        r = p.add_run("Hello World")
        r.italic = True

        ok = _replace_in_paragraph(p, "World", "Earth")
        assert ok
        assert p.runs[0].text == "Hello Earth"
        assert p.runs[0].italic


class TestInsertParagraph:
    def test_insert_after_index(self, doc):
        count = len(doc.paragraphs)
        insert_paragraph(doc, 0, "New paragraph")
        assert len(doc.paragraphs) == count + 1
        assert doc.paragraphs[1].text == "New paragraph"

    def test_insert_at_beginning(self, doc):
        insert_paragraph(doc, -1, "First paragraph")
        assert doc.paragraphs[0].text == "First paragraph"

    def test_insert_at_end(self, doc):
        last_idx = len(doc.paragraphs) - 1
        insert_paragraph(doc, last_idx, "Last paragraph")
        assert doc.paragraphs[-1].text == "Last paragraph"


class TestRemoveParagraph:
    def test_remove_existing(self, doc):
        count = len(doc.paragraphs)
        ok = remove_paragraph(doc, "Client satisfaction")
        assert ok
        assert len(doc.paragraphs) == count - 1
        assert all("Client satisfaction" not in p.text for p in doc.paragraphs)

    def test_remove_not_found(self, doc):
        assert not remove_paragraph(doc, "nonexistent text xyz")


class TestCompare:
    def test_detects_text_change(self, sample_path, tmp_path):
        output = str(tmp_path / "modified.docx")
        doc = Document(sample_path)
        replace_text(doc, "strong growth", "moderate growth")
        doc.save(output)

        diff = compare(sample_path, output)
        assert len(diff["differences"]) > 0
        assert diff["tables_preserved"]

    def test_no_formatting_issues(self, sample_path, tmp_path):
        output = str(tmp_path / "modified.docx")
        doc = Document(sample_path)
        replace_text(doc, "strong growth", "moderate growth")
        doc.save(output)

        diff = compare(sample_path, output)
        assert diff["formatting_issues"] == []

    def test_detects_added_paragraph(self, sample_path, tmp_path):
        output = str(tmp_path / "modified.docx")
        doc = Document(sample_path)
        insert_paragraph(doc, 0, "Brand new paragraph")
        doc.save(output)

        diff = compare(sample_path, output)
        assert any(d["type"] in ("changed", "added") for d in diff["differences"])

    def test_detects_removed_paragraph(self, sample_path, tmp_path):
        output = str(tmp_path / "modified.docx")
        doc = Document(sample_path)
        remove_paragraph(doc, "Client satisfaction")
        doc.save(output)

        diff = compare(sample_path, output)
        assert any(d["type"] in ("changed", "removed") for d in diff["differences"])


@pytest.mark.integration
class TestFullAgent:
    def test_replace_flow(self, sample_path, tmp_path):
        from src.agent import build_graph

        output = str(tmp_path / "output.docx")
        graph = build_graph()
        result = graph.invoke({
            "document_path": sample_path,
            "output_path": output,
            "instruction": "Replace '23%' with '25%' in the executive summary",
            "structure": "",
            "plan": [],
            "execution_log": [],
            "validation": {},
            "retry_count": 0,
        })

        assert result["validation"]["passed"]
        assert Path(output).exists()

        doc = Document(output)
        full = " ".join(p.text for p in doc.paragraphs)
        assert "25%" in full
        assert "23%" not in full
