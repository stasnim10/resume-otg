"""
Handle .docx and .pdf file operations: extraction and deterministic replacement
Word-style Find & Replace that preserves formatting for .docx
"""
import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches
from typing import List, Tuple, Dict, Any


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract plain text from PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Full plain text from document

    Raises:
        ImportError: If PyPDF2 is not installed
        RuntimeError: If PDF extraction fails
    """
    try:
        import PyPDF2
    except ImportError:
        raise ImportError("PyPDF2 is required for PDF support. Install with: pip install PyPDF2")

    try:
        text_parts = []
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {str(e)}")


def extract_text(doc_path: str) -> str:
    """
    Extract plain text from .docx or .pdf file.

    Args:
        doc_path: Path to .docx or .pdf file

    Returns:
        Full plain text from document
    """
    if doc_path.lower().endswith('.pdf'):
        return extract_text_from_pdf(doc_path)
    else:
        # Default to .docx handling
        doc = Document(doc_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text


def replace_paragraph_text(para, replacement: str) -> bool:
    """
    Replace entire paragraph text while preserving formatting.
    
    Args:
        para: Paragraph object
        replacement: New text for the entire paragraph
        
    Returns:
        True if replacement successful
    """
    if not para.runs:
        para.add_run(replacement)
        return True
    
    # Get formatting from first run
    first_run = para.runs[0]
    first_fmt = {
        'bold': first_run.bold,
        'italic': first_run.italic,
        'underline': first_run.underline,
        'font_name': first_run.font.name,
        'font_size': first_run.font.size,
        'font_color': first_run.font.color.rgb if hasattr(first_run.font.color, 'rgb') else None,
    }
    
    # Clear all runs
    for run in para.runs:
        r = run._element
        r.getparent().remove(r)
    
    # Add replacement text with original formatting
    new_run = para.add_run(replacement)
    new_run.bold = first_fmt['bold']
    new_run.italic = first_fmt['italic']
    new_run.underline = first_fmt['underline']
    if first_fmt['font_name']:
        new_run.font.name = first_fmt['font_name']
    if first_fmt['font_size']:
        new_run.font.size = first_fmt['font_size']
    if first_fmt['font_color']:
        try:
            new_run.font.color.rgb = first_fmt['font_color']
        except:
            pass
    
    return True


def replace_exact_paragraph(doc, anchor: str, new_text: str) -> str:
    """
    Replace a paragraph using STRICT FULL-TEXT EQUALITY.
    
    This is deterministic and safe:
    - Matches only if paragraph.text.strip() == anchor.strip()
    - No substring matching
    - No partial anchors
    - Immune to formatting differences
    
    Args:
        doc: Document object
        anchor: FULL paragraph text (exact match required)
        new_text: Replacement text
        
    Returns:
        Success message
        
    Raises:
        ValueError: If no match or duplicates found
    """
    matches = []
    for idx, para in enumerate(doc.paragraphs):
        # STRICT EQUALITY - not substring matching
        if para.text.strip() == anchor.strip():
            matches.append((idx, para))
    
    if len(matches) == 0:
        raise ValueError(f"❌ Anchor not found (must be FULL paragraph text): '{anchor[:80]}...'")
    elif len(matches) > 1:
        raise ValueError(f"❌ Multiple matches found ({len(matches)}) for anchor: '{anchor[:80]}...'")
    
    idx, para = matches[0]
    
    # Replace entire paragraph
    replace_paragraph_text(para, new_text)
    
    return f"✅ Replaced: '{anchor[:60]}...'"


def apply_replacements(doc_path: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Apply all replacements from payload to document.
    Preserves formatting like Word's Find & Replace.
    
    Args:
        doc_path: Path to .docx file
        payload: Validated replacement payload
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        doc = Document(doc_path)
        replaced_anchors = []
        errors = []
        
        # Summary replacement
        if "summary_replacement" in payload:
            sr = payload["summary_replacement"]
            try:
                msg = replace_exact_paragraph(doc, sr["match_anchor"], sr["replacement_text"])
                replaced_anchors.append(sr["match_anchor"])
                print(msg)
            except ValueError as e:
                errors.append(str(e))
                print(str(e))
        
        # Bullet replacements
        if "bullet_replacements" in payload:
            for idx, bullet in enumerate(payload["bullet_replacements"]):
                try:
                    msg = replace_exact_paragraph(doc, bullet["match_anchor"], bullet["replacement_text"])
                    replaced_anchors.append(bullet["match_anchor"])
                    print(msg)
                except ValueError as e:
                    errors.append(str(e))
                    print(str(e))
        
        # Skills replacements
        if "skills_replacements" in payload:
            for idx, skill in enumerate(payload["skills_replacements"]):
                try:
                    msg = replace_exact_paragraph(doc, skill["match_anchor"], skill["replacement_text"])
                    replaced_anchors.append(skill["match_anchor"])
                    print(msg)
                except ValueError as e:
                    errors.append(str(e))
                    print(str(e))
        
        # If any errors, fail
        if errors:
            error_summary = "\n".join(errors)
            return False, f"Errors during replacement:\n{error_summary}"
        
        # Save file
        output_path = generate_output_filename(doc_path)
        doc.save(output_path)
        
        msg = f"✅ Successfully optimized resume!\nReplaced {len(replaced_anchors)} section(s).\n📄 Saved: {output_path}"
        return True, msg
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}"


def apply_cover_letter_replacements(doc_path: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Apply cover letter replacements from payload to document.

    Expected keys (all optional):
    - paragraph_1_replacement (object)
    - capability_replacements (list)
    - final_paragraph_replacement (object)
    """
    try:
        doc = Document(doc_path)
        replaced_anchors = []
        errors = []

        if "paragraph_1_replacement" in payload:
            pr = payload["paragraph_1_replacement"]
            try:
                msg = replace_exact_paragraph(doc, pr["match_anchor"], pr["replacement_text"])
                replaced_anchors.append(pr["match_anchor"])
                print(msg)
            except ValueError as e:
                errors.append(str(e))
                print(str(e))

        if "capability_replacements" in payload:
            for idx, cap in enumerate(payload["capability_replacements"]):
                try:
                    msg = replace_exact_paragraph(doc, cap["match_anchor"], cap["replacement_text"])
                    replaced_anchors.append(cap["match_anchor"])
                    print(msg)
                except ValueError as e:
                    errors.append(str(e))
                    print(str(e))

        if "final_paragraph_replacement" in payload:
            fr = payload["final_paragraph_replacement"]
            try:
                msg = replace_exact_paragraph(doc, fr["match_anchor"], fr["replacement_text"])
                replaced_anchors.append(fr["match_anchor"])
                print(msg)
            except ValueError as e:
                errors.append(str(e))
                print(str(e))

        if errors:
            error_summary = "\n".join(errors)
            return False, f"Errors during replacement:\n{error_summary}"

        output_path = generate_output_filename(doc_path)
        doc.save(output_path)

        msg = (
            "✅ Successfully optimized cover letter!\n"
            f"Replaced {len(replaced_anchors)} section(s).\n"
            f"📄 Saved: {output_path}"
        )
        return True, msg

    except Exception as e:
        return False, f"❌ Error: {str(e)}"


