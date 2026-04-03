# Resume Optimizer - Complete Suite 🚀

A deterministic resume optimization tool available in **two versions**: Desktop (offline) and Web (browser-based). Upload a .docx resume and provide JSON replacement payload for summary and bullet points.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📦 Choose Your Version

### 🖥️ Desktop Edition (This Folder)
**Best for:** Regular personal use, maximum privacy
- ✅ 100% offline - no internet required
- ✅ Runs on your computer with Python
- ✅ Instant processing
- ✅ Zero data leaves your machine

👉 **[Setup Instructions](#setup)** below

### 🌐 Web Edition
**Best for:** Sharing with friends, no-install access
- ✅ Access from any browser
- ✅ No Python installation needed
- ✅ Drag & drop interface
- ✅ Deploy to free hosting (Render, Railway)

👉 **[View Web Version](../resume_optimizer_web/)** - Separate folder with deployment guide

---

# Desktop Edition - Local Offline Version

Desktop application for deterministic resume optimization. No API calls, fully offline, completely free.

## Features

- 🖥️ **Desktop GUI** (tkinter) - No web server required
- 🔒 **Fully Offline** - No API calls, no internet needed
- 💰 **Completely Free** - No AI subscriptions
- 📝 **Exact Matching** - Safe deterministic paragraph replacement using strict equality
- 📄 **Preserves Formatting** - Maintains document structure and styling
- ⚡ **Fail-Safe** - Clear errors for missing or duplicate anchors
- 🎯 **Production-Grade** - Uses full-paragraph matching for 100% reliability

## Why This Tool?

Traditional resume optimizers use:
- ❌ Partial text matching (leaves leftover text)
- ❌ Substring replacement (can match wrong paragraphs)
- ❌ AI rewrites (inconsistent results)

This tool uses:
- ✅ **Strict full-paragraph equality** matching
- ✅ **Deterministic replacements** (same input = same output)
- ✅ **Manual control** (you provide optimized text via JSON)
- ✅ **Zero ambiguity** (errors if anchor not found or duplicated)

## Setup

### 1. Install Python 3.11+

Verify installation:
```bash
python3 --version
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs only:
- `python-docx` (for .docx handling)

### 3. Run the Application

```bash
python main.py
```

The tkinter GUI will open.

## How to Use

### Step 1: Upload Resume
Click **📁 Select Resume** and choose your `.docx` file.

### Step 2: Prepare JSON Payload
The app includes an example JSON structure. Replace it with your payload.

**JSON Format:**

```json
{
  "summary_replacement": {
    "match_anchor": "FULL exact summary paragraph from your resume",
    "replacement_text": "New optimized summary"
  },
  "bullet_replacements": [
    {
      "match_anchor": "FULL exact bullet text from resume (entire sentence/paragraph)",
      "replacement_text": "Optimized bullet"
    }
  ]
}
```

**CRITICAL RULES:**
- `match_anchor` **MUST** be the complete paragraph text from your resume
- Copy the **entire bullet or summary** - not just first few words
- Match is done using strict equality: `paragraph == anchor`
- If anchor not found → error
- If anchor duplicated → error
- All fields optional, include only what you want to change

**Why full paragraphs?**
- Partial anchors cause mismatches and leave leftover text
- Full-text matching is deterministic and safe
- Immune to formatting differences
- No risk of matching wrong paragraphs

### Step 3: Click "🚀 Optimize Resume"

The app will:
1. ✅ Validate JSON
2. ✅ Find exact paragraphs to replace
3. ✅ Apply replacements
4. ✅ Save as `[OriginalName]_Optimized.docx`

Output shows:
- Which anchors were replaced
- Errors if any anchors not found
- Final file location

## How to Get Full Paragraph Text (Easy Method)

Use the included **paragraph extractor** tool:

```bash
python extract_paragraphs.py "YourResume.docx"
```

This will display all paragraphs from your resume with numbers:
```
[01] 📝 SUMMARY:
   "MBA candidate and strategy-driven operations professional..."

[16] PARAGRAPH:
   "Directed a $50M supply chain transformation across 15 distribution centers..."
```

**Copy the exact text** (without quotes) and use as your `match_anchor` in JSON.

## How to Get Optimized Text

### Option A: ChatGPT / Claude
1. Extract paragraphs using the tool above
2. Paste into ChatGPT: "Optimize these resume bullets for [Job Title]"
3. Ask for full-paragraph replacements (not just keywords)
4. Copy optimized text into `replacement_text`

### Option B: Manual Editing
Write your own improved versions maintaining similar length.

**Pro Tip:** Keep replacement length similar to original to preserve formatting:
- Original 1 line → Replacement ~1 line
- Original 3 lines → Replacement ~3 lines

## Project Folder

```
resume_optimizer_local/
├── main.py              # Tkinter GUI
├── docx_handler.py      # Document operations
├── json_parser.py       # JSON validation
├── requirements.txt     # Dependencies
└── README.md           # This file
```

## Upload to GitHub

### Create .gitignore

```
__pycache__/
*.pyc
.DS_Store
*_Optimized.docx
```

### Initialize Repository

```bash
git init
git add .
git commit -m "Initial commit: Resume Optimizer offline tool"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/resume-optimizer-local.git
git push -u origin main
```

## Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| "No JSON block found" | Malformed JSON | Verify JSON is valid (use jsonlint.com) |
| "Invalid JSON" | JSON syntax error | Check brackets, quotes, commas |
| "Anchor not found" | Text not in resume | Match anchor exactly (copy from resume) |
| "Multiple matches found" | Anchor appears twice | Make anchor more specific |

## Technical Details

### No Regex for Document Replacement
- Uses simple substring matching: `if anchor in paragraph.text`
- Replaces entire paragraph preserving style
- Zero risk of unintended partial replacements

### JSON Parsing
- Extracts JSON using: `re.search(r'{[\s\S]*}\s*$', text)`
- Validates with: `json.loads()`
- Fails immediately if invalid

### Safety
- ✅ No silent failures
- ✅ Duplicate detection
- ✅ Clear error messages
- ✅ No partial replacements
- ✅ Preserves formatting

## Requirements

- Python 3.11+
- python-docx
- tkinter (included with Python on most systems)

## Why This Approach?

✅ **Free** - No API costs
✅ **Fast** - No network latency
✅ **Safe** - Deterministic replacements
✅ **Private** - Everything stays on your computer
✅ **Simple** - Just JSON and a button
✅ **Reliable** - No API rate limits or downtime

## License

MIT - Use freely, modify as needed.

---

**Built for precision. Zero compromise on safety.**
