"""Creates sample .docx documents for testing and demonstration."""

from pathlib import Path
from docx import Document


def create_sample_input(path: str = "samples/sample_input.docx") -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    doc.add_heading("Quarterly Report — Q4 2025", level=1)

    p = doc.add_paragraph()
    p.add_run("Prepared by: ").bold = True
    p.add_run("Dr. Elena Schmidt")

    p = doc.add_paragraph()
    p.add_run("Date: ").bold = True
    p.add_run("December 15, 2025")

    doc.add_heading("Executive Summary", level=2)

    doc.add_paragraph(
        "The fourth quarter showed strong growth across all departments. "
        "Revenue increased by 23% compared to Q3, driven primarily by "
        "the launch of our new therapy management module."
    )

    doc.add_paragraph(
        "Client satisfaction scores remained above 90%, with notable "
        "improvements in onboarding time and system reliability."
    )

    doc.add_heading("Key Metrics", level=2)

    table = doc.add_table(rows=4, cols=3, style="Table Grid")
    for i, h in enumerate(["Metric", "Q3 2025", "Q4 2025"]):
        table.cell(0, i).text = h
    for r, row_data in enumerate([
        ["Active Users", "1,250", "1,580"],
        ["Revenue (EUR)", "340,000", "418,200"],
        ["Uptime (%)", "99.7", "99.9"],
    ]):
        for c, val in enumerate(row_data):
            table.cell(r + 1, c).text = val

    doc.add_heading("Next Steps", level=2)

    doc.add_paragraph(
        "The team will focus on expanding the AI-assisted documentation "
        "feature and improving integration with existing EHR systems."
    )

    p = doc.add_paragraph()
    r = p.add_run("Important: ")
    r.bold = True
    r.italic = True
    p.add_run("All figures in this report are ")
    r = p.add_run("preliminary")
    r.italic = True
    p.add_run(" and subject to final audit review.")

    doc.save(path)
    print(f"Created: {path}")
    return path


def create_sample_output(
    input_path: str = "samples/sample_input.docx",
    output_path: str = "samples/sample_output.docx",
) -> str:
    """Demonstrates a text replacement without LLM (for reproducible sample)."""
    from src.document import replace_text

    doc = Document(input_path)
    replace_text(doc, "23%", "25%")
    doc.save(output_path)
    print(f"Created: {output_path} (replaced '23%' -> '25%')")
    return output_path


if __name__ == "__main__":
    inp = create_sample_input()
    create_sample_output(inp)
