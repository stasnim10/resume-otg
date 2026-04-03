#!/usr/bin/env python3
"""
Resume Paragraph Extractor
Extracts all paragraphs from a .docx resume so you can copy them as anchors
"""
import sys
from docx import Document


def extract_paragraphs(docx_path: str):
    """
    Extract and display all paragraphs from a resume.
    Useful for creating JSON anchors.
    """
    doc = Document(docx_path)
    
    print("=" * 100)
    print("RESUME PARAGRAPHS (Copy these as match_anchor values)")
    print("=" * 100)
    print()
    
    bullet_markers = ["•", "●", "○", "·", "-"]
    
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        
        # Identify type
        is_bullet = any(text.startswith(marker) for marker in bullet_markers)
        is_summary = "MBA" in text and len(text) > 200
        is_heading = text.isupper() or (len(text) < 50 and text.endswith(":") == False)
        
        # Skip very short paragraphs (likely headings)
        if len(text) < 30 and not is_bullet:
            print(f"[{idx:02d}] HEADING: {text}")
            continue
        
        # Print with clear formatting
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
    
    print("=" * 100)
    print("USAGE: Copy any line above and use as your match_anchor in JSON")
    print("=" * 100)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_paragraphs.py <resume.docx>")
        print()
        print("Example:")
        print('  python extract_paragraphs.py "Simum Tasnim_Resume_Draft.docx"')
        sys.exit(1)
    
    docx_path = sys.argv[1]
    extract_paragraphs(docx_path)
