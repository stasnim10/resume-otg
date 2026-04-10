"""
Handle .docx file operations: extraction and replacement
"""
from docx import Document
from typing import Tuple, List


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract plain text from a .docx file, including content inside tables.
    
    Args:
        file_path: Path to the .docx file
        
    Returns:
        Plain text content from the document
    """
    doc = Document(file_path)
    parts = []

    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag
        if tag == "p":
            from docx.text.paragraph import Paragraph
            para = Paragraph(block, doc)
            if para.text.strip():
                parts.append(para.text)
        elif tag == "tbl":
            from docx.table import Table
            table = Table(block, doc)
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        parts.append(cell_text)

    return "\n".join(parts)


def find_paragraph_by_anchor(doc, anchor: str) -> int:
    """
    Find a paragraph index by exact anchor text match.
    
    Args:
        doc: Document object
        anchor: Exact text to match
        
    Returns:
        Index of the matching paragraph
        
    Raises:
        ValueError: If anchor not found or duplicates found
    """
    matches = []
    for idx, para in enumerate(doc.paragraphs):
        if anchor in para.text:
            matches.append(idx)
    
    if len(matches) == 0:
        raise ValueError(f"❌ Anchor not found: '{anchor}'")
    elif len(matches) > 1:
        raise ValueError(f"❌ Multiple matches found ({len(matches)}) for anchor: '{anchor}'. Anchor must be unique.")
    
    return matches[0]


def replace_exact_paragraph(doc, anchor: str, new_text: str) -> bool:
    """
    Replace a paragraph that contains the anchor text with new text.
    Preserves paragraph formatting (style).
    
    Args:
        doc: Document object
        anchor: Exact substring to match in paragraph
        new_text: Text to replace the entire paragraph with
        
    Returns:
        True if replacement successful
        
    Raises:
        ValueError: If anchor not found or duplicates found
    """
    idx = find_paragraph_by_anchor(doc, anchor)
    para = doc.paragraphs[idx]
    
    # Preserve style
    style = para.style
    
    # Clear all runs in the paragraph
    for run in para.runs:
        run._element.getparent().remove(run._element)
    
    # Add new text with preserved style
    para.add_run(new_text)
    para.style = style
    
    return True


def replace_multiple_paragraphs(doc, replacements: List[dict]) -> dict:
    """
    Replace multiple paragraphs in a document.
    
    Args:
        doc: Document object
        replacements: List of dicts with keys:
                     - match_anchor (str)
                     - replacement_text (str)
        
    Returns:
        dict with keys:
        - success: bool
        - replaced_anchors: list of successfully replaced anchors
        - errors: list of error messages
    """
    replaced_anchors = []
    errors = []
    
    for item in replacements:
        anchor = item.get("match_anchor")
        new_text = item.get("replacement_text")
        
        if not anchor or not new_text:
            errors.append("Invalid replacement item: missing match_anchor or replacement_text")
            continue
        
        try:
            replace_exact_paragraph(doc, anchor, new_text)
            replaced_anchors.append(anchor)
            print(f"✅ Replaced: '{anchor[:50]}...'")
        except ValueError as e:
            errors.append(str(e))
            print(f"⚠️ {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "replaced_anchors": replaced_anchors,
        "errors": errors
    }


def save_optimized_document(doc, original_path: str, output_path: str) -> str:
    """
    Save the optimized document.
    
    Args:
        doc: Document object
        original_path: Original file path (for naming)
        output_path: Path to save the optimized document
        
    Returns:
        Path to saved file
    """
    doc.save(output_path)
    print(f"📄 Document saved: {output_path}")
    return output_path


def optimize_resume(
    resume_path: str,
    replacements: List[dict],
    output_path: str
) -> Tuple[bool, str]:
    """
    Main function: Load resume, apply replacements, save optimized version.
    
    Args:
        resume_path: Path to original .docx
        replacements: List of replacement dicts
        output_path: Path to save optimized .docx
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        doc = Document(resume_path)
        result = replace_multiple_paragraphs(doc, replacements)
        
        if result["errors"]:
            error_msg = "\n".join(result["errors"])
            return False, f"Errors during replacement:\n{error_msg}"
        
        save_optimized_document(doc, resume_path, output_path)
        return True, f"✅ Successfully optimized resume. Replaced {len(result['replaced_anchors'])} section(s)."
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}"
