"""
Resume Optimizer Web Application
Flask-based web interface for optimizing resumes with JSON-based replacements.
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from docx_handler import apply_replacements
from json_parser import extract_json_from_text, validate_payload

app = Flask(__name__)

_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    import secrets as _secrets
    _secret_key = _secrets.token_hex(32)
    print(
        "WARNING: SECRET_KEY environment variable is not set. "
        "A random key has been generated for this session — sessions will not persist across restarts. "
        "Set SECRET_KEY in your environment before deploying to production.",
        flush=True,
    )
app.secret_key = _secret_key
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'docx'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def cleanup_old_files():
    """Remove files older than 1 hour from uploads folder."""
    try:
        now = datetime.now().timestamp()
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                if file_age > 3600:  # 1 hour
                    os.remove(filepath)
    except Exception as e:
        print(f"Cleanup error: {e}")


@app.route('/')
def index():
    """Render main page."""
    return render_template('index.html')


@app.route('/optimize', methods=['POST'])
def optimize():
    """Process resume optimization request."""
    cleanup_old_files()
    
    # Validate file upload
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file uploaded'}), 400
    
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only .docx files are allowed'}), 400
    
    # Validate JSON payload
    json_text = request.form.get('json_payload', '').strip()
    if not json_text:
        return jsonify({'error': 'JSON payload is required'}), 400
    
    try:
        # Extract and validate JSON
        payload = extract_json_from_text(json_text)
        if not payload:
            return jsonify({'error': 'Invalid JSON format. Please check your JSON syntax.'}), 400
        
        is_valid, error_msg = validate_payload(payload)
        if not is_valid:
            return jsonify({'error': f'Invalid payload: {error_msg}'}), 400
        
    except json.JSONDecodeError as e:
        return jsonify({'error': f'JSON parsing error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Validation error: {str(e)}'}), 400
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(input_path)
    
    # Generate output filename
    base_name = os.path.splitext(unique_filename)[0]
    output_filename = f"{base_name}_Optimized.docx"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    
    try:
        # Apply replacements
        success, message = apply_replacements(input_path, payload, output_path)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'download_url': url_for('download', filename=output_filename)
            })
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': f'Processing error: {str(e)}'}), 500
    finally:
        # Clean up input file
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
        except:
            pass


@app.route('/download/<filename>')
def download(filename):
    """Serve optimized resume for download."""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return jsonify({'error': f'Download error: {str(e)}'}), 500


@app.route('/example-json')
def example_json():
    """Return example JSON payload."""
    example = {
        "summary_replacement": {
            "match_anchor": "MBA candidate and strategy-driven operations professional with 5+ years of experience optimizing supply chains and leading cross-functional teams to deliver measurable business impact.",
            "replacement_text": "Results-oriented MBA candidate with proven track record in supply chain optimization and cross-functional leadership, delivering $50M+ in cost savings and operational improvements."
        },
        "bullet_replacements": [
            {
                "match_anchor": "Directed a $50M supply chain transformation across 15 distribution centers, reducing operating costs by 22% and improving delivery times by 18% through data-driven inventory optimization and warehouse automation.",
                "replacement_text": "Spearheaded $50M supply chain transformation across 15 distribution centers, achieving 22% cost reduction and 18% faster delivery through advanced analytics and warehouse automation."
            },
            {
                "match_anchor": "Led team of 8 analysts in developing predictive demand forecasting models using Python and SQL, resulting in 30% reduction in stockouts and $5M annual savings.",
                "replacement_text": "Managed 8-person analytics team building ML-powered demand forecasting models (Python/SQL), cutting stockouts by 30% and generating $5M in annual savings."
            }
        ],
        "skills_replacements": [
            {
                "match_anchor": "Supply Chain & Operations: Supply Chain Management, Operations Management, Cloud Experience, Supply Chain Analytics",
                "replacement_text": "Supply Chain & Operations: Supply Chain Management, Operations Management, Network Optimization, Capacity Planning, Supplier Performance Management, Lean Process Improvement, Logistics Cost Optimization, KPI Governance"
            },
            {
                "match_anchor": "Analytics: Excel, SQL, Tableau",
                "replacement_text": "Analytics & Data Tools: Advanced Excel (Financial Modeling, Scenario Analysis), SQL, Tableau, Data Visualization, KPI Dashboard Development"
            },
            {
                "match_anchor": "Programming & Systems: Python, R, SAP",
                "replacement_text": "ERP & Enterprise Systems: SAP (Reporting & Data Extraction), CRM-Enabled Workflow Support, Programming & Technical Tools: Python, R"
            },
            {
                "match_anchor": "Web & Mobile Application: GitHub, Cursor, Google Firebase Studio, Figma, IOS app Developer, Xcode, Android app developer",
                "replacement_text": "Digital Product & Systems Exposure: GitHub, Firebase Studio, Figma, Xcode, Android Development Tools"
            }
        ]
    }
    return jsonify(example)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
