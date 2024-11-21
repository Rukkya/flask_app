from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from transformers import BloomTokenizerFast, BloomForCausalLM
import torch
from sentence_transformers import SentenceTransformer, util
import PyPDF2
import glob

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123@rokia:5432/postgres'
db = SQLAlchemy(app)

# Load models
tokenizer = BloomTokenizerFast.from_pretrained("bigscience/bloom-560m")
model = BloomForCausalLM.from_pretrained("bigscience/bloom-560m")
sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

with app.app_context():
    db.create_all()

def get_file_content(file_path):
    if file_path.lower().endswith('.pdf'):
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    elif file_path.lower().endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    return None

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['username'] = username
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            return render_template('signup.html', error='Username already exists')
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/browse_files')
def browse_files():
    current_path = request.args.get('path', '/')
    
    try:
        # Get directories
        directories = [d for d in os.listdir(current_path) if os.path.isdir(os.path.join(current_path, d))]
        
        # Get PDF and TXT files using glob
        pdf_files = glob.glob(os.path.join(current_path, '*.pdf'))
        txt_files = glob.glob(os.path.join(current_path, '*.txt'))
        
        # Combine and get just the filenames
        files = [os.path.basename(f) for f in pdf_files + txt_files]
        
        return jsonify({
            'current_path': current_path,
            'directories': sorted(directories),
            'files': sorted(files)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/process_query', methods=['POST'])
def process_query():
    file_path = request.form.get('file_path')
    query = request.form.get('query')
    
    if not file_path or not query:
        return jsonify({'error': 'Missing file path or query'}), 400
    
    try:
        # Read file content
        content = get_file_content(file_path)
        if not content:
            return jsonify({'error': 'Unable to read file content'}), 400
        
        # Generate embeddings
        content_embedding = sentence_model.encode(content)
        query_embedding = sentence_model.encode(query)
        
        # Calculate similarity
        similarity = util.pytorch_cos_sim(content_embedding, query_embedding).item()
        
        if similarity < 0.5:
            # Generate response using BLOOM
            inputs = tokenizer(query, return_tensors="pt")
            outputs = model.generate(**inputs, max_length=100, num_return_sequences=1)
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        else:
            # Use content from document
            response = f"Found relevant content (similarity: {similarity:.2f}): {content[:500]}..."
        
        return jsonify({'response': response, 'similarity': similarity})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
