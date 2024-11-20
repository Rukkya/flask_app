import PyPDF2
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM
from sklearn.metrics.pairwise import cosine_similarity

# Initialize Flask app
app = Flask(__name__)

# Secret key for session management (replace this with your actual secret key)
app.secret_key = 'd3b07384d113edec49eaa6238ad5f28d'  # Replace with a secure random key

# Configure SQLAlchemy to use PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://rokia:123@localhost/flask_app'  # Update this
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize Bcrypt for password hashing
bcrypt = Bcrypt(app)

# Initialize Sentence Transformers and Hugging Face model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
tokenizer = AutoTokenizer.from_pretrained("bigscience/bloom-560m")
model = AutoModelForCausalLM.from_pretrained("bigscience/bloom-560m")

# Create User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

# Create Document model
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(200), nullable=False)

# Create tables (run this once)
@app.before_first_request
def create_tables():
    db.create_all()

# Function to process the document (PDF or text)
def process_document(uploaded_file):
    document_text = ""
    
    if uploaded_file.type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        for page in pdf_reader.pages:
            document_text += page.extract_text() or ""
    else:
        document_text = uploaded_file.read().decode("utf-8")
    
    return document_text

# Function to calculate embeddings and generate response
def analyze_document_with_query(document_text, user_query):
    # Generate embeddings for document text
    document_embeddings = embedding_model.encode([document_text])
    user_query_embedding = embedding_model.encode([user_query])

    similarity_score = cosine_similarity(document_embeddings, user_query_embedding)

    if similarity_score[0][0] > 0.5:
        # Use embeddings-based response generation
        return f"Document relevance score: {similarity_score[0][0]}. Answer based on document embeddings."
    else:
        # Use Bloom model for response generation
        combined_input = f"Document: {document_text}\n\nQuery: {user_query}"
        input_ids = tokenizer.encode(combined_input, return_tensors="pt")
        output = model.generate(input_ids, max_length=300, num_beams=4, early_stopping=True)
        generated_response = tokenizer.decode(output[0], skip_special_tokens=True)
        return generated_response

# Sign-up route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the user already exists
        user = User.query.filter_by(username=username).first()
        if user:
            flash("Username already exists!", "danger")
            return redirect(url_for('signup'))

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Create a new user and add to the database
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Sign-up successful! You can now log in.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if user exists
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            # Successful login
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

# Dashboard route
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        uploaded_file = request.files['file']
        user_query = request.form['query']

        if uploaded_file:
            # Process the uploaded document (PDF or Text)
            document_text = process_document(uploaded_file)

            # Save document to the database
            new_document = Document(user_id=session['user_id'], content=document_text, filename=uploaded_file.filename)
            db.session.add(new_document)
            db.session.commit()

            # Analyze the document with the query
            response = analyze_document_with_query(document_text, user_query)
            return render_template('dashboard.html', response=response)

    return render_template('dashboard.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
