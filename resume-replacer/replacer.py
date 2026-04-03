from docx import Document
from difflib import SequenceMatcher

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def replace_bullets(doc_path, replacements, output_path="optimized_resume.docx"):
    doc = Document(doc_path)

    for para in doc.paragraphs:
        for change in replacements:
            if similarity(para.text.strip(), change["original"].strip()) > 0.92:
                para.text = change["revised"]

    doc.save(output_path)
    return output_path
