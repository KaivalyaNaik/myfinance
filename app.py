from flask import Flask, request, send_file, abort, render_template_string
import tempfile
from parser import parse_bank_statement
import os
app = Flask(__name__)

@app.route('/')
def index():
    # Get list of supported banks from parser module
    try:
        from parser import BANKS
        bank_options = "".join([f'<option value="{bank}">{config["name"]}</option>' for bank, config in BANKS.items()])
    except ImportError:
        bank_options = ""
    
    # Simple HTML form to upload a PDF file with bank selection
    return render_template_string('''
    <!doctype html>
    <html>
    <head>
        <title>Bank Statement Parser</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            h1 {
                color: #333;
            }
            form {
                background-color: #f5f5f5;
                padding: 20px;
                border-radius: 5px;
            }
            label {
                display: block;
                margin: 10px 0 5px;
                font-weight: bold;
            }
            input[type="file"], select {
                margin-bottom: 15px;
                width: 100%;
                padding: 8px;
            }
            input[type="submit"] {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            input[type="submit"]:hover {
                background-color: #45a049;
            }
        </style>
    </head>
    <body>
        <h1>Bank Statement Parser</h1>
        <p>Upload your bank statement PDF to extract transactions into Excel format.</p>
        <form method="post" enctype="multipart/form-data" action="/upload">
            <label for="file">Select PDF Statement:</label>
            <input type="file" name="file" id="file" accept=".pdf">
            
            <label for="bank">Select Bank (optional, auto-detected if not selected):</label>
            <select name="bank" id="bank">
                <option value="">Auto-detect</option>
                {{ bank_options|safe }}
            </select>
            
            <input type="submit" value="Upload and Parse">
        </form>
    </body>
    </html>
    ''', bank_options=bank_options)

@app.route('/upload', methods=['POST'])
def upload():    
    if 'file' not in request.files:
        return abort(400, "No file part in the request")
    
    file = request.files['file']
    if file.filename == '':
        return abort(400, "No file selected for uploading")
    
    # Get selected bank
    bank_key = request.form.get('bank', '') or None
    
    try:
        # Create temporary files
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        file.save(temp_pdf.name)
        
        excel_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        
        # Call the new parse_bank_statement function
        result = parse_bank_statement(
            pdf_file=temp_pdf.name,
            excel_output=excel_file.name,
            bank_key=bank_key
        )
        
        if result is None:
            return abort(400, "Failed to parse the bank statement. Please check the PDF format.")
        
        return send_file(
            excel_file.name, 
            as_attachment=True, 
            download_name="transactions.xlsx"
        )
    except Exception as e:
        return abort(500, f"An error occurred: {str(e)}")
    finally:
        # Clean up temporary files
        if 'temp_pdf' in locals() and os.path.exists(temp_pdf.name):
            os.unlink(temp_pdf.name)
        if 'excel_file' in locals() and os.path.exists(excel_file.name):
            os.unlink(excel_file.name)

if __name__ == '__main__':
    app.run(debug=True)
