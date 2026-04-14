# Resume Optimizer OTG 📄✨

**On-The-Go Resume Optimization Tool** - Available as both desktop app and web application

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com/)

Upload your .docx resume, provide JSON-based optimizations, and download an enhanced version while preserving all formatting. Choose between **desktop app** (100% offline) or **web app** (accessible anywhere).

## 🎯 Key Features

- **🎨 Preserves Formatting** - All fonts, styles, and layouts stay intact
- **🔍 Strict Matching** - Full-paragraph equality (no substring guessing)
- **⚡ Deterministic** - Same input always produces same output
- **🔒 Privacy-Focused** - Desktop offline or web with auto-file-deletion
- **💰 Completely Free** - No API subscriptions needed
- **🛡️ Production-Grade** - Tested matching algorithm

## 📦 Choose Your Version

### 🖥️ [Desktop Edition](resume_optimizer_local/)
**Best for: Regular personal use, maximum privacy**

```bash
# Install and run
cd resume_optimizer_local
pip install -r requirements.txt
python main.py
```

**Features:**
- ✅ 100% offline - no internet required
- ✅ Tkinter GUI interface
- ✅ Instant processing on your machine
- ✅ Zero data leaves your computer
- ✅ Helper tool to extract paragraph text

**[→ Desktop Setup Guide](resume_optimizer_local/README.md)**

---

### 🌐 [Web Edition](resume_optimizer_web/)
**Best for: Sharing with friends, no-install access**

```bash
# Run locally
cd resume_optimizer_web
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
```

**Features:**
- ✅ Access from any browser
- ✅ No Python installation for users
- ✅ Drag & drop interface
- ✅ Deploy to free hosting (Render, Railway, PythonAnywhere)
- ✅ Auto-deletes files after 1 hour

**[→ Web Setup & Deployment Guide](resume_optimizer_web/README.md)**

---

## 🚀 Quick Start

### For End Users (Web Version)
1. Visit the deployed web app (ask admin for URL)
2. Upload your `.docx` resume
3. Paste your JSON optimization payload
4. Click "Optimize" and download!

### For Developers (Both Versions)
```bash
# Clone repository
git clone https://github.com/stasnim10/resume-optimizer-otg.git
cd resume-optimizer-otg

# Choose version:
# Desktop: cd resume_optimizer_local
# Web:     cd resume_optimizer_web

# Install dependencies
pip install -r requirements.txt

# Run
# Desktop: python main.py
# Web:     python app.py
```

## 📝 How to Create JSON Payload

### Step 1: Get Exact Paragraph Text

Use the app's review screen to copy exact paragraph text for anchors.

### Step 2: Create JSON

Copy **full paragraph text** and create JSON:

```json
{
  "summary_replacement": {
    "match_anchor": "MBA candidate and strategy-driven operations professional with 5+ years of experience...",
    "replacement_text": "Results-oriented MBA candidate with proven track record in supply chain optimization..."
  },
  "bullet_replacements": [
    {
      "match_anchor": "Directed a $50M supply chain transformation across 15 distribution centers...",
      "replacement_text": "Spearheaded $50M supply chain transformation achieving 22% cost reduction..."
    }
  ]
}
```

### Step 3: Get Optimized Text

**Option A:** Use ChatGPT/Claude
- Paste extracted paragraphs
- Ask: "Optimize these for [Job Title]"
- Request full-paragraph replacements

**Option B:** Manual editing
- Write your own improved versions

## 🛡️ Why This Tool is Better

| Traditional Tools | Resume Optimizer OTG |
|------------------|---------------------|
| ❌ Substring matching (leaves leftover text) | ✅ Full-paragraph equality matching |
| ❌ AI black boxes (inconsistent) | ✅ Manual control via JSON |
| ❌ Paid API subscriptions | ✅ Completely free |
| ❌ Formatting gets messed up | ✅ Preserves all formatting |
| ❌ Partial anchors cause issues | ✅ Strict matching catches errors |

## 📊 Comparison: Desktop vs Web

| Feature | Desktop | Web |
|---------|---------|-----|
| **Installation** | Python required | Browser only |
| **Privacy** | 100% offline | Files auto-deleted |
| **Speed** | Instant | Network dependent |
| **Access** | Local machine | Anywhere with internet |
| **Best Use** | Personal regular use | Sharing with others |
| **GUI** | Tkinter (native) | Modern Bootstrap UI |

## 🏗️ Project Structure

```
resume-optimizer-otg/
├── resume_optimizer_local/      # Desktop version (tkinter)
│   ├── main.py                  # GUI application
│   ├── docx_handler.py          # Core document processing
│   ├── json_parser.py           # JSON validation
│   ├── requirements.txt
│   └── README.md
│
├── resume_optimizer_web/        # Web version (Flask)
│   ├── app.py                   # Flask application
│   ├── docx_handler.py          # Core document processing
│   ├── json_parser.py           # JSON validation
│   ├── templates/
│   │   └── index.html          # Web interface
│   ├── requirements.txt
│   ├── Procfile                # Deployment config
│   └── README.md
│
└── README.md                    # This file
```

## 🎓 Core Technology

### Strict Equality Matching

```python
# Safe deterministic matching
if paragraph.text.strip() == anchor.strip():
    replace_paragraph_text(para, new_text)
```

**Benefits:**
- ✅ No ambiguity - exact match required
- ✅ Catches errors immediately
- ✅ Immune to formatting differences
- ✅ No leftover text issues

## ⚠️ Important Notes

- **Use FULL paragraph text as anchors** - Not just first few words!
- **Anchors must be unique** - Tool will error if duplicates found
- **Only .docx supported** - Not .doc or PDF
- **Strict equality matching** - Text must match exactly (whitespace normalized)
- **No skills_replacement** - Only summary and bullet replacements

## 🤝 Contributing

Found a bug or have a feature request? [Open an issue](https://github.com/stasnim10/resume-optimizer-otg/issues)!

## 📄 License

MIT License - See LICENSE file for details

## 🔗 Links

- **GitHub Repository:** https://github.com/stasnim10/resume-optimizer-otg
- **Desktop Guide:** [resume_optimizer_local/README.md](resume_optimizer_local/README.md)
- **Web Guide:** [resume_optimizer_web/README.md](resume_optimizer_web/README.md)

## 💡 Tips for Best Results

1. **Use the review screen first** to copy exact anchor text
2. **Copy exact text** - don't truncate or modify
3. **Keep replacement length similar** to preserve layout
4. **Test with small changes first** before full optimization
5. **Use ChatGPT/Claude** to generate polished replacement text

## 🎉 Success Stories

> "Fixed my formatting issues! The strict matching prevented the leftover text problem I had with other tools." - Beta Tester

> "Web version makes it easy to help friends optimize their resumes without asking them to install Python!" - Early Adopter

---

**Made with ❤️ for job seekers** | Report Issues: https://github.com/stasnim10/resume-optimizer-otg/issues