def generate_output_filename(original_path: str, suffix: str = "_Optimized") -> str:
    """
    Generate output filename with _Optimized suffix.
    
    Args:
        original_path: Original file path
        
    Returns:
        New file path with _Optimized suffix
    """
    from pathlib import Path
    path = Path(original_path)
    output_name = f"{path.stem}{suffix}{path.suffix}"
    output_path = path.parent / output_name
    return str(output_path)


def save_cover_letter_content(template_path: str, content: str, output_path: str) -> Tuple[bool, str]:
    """
    Replace cover letter body content while preserving template formatting.
    
    Workflow:
    1. Load template document
    2. Keep header greeting "Dear Hiring Manager:"
    3. Remove body paragraphs after greeting
    4. Clean markdown from content:
       - Remove ** bold markers (keep text plain)
       - Remove * bullet markers (keep as plain paragraphs)
    5. Add cleaned paragraphs
    6. Save to output path
    
    Args:
        template_path: Path to template/draft .docx file
        content: New cover letter text from textarea (may contain markdown)
        output_path: Path where to save the updated .docx file
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        doc = Document(template_path)
        
        # Find where body starts (after "Dear Hiring Manager:")
        body_start_idx = 0
        for idx, para in enumerate(doc.paragraphs):
            if "dear" in para.text.lower() and "manager" in para.text.lower():
                body_start_idx = idx + 1
                break
        
        # Remove body paragraphs (everything after the greeting)
        for idx in range(len(doc.paragraphs) - 1, body_start_idx, -1):
            p = doc.paragraphs[idx]._element
            p.getparent().remove(p)
        
        # Clean markdown and add paragraphs
        lines = content.strip().split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                continue
            
            # Remove ** bold markers (keep text plain)
            if line_stripped.startswith('**') and line_stripped.endswith('**'):
                cleaned_text = line_stripped[2:-2]
                doc.add_paragraph(cleaned_text)
            
            # Remove * bullet markers (keep as plain paragraphs)
            elif line_stripped.startswith('*'):
                cleaned_text = line_stripped[1:].strip()
                doc.add_paragraph(cleaned_text)
            
            # Normal paragraph text
            else:
                doc.add_paragraph(line_stripped)
        
        # Ensure directory exists
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save document
        doc.save(output_path)
        
        msg = f"✅ Cover letter updated successfully!\n📄 Saved to: {output_path}"
        return True, msg
        
    except Exception as e:
        return False, f"❌ Error updating cover letter: {str(e)}"


def _clean_markdown(text: str) -> str:
    """
    Remove markdown formatting from text.
    
    Removes:
    - ** bold markers ** → text
    - * bullet points → text
    - Extra whitespace
    
    Args:
        text: Text with potential markdown
        
    Returns:
        Cleaned text
    """
    import re
    
    # Remove ** bold markers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    
    # Remove * bullet markers at start of lines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove leading * (bullet) and trim
        line = re.sub(r'^\s*\*\s+', '', line)
        cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    return text


def _set_default_page_layout(doc: Document) -> None:
    """Apply simple ATS-friendly page settings."""
    section = doc.sections[0]
    section.top_margin = Inches(0.6)
    section.bottom_margin = Inches(0.6)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)


def _add_section_heading(doc: Document, title: str) -> None:
    """Add a simple resume section heading."""
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(title.upper())
    run.bold = True
    run.font.size = Pt(11)
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(2)


def _add_bullets(doc: Document, items: List[str]) -> None:
    """Add bullet items using Word's built-in list style."""
    for item in items:
        bullet = doc.add_paragraph(style="List Bullet")
        bullet.paragraph_format.space_after = Pt(0)
        bullet.add_run(item)


