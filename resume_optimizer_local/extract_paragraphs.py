#!/usr/bin/env python3
"""
Resume Paragraph Extractor
Extracts all paragraphs (and table cells) from a .docx resume so you can
copy them as anchors for the JSON payload.
"""
import sys
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table


def extract_paragraphs(docx_path: str):
    """
    Extract and display all paragraphs and table-cell text from a resume.
    Useful for creating JSON anchors.
    """
    doc = Document(docx_path)
    
    print("=" * 100)
    print("RESUME PARAGRAPHS (Copy these as match_anchor values)")
    print("=" * 100)
    print()
    
    bullet_markers = ["•", "●", "○", "·", "-"]
    idx = 0

    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

        if tag == "p":
            para = Paragraph(block, doc)
            text = para.text.strip()
            if not text:
                continue
            _print_entry(idx, text, bullet_markers)
            idx += 1

        elif tag == "tbl":
            table = Table(block, doc)
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if not cell_text:
                        continue
                    print(f"[{idx:02d}] TABLE CELL:")
                    print(f'   "{cell_text}"')
                    print()
                    idx += 1
    
    print("=" * 100)
    print("USAGE: Copy any line above and use as your match_anchor in JSON")
    print("=" * 100)


def _print_entry(idx: int, text: str, bullet_markers: list):
    """Print a single paragraph entry with a type label."""
    is_bullet = any(text.startswith(marker) for marker in bullet_markers)
    is_summary = len(text) > 200

    if len(text) < 30 and not is_bullet:
        print(f"[{idx:02d}] HEADING: {text}")
        return

    if is_summary:
        print(f"[{idx:02d}] 📝 SUMMARY:")
        print(f'   "{text}"')
        print()
    elif is_bullet:
        print(f"[{idx:02d}] • BULLET:")
        print(f'   "{text}"')
        print()
    else:
        print(f"[{idx:02d}] PARAGRAPH:")
        print(f'   "{text}"')
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_paragraphs.py <resume.docx>")
        print()
        print("Example:")
        print('  python extract_paragraphs.py "Simum Tasnim_Resume_Draft.docx"')
        sys.exit(1)
    
    extract_paragraphs(sys.argv[1])
