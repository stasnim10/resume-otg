# Utility functions for the Resume Replacer app

def parse_before_after_format(text):
    """
    Parse text blocks formatted as:
    BEFORE:
    some text
    
    AFTER:
    some text
    
    Returns a list of dictionaries with keys: "original" and "revised"
    """
    replacements = []
    blocks = text.strip().split('\n\n')
    
    current_block = {}
    for block in blocks:
        block = block.strip()
        if block.startswith('BEFORE:'):
            current_block['original'] = block.replace('BEFORE:', '').strip()
        elif block.startswith('AFTER:'):
            current_block['revised'] = block.replace('AFTER:', '').strip()
            if 'original' in current_block:
                replacements.append(current_block.copy())
                current_block = {}
    
    return replacements