def build_resume_from_scratch(payload: Dict[str, Any]) -> bytes:
    """
    Build a simple ATS-friendly resume document from validated builder JSON.

    Returns the .docx file bytes so the UI can offer a direct download.
    """
    doc = Document()
    _set_default_page_layout(doc)

    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(10.5)

    basics = payload.get("basics", {})

    name_paragraph = doc.add_paragraph()
    name_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_paragraph.add_run(basics.get("full_name", ""))
    name_run.bold = True
    name_run.font.size = Pt(16)

    contact_parts = [
        basics.get("email", ""),
        basics.get("phone", ""),
        basics.get("location", ""),
        basics.get("linkedin", ""),
    ]
    contact_line = " | ".join([part for part in contact_parts if part])
    if contact_line:
        contact_paragraph = doc.add_paragraph()
        contact_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_paragraph.add_run(contact_line)
        contact_paragraph.paragraph_format.space_after = Pt(6)

    summary = payload.get("summary", "").strip()
    if summary:
        _add_section_heading(doc, "Summary")
        doc.add_paragraph(summary)

    education_items = payload.get("education", [])
    if education_items:
        _add_section_heading(doc, "Education")
        for item in education_items:
            paragraph = doc.add_paragraph()
            school_run = paragraph.add_run(item.get("school", ""))
            school_run.bold = True
            degree = item.get("degree", "")
            graduation_date = item.get("graduation_date", "")
            trailing = " | ".join([part for part in [degree, graduation_date] if part])
            if trailing:
                paragraph.add_run(f" | {trailing}")
            details = item.get("details", [])
            if details:
                _add_bullets(doc, details)

    experience_items = payload.get("experience", [])
    if experience_items:
        _add_section_heading(doc, "Experience")
        for item in experience_items:
            paragraph = doc.add_paragraph()
            title_run = paragraph.add_run(item.get("title", ""))
            title_run.bold = True
            organization = item.get("organization", "")
            location = item.get("location", "")
            dates = item.get("dates", "")
            trailing = " | ".join([part for part in [organization, location, dates] if part])
            if trailing:
                paragraph.add_run(f" | {trailing}")
            bullets = item.get("bullets", [])
            if bullets:
                _add_bullets(doc, bullets)

    project_items = payload.get("projects", [])
    if project_items:
        _add_section_heading(doc, "Projects")
        for item in project_items:
            paragraph = doc.add_paragraph()
            name_run = paragraph.add_run(item.get("name", ""))
            name_run.bold = True
            details = item.get("details", [])
            if details:
                _add_bullets(doc, details)

    skill_items = payload.get("skills", [])
    if skill_items:
        _add_section_heading(doc, "Skills")
        doc.add_paragraph(", ".join(skill_items))

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

