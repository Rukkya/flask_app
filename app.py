import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM
from sklearn.metrics.pairwise import cosine_similarity
import PyPDF2
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://rokia:123@localhost/flask_app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# File upload configuration
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize models
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
tokenizer = AutoTokenizer.from_pretrained("bigscience/bloom-560m")
model = AutoModelForCausalLM.from_pretrained("bigscience/bloom-560m")

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

# Document model to store file information
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('documents', lazy=True))

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_document(file_path):
    """Process uploaded PDF file"""
    if file_path.endswith('.pdf'):
        pdf_reader = PyPDF2.PdfReader(file_path)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

def analyze_document(document_text, query):
    """Analyze document and return response based on cosine similarity"""
    doc_embedding = embedding_model.encode([document_text])
    query_embedding = embedding_model.encode([query])
    
    similarity = cosine_similarity(doc_embedding, query_embedding.reshape(1, -1))[0][0]
    
    # Function to extract key information from the document
    def extract_key_information(text):
        # Regular expressions for key information extraction
        location_pattern = re.compile(r'from (\w+)', re.IGNORECASE)  # e.g., "from Japan"
        age_pattern = re.compile(r'(\d+)\s*years\s*old', re.IGNORECASE)  # e.g., "19 years old"
        profession_pattern = re.compile(r'I\s*stud(?:y|ying)\s*(\w+)', re.IGNORECASE)  # e.g., "studying machine learning"
        
        # Extracting information based on patterns
        location_match = location_pattern.search(text)
        age_match = age_pattern.search(text)
        profession_match = profession_pattern.search(text)
        
        info = {}
        if location_match:
            info['location'] = location_match.group(1)
        if age_match:
            info['age'] = age_match.group(1)
        if profession_match:
            info['profession'] = profession_match.group(1)
        
        return info
    
    # If similarity is above threshold, give a response based on document content
    if similarity > 0.5:
        response = "Response based on document content."
    else:
        # If similarity is low, try to extract relevant information from the document
        extracted_info = extract_key_information(document_text)
        
        # If location is found in the document, return it
        if 'location' in extracted_info:
            response = f"Rokia is from {extracted_info['location']}."
        else:
            response = "No specific information found about location."
    
    # Return formatted output
    return f"similarity score: {similarity:.2f}\nresponse: {response}"

# Routes
@app.route('/', methods=['GET'])
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        hashed_password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        user = User(username=request.form['username'], password=hashed_password)
        db.session.add(user)
        try:
            db.session.commit()
            flash('Account created successfully')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Username already exists')
    return render_template('signup.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    response = None
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded')
            return redirect(request.url)
        
        file = request.files['file']
        query = request.form['query']
        
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Save the uploaded PDF file to the server
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            try:
                document_text = process_document(file_path)
                response = analyze_document(document_text, query)
                
                # Save document metadata to the database
                new_document = Document(filename=filename, filepath=file_path, user_id=session['user_id'])
                db.session.add(new_document)
                db.session.commit()

            except Exception as e:
                flash(f'Error processing file: {str(e)}')
    
    return render_template('dashboard.html', response=response)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
