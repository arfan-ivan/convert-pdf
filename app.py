from flask import Flask, render_template, request, jsonify
import os
import subprocess
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
import pdf2image
import img2pdf
from pdf2docx import Converter
import pytesseract
from PIL import Image
import pandas as pd
from fpdf import FPDF
from pptx import Presentation
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf', 'docx', 'xlsx', 'pptx'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    clean_old_files()  # Bersihkan file lama sebelum upload baru
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'success': True, 'filename': filename, 'filepath': filepath})
    return jsonify({'error': 'Invalid file format'})

@app.route('/pdf-to-img', methods=['POST'])
def pdf_to_img():
    """Konversi PDF ke gambar"""
    data = request.json
    pdf_path = data.get('filepath')
    if not pdf_path:
        return jsonify({'error': 'Filepath missing'})
    
    images = pdf2image.convert_from_path(pdf_path)
    image_paths = []
    for i, img in enumerate(images):
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], f'page_{i}.png')
        img.save(img_path, 'PNG')
        image_paths.append(img_path)
    
    return jsonify({'success': True, 'image_paths': image_paths})

@app.route('/img-to-pdf', methods=['POST'])
def img_to_pdf():
    """Konversi gambar ke PDF"""
    data = request.json
    img_paths = data.get('filepaths')

    if not img_paths or not isinstance(img_paths, list):
        return jsonify({'error': 'Filepaths missing or incorrect format'})

    valid_img_paths = []
    for img_path in img_paths:
        abs_path = os.path.abspath(img_path)
        print(f"Checking file: {abs_path}")  # Debugging
        if os.path.exists(abs_path) and img_path.lower().endswith(('png', 'jpg', 'jpeg')):
            valid_img_paths.append(abs_path)
        else:
            return jsonify({'error': f'Invalid image file: {img_path}'})

    if not valid_img_paths:
        return jsonify({'error': 'No valid images found for conversion'})

    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'output.pdf')

    try:
        with open(pdf_path, 'wb') as f:
            f.write(img2pdf.convert(valid_img_paths))
    except Exception as e:
        return jsonify({'error': f'Failed to convert images to PDF: {str(e)}'})

    return jsonify({'success': True, 'pdf_path': pdf_path})

@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    """Konversi PDF ke Word"""
    data = request.json
    pdf_path = data.get('filepath')
    if not pdf_path:
        return jsonify({'error': 'Filepath missing'})

    word_path = os.path.splitext(pdf_path)[0] + ".docx"
    cv = Converter(pdf_path)
    cv.convert(word_path)
    cv.close()
    
    return jsonify({'success': True, 'word_path': word_path})

@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    """Konversi Word ke PDF menggunakan LibreOffice"""
    data = request.json
    word_path = data.get('filepath')
    if not word_path:
        return jsonify({'error': 'Filepath missing'})

    pdf_path = os.path.splitext(word_path)[0] + ".pdf"
    command = ["libreoffice", "--headless", "--convert-to", "pdf", word_path, "--outdir", app.config['UPLOAD_FOLDER']]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return jsonify({'success': True, 'pdf_path': pdf_path})

@app.route('/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    """Konversi Excel ke PDF menggunakan LibreOffice"""
    data = request.json
    excel_path = data.get('filepath')
    if not excel_path:
        return jsonify({'error': 'Filepath missing'})

    pdf_path = os.path.splitext(excel_path)[0] + ".pdf"
    command = ["libreoffice", "--headless", "--convert-to", "pdf", excel_path, "--outdir", app.config['UPLOAD_FOLDER']]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return jsonify({'success': True, 'pdf_path': pdf_path})

@app.route('/ppt-to-pdf', methods=['POST'])
def ppt_to_pdf():
    """Konversi PowerPoint ke PDF menggunakan LibreOffice"""
    data = request.json
    ppt_path = data.get('filepath')
    if not ppt_path:
        return jsonify({'error': 'Filepath missing'})

    pdf_path = os.path.splitext(ppt_path)[0] + ".pdf"
    command = ["libreoffice", "--headless", "--convert-to", "pdf", ppt_path, "--outdir", app.config['UPLOAD_FOLDER']]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return jsonify({'success': True, 'pdf_path': pdf_path})

@app.route('/split-pdf', methods=['POST'])
def split_pdf():
    """Pisahkan halaman PDF"""
    data = request.json
    pdf_path = data.get('filepath')
    pages = data.get('pages', [])
    if not pdf_path or not pages:
        return jsonify({'error': 'Filepath or pages missing'})

    pdf_doc = fitz.open(pdf_path)
    split_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'split.pdf')
    new_pdf = fitz.open()

    for page in pages:
        new_pdf.insert_pdf(pdf_doc, from_page=page-1, to_page=page-1)

    new_pdf.save(split_pdf_path)
    return jsonify({'success': True, 'pdf_path': split_pdf_path})

@app.route('/ocr', methods=['POST'])
def ocr():
    """Ekstrak teks dari gambar (OCR)"""
    data = request.json
    img_path = data.get('filepath')
    if not img_path:
        return jsonify({'error': 'Filepath missing'})

    text = pytesseract.image_to_string(Image.open(img_path))
    return jsonify({'success': True, 'text': text})

@app.route('/ocr-camera', methods=['POST'])
def ocr_camera():
    """Ekstrak teks dari kamera"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    text = pytesseract.image_to_string(Image.open(filepath))
    return jsonify({'success': True, 'text': text, 'filepath': filepath})

def clean_old_files():
    """Menghapus file yang sudah lebih dari 1 jam di folder upload"""
    now = time.time()
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)
            if file_age > 3600:  # 1 jam = 3600 detik
                os.remove(file_path)
                print(f"Deleted old file: {filename}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2025, debug=True)
