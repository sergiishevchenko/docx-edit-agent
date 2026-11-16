"""Document analysis and editing operations for .docx files."""

from docx import Document as DocxDocument


def analyze(path: str) -> str:
    doc = DocxDocument(path)
    lines = []

    for i, para in enumerate(doc.paragraphs):
        style = para.style.name if para.style else "Default"
        lines.append(f"[P{i}|{style}] {para.text}")
        fmt_parts = []
        for run in para.runs:
            markers = []
            if run.bold:
                markers.append("B")
            if run.italic:
                markers.append("I")
            if run.underline:
                markers.append("U")
            if markers:
                fmt_parts.append(f"'{run.text}'[{''.join(markers)}]")
        if fmt_parts:
            lines.append(f"  Runs: {', '.join(fmt_parts)}")

    for i, table in enumerate(doc.tables):
        lines.append(f"\n[Table {i}] {len(table.rows)} rows x {len(table.columns)} cols")
        for r, row in enumerate(table.rows):
            cells = [c.text.replace("\n", " ") for c in row.cells]
            lines.append(f"  Row {r}: {cells}")

    img_count = len(doc.inline_shapes)
    if img_count:
        lines.append(f"\n[Images] {img_count} inline image(s)")

    return "\n".join(lines)


def replace_text(doc: DocxDocument, old: str, new: str) -> bool:
    if not old:
        return False
    replaced = False
    for para in _all_paragraphs(doc):
        while old in "".join(r.text for r in para.runs):
            if _replace_in_paragraph(para, old, new):
                replaced = True
            else:
                break
    return replaced


def insert_paragraph(
    doc: DocxDocument, after_index: int, text: str, style: str = "Normal"
) -> bool:
    if not doc.paragraphs:
        doc.add_paragraph(text, style=style)
        return True

    new_para = doc.add_paragraph(text, style=style)
    elem = new_para._element
    doc.element.body.remove(elem)

    paras = doc.paragraphs
    if after_index < 0:
        paras[0]._element.addprevious(elem)
    else:
        idx = min(after_index, len(paras) - 1)
        paras[idx]._element.addnext(elem)

    return True


def remove_paragraph(doc: DocxDocument, text_to_find: str) -> bool:
    for para in doc.paragraphs:
        if text_to_find in para.text:
            para._element.getparent().remove(para._element)
            return True
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if text_to_find in para.text:
                        para._element.getparent().remove(para._element)
                        return True
    return False


def compare(original_path: str, modified_path: str) -> dict:
    orig = DocxDocument(original_path)
    mod = DocxDocument(modified_path)

    orig_paras = list(orig.paragraphs)
    mod_paras = list(mod.paragraphs)

    differences = []
    formatting_issues = []

    for i in range(min(len(orig_paras), len(mod_paras))):
        op, mp = orig_paras[i], mod_paras[i]
        if op.text != mp.text:
            differences.append(
                {"type": "changed", "paragraph": i, "before": op.text, "after": mp.text}
            )
        elif len(op.runs) == len(mp.runs):
            for j, (or_, mr) in enumerate(zip(op.runs, mp.runs)):
                if (
                    or_.bold != mr.bold
                    or or_.italic != mr.italic
                    or or_.underline != mr.underline
                ):
                    formatting_issues.append(
                        {"paragraph": i, "run": j, "detail": "formatting changed"}
                    )

    for i in range(len(mod_paras), len(orig_paras)):
        differences.append({"type": "removed", "paragraph": i, "text": orig_paras[i].text})
    for i in range(len(orig_paras), len(mod_paras)):
        differences.append({"type": "added", "paragraph": i, "text": mod_paras[i].text})

    return {
        "orig_paragraphs": len(orig_paras),
        "mod_paragraphs": len(mod_paras),
        "differences": differences,
        "formatting_issues": formatting_issues,
        "tables_preserved": len(orig.tables) == len(mod.tables),
    }


def _replace_in_paragraph(paragraph, old: str, new: str) -> bool:
    runs = paragraph.runs
    if not runs:
        return False

    full = "".join(r.text for r in runs)
    start = full.find(old)
    if start == -1:
        return False

    end = start + len(old)

    char_map = []
    for i, run in enumerate(runs):
        char_map.extend([i] * len(run.text))

    if not char_map:
        return False

    sr = char_map[start]
    er = char_map[end - 1]

    s_off = start - sum(len(runs[i].text) for i in range(sr))
    e_off = end - sum(len(runs[i].text) for i in range(er))

    if sr == er:
        runs[sr].text = runs[sr].text[:s_off] + new + runs[sr].text[e_off:]
    else:
        runs[sr].text = runs[sr].text[:s_off] + new
        for i in range(sr + 1, er):
            runs[i].text = ""
        runs[er].text = runs[er].text[e_off:]

    return True


def _all_paragraphs(doc):
    yield from doc.paragraphs
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from cell.paragraphs
