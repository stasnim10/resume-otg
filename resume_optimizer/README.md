# Resume AI Optimizer

A desktop application that uses OpenAI to optimize your resume against job descriptions. Features intelligent paragraph replacement while preserving document formatting.

## Features

- 🎯 Upload a resume (.docx) and job description
- 🤖 AI-powered optimization using OpenAI GPT-4
- 📝 Intelligent paragraph replacement
- 💾 Saves optimized resume as `[OriginalName]_Optimized.docx`
- 🛡️ Safe exact-match replacement (no regex, no partial edits)
- ✅ Error handling and status reporting

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Your OpenAI API Key

**Option A: Environment Variable (Recommended)**

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Option B: .env File**

Create a `.env` file in the project directory:
```
OPENAI_API_KEY=sk-your-key-here
```

Get your API key: https://platform.openai.com/api-keys

### 3. Run the Application

```bash
python main.py
```

## How to Use

1. **Upload Resume**: Click "Select Resume (.docx)" and choose your resume file
2. **Paste Job Description**: Paste the job description in the text area
3. **Click "Optimize Resume"**: The app will:
   - Extract text from your resume
   - Send it to OpenAI with the job description
   - Receive AI-generated recommendations
   - Apply changes to your document
   - Save as `[YourResume]_Optimized.docx`

## Project Structure

```
resume_optimizer/
├── main.py                  # Tkinter GUI application
├── llm_client.py           # OpenAI API client
├── docx_handler.py         # Word document processing
├── prompt_template.txt     # System prompt for LLM
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Technical Details

### Document Replacement Strategy

- Uses **exact substring matching** (no regex)
- Matches full paragraph text using `if anchor in paragraph.text`
- Throws errors if anchor not found or duplicates detected
- Preserves paragraph-level formatting

### JSON Extraction

- Extracts JSON from response using: `re.search(r'{[\s\S]*}\s*$', response_text)`
- Validates JSON using `json.loads()`
- Fails loudly with clear error messages

### API Model

Uses `gpt-4o-mini` for cost-effective optimization while maintaining quality.

## Optimization Targets

The system can optimize:

1. **Professional Summary** - Full text replacement
2. **Bullet Points** - Up to 5 key achievements
3. **Technical Skills** - Skills section alignment

## Error Handling

- Missing OpenAI API key → Clear error message
- Anchor not found → Throws error with anchor text
- Duplicate anchors → Throws error with count and anchor
- Invalid JSON → Throws JSON decode error with details

## Troubleshooting

### "OpenAI API key not found"
- Verify `OPENAI_API_KEY` environment variable is set
- Check that your API key is valid
- Restart the application after setting the key

### "Anchor not found"
- The text in your resume doesn't match the AI recommendation exactly
- This is a safety feature to prevent unintended replacements
- Check for whitespace differences or line breaks

### "Multiple matches found"
- The anchor text appears multiple times in your document
- Make the anchor more specific with surrounding context
- This prevents accidental replacements

## Requirements

- Python 3.11+
- OpenAI API key (https://platform.openai.com)
- .docx resume file (Microsoft Word format)

## Dependencies

- `python-docx` - Read/write .docx files
- `openai` - OpenAI API client
- `python-dotenv` - Load environment variables

## Safety Features

✅ No regex replacements - exact substring matching only  
✅ Full error reporting - never silently fails  
✅ Duplicate detection - stops if anchor appears multiple times  
✅ Style preservation - maintains paragraph formatting  
✅ Output confirmation - saves with clear naming convention  

## License

Proprietary - For personal use only
