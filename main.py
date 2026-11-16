"""CLI entry point for the document editing agent."""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.agent import build_graph


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="AI-powered Word Document Editor")
    parser.add_argument("document", help="Path to the .docx file")
    parser.add_argument("instruction", help="Editing instruction in natural language")
    parser.add_argument("-o", "--output", help="Output path (default: <name>_edited.docx)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    doc_path = Path(args.document)
    if not doc_path.exists():
        print(f"Error: file not found: {doc_path}")
        sys.exit(1)

    output = args.output or str(doc_path.with_stem(doc_path.stem + "_edited"))

    print(f"Processing: {doc_path}")
    print(f"Instruction: {args.instruction}\n")

    graph = build_graph()
    result = graph.invoke({
        "document_path": str(doc_path),
        "output_path": output,
        "instruction": args.instruction,
        "structure": "",
        "plan": [],
        "execution_log": [],
        "validation": {},
        "retry_count": 0,
    })

    if args.verbose:
        print(f"--- Document structure ---\n{result['structure']}\n")
        print(f"--- Edit plan ---\n{result['plan']}\n")
        print(f"--- Execution log ---")
        for entry in result["execution_log"]:
            print(f"  {entry}")
        print()

    v = result["validation"]
    status = "PASSED" if v.get("passed") else f"FAILED: {v.get('reason', 'unknown')}"
    print(f"Validation: {status}")
    print(f"Output: {output}")

    if v.get("differences"):
        print(f"Changes: {len(v['differences'])} paragraph(s) affected")

    if not v.get("passed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
