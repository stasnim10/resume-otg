# Resume Optimizer - Web Edition 🌐

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

**Browser-based resume optimization tool** - Upload your .docx resume, paste JSON replacements, and download the optimized version. No installation required for users!

## 🎯 Features

- **🌐 Web-based interface** - Access from any browser
- **📤 Drag & drop upload** - Easy file handling
- **✨ Preserves formatting** - All fonts, styles, and layouts stay intact
- **🔒 Privacy-focused** - Files auto-deleted after 1 hour
- **🎨 Modern UI** - Clean, responsive design with Bootstrap
- **⚡ Fast processing** - Instant optimization and download
- **🔍 Strict matching** - Uses full-paragraph equality for reliability

## 🚀 Quick Start

### Run Locally

```bash
# 1. Clone repository
git clone https://github.com/stasnim10/resume-optimizer-otg.git
cd resume-optimizer-otg/resume_optimizer_web

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py

# 5. Open browser to http://localhost:5000
```

## 🌍 Deploy to Production

### Deploy to Render (Free)

1. **Create Render account** at [render.com](https://render.com)

2. **New Web Service** → Connect your GitHub repository

3. **Configure settings:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Environment:** Python 3.11+

4. Click **Create Web Service**

Your app will be live at `https://your-app.onrender.com`

### Deploy to Railway (Free Tier)

1. **Create Railway account** at [railway.app](https://railway.app)

2. **New Project** → Deploy from GitHub

3. **Select repository** and branch

4. Railway auto-detects Flask and deploys!

Your app will be live at `https://your-app.up.railway.app`

### Deploy to PythonAnywhere

1. **Create account** at [pythonanywhere.com](https://www.pythonanywhere.com)

2. **Upload code** via Files tab or Git

3. **Create web app:**
   - Python 3.11
   - Manual configuration
   - Set WSGI file to point to `app.py`

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

Your app will be live at `https://yourusername.pythonanywhere.com`

## 📝 How to Use

### Step 1: Upload Resume
- Click upload zone or drag & drop your `.docx` resume
- Only `.docx` files supported (max 16MB)

### Step 2: Prepare JSON Payload

#### Get Full Paragraph Text
Use the desktop version's extraction tool:
```bash
cd resume_optimizer_local
python extract_paragraphs.py "YourResume.docx"
```

This shows all paragraphs with numbers - copy the exact text.

#### Create JSON
Click **"Load Example JSON"** in the web app or create manually:

```json
{
  "summary_replacement": {
    "match_anchor": "MBA candidate and strategy-driven operations professional with 5+ years of experience optimizing supply chains and leading cross-functional teams to deliver measurable business impact.",
    "replacement_text": "Results-oriented MBA candidate with proven track record in supply chain optimization and cross-functional leadership, delivering $50M+ in cost savings."
  },
  "bullet_replacements": [
    {
      "match_anchor": "Directed a $50M supply chain transformation across 15 distribution centers, reducing operating costs by 22% and improving delivery times by 18% through data-driven inventory optimization.",
      "replacement_text": "Spearheaded $50M supply chain transformation across 15 distribution centers, achieving 22% cost reduction and 18% faster delivery through advanced analytics."
    }
  ]
}
```

### Step 3: Optimize & Download
- Click **"Optimize Resume"**
- Download your optimized resume in seconds!

## 🔧 Configuration

### Environment Variables

Create `.env` file for production:

```bash
SECRET_KEY=your-secret-key-here
MAX_CONTENT_LENGTH=16777216  # 16MB in bytes
```

### File Cleanup

Files are auto-deleted after 1 hour. Adjust in `app.py`:

```python
if file_age > 3600:  # Change 3600 to desired seconds
```

## 🛡️ Security Features

- ✅ **File type validation** - Only `.docx` allowed
- ✅ **Size limits** - Max 16MB per file
- ✅ **Secure filenames** - Werkzeug's `secure_filename()`
- ✅ **Auto cleanup** - Files deleted after 1 hour
- ✅ **No permanent storage** - Temporary processing only
- ✅ **CSRF protection** - Flask secret key

## 📊 API Endpoints

### `GET /`
Render main interface

### `POST /optimize`
Process resume optimization

**Request:**
- Form data with `resume` file and `json_payload` text

**Response:**
```json
{
  "success": true,
  "message": "Successfully optimized!",
  "download_url": "/download/filename.docx"
}
```

### `GET /download/<filename>`
Download optimized resume

### `GET /example-json`
Get example JSON payload

### `GET /health`
Health check endpoint

## 🏗️ Project Structure

```
resume_optimizer_web/
├── app.py                 # Flask application
├── docx_handler.py        # Document processing (strict equality matching)
├── json_parser.py         # JSON validation
├── requirements.txt       # Dependencies
├── Procfile              # Deployment config (Heroku/Render)
├── runtime.txt           # Python version
├── templates/
│   └── index.html        # Main web interface
├── static/               # (Future: custom CSS/JS)
└── uploads/              # Temporary file storage
```

## 🔄 Desktop vs Web Version

| Feature | Desktop (Local) | Web Edition |
|---------|----------------|-------------|
| **Installation** | Python required | No installation |
| **Privacy** | 100% offline | Files auto-deleted |
| **Speed** | Instant | Network dependent |
| **Accessibility** | Local machine only | Access anywhere |
| **Best For** | Regular users | Sharing with friends |

## 🤝 Contributing

Found a bug or have a feature request? Open an issue on GitHub!

## 📄 License

MIT License - See LICENSE file for details

## 🔗 Related Projects

- **Desktop Version:** `resume_optimizer_local/` - Offline tkinter GUI
- **GitHub Repository:** https://github.com/stasnim10/resume-optimizer-otg

## 💡 Tips

1. **Use full paragraphs as anchors** - Not just first few words!
2. **Keep replacements similar length** - Preserves document layout
3. **Test with example JSON first** - Click "Load Example" button
4. **Extract paragraphs with desktop tool** - Use `extract_paragraphs.py`

## ⚠️ Important Notes

- **Full-paragraph matching only** - Partial anchors will fail
- **Strict equality** - Text must match exactly (case/spacing ignored)
- **No skills_replacement** - Only summary and bullet replacements
- **One match only** - Anchors must be unique in document

## 🎓 How It Works

1. User uploads `.docx` resume
2. Server validates file and JSON payload
3. `docx_handler.py` uses strict equality matching:
   ```python
   if paragraph.text.strip() == anchor.strip():
       replace_paragraph_text(para, new_text)
   ```
4. Optimized resume saved to `uploads/`
5. User downloads file
6. Files auto-deleted after 1 hour

---

**Made with ❤️ for job seekers** | [Report Issues](https://github.com/stasnim10/resume-optimizer-otg/issues)
