import * as tf from '@tensorflow/tfjs';
import * as use from '@tensorflow-models/universal-sentence-encoder';
import * as pdfjsLib from 'pdfjs-dist';

pdfjsLib.GlobalWorkerOptions.workerSrc = //cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js;

// Initialize the Universal Sentence Encoder model
let model = null;
async function loadModel() {
    if (!model) {
        model = await use.load();
    }
    return model;
}

// Load model when the page loads
loadModel();

// User state management
let currentUser = null;

// Check if user is logged in
function checkAuth() {
    const user = localStorage.getItem('user');
    if (user) {
        currentUser = JSON.parse(user);
        showDashboard();
    }
}

// Show/hide alerts
function showAlert(elementId, message, isSuccess = false) {
    const alert = document.getElementById(elementId);
    alert.textContent = message;
    alert.style.display = 'block';
    alert.className = alert ${isSuccess ? 'success' : ''};
    setTimeout(() => {
        alert.style.display = 'none';
    }, 3000);
}

// Toggle between login and signup forms
window.toggleForms = function() {
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    loginForm.style.display = loginForm.style.display === 'none' ? 'block' : 'none';
    signupForm.style.display = signupForm.style.display === 'none' ? 'block' : 'none';
}

// Handle login
window.handleLogin = function(event) {
    event.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;

    // Simulate login (replace with actual backend call)
    const users = JSON.parse(localStorage.getItem('users') || '[]');
    const user = users.find(u => u.username === username && u.password === password);

    if (user) {
        currentUser = { username };
        localStorage.setItem('user', JSON.stringify(currentUser));
        showDashboard();
        showAlert('dashboard-alert', 'Login successful!', true);
    } else {
        showAlert('login-alert', 'Invalid credentials');
    }
}

// Handle signup
window.handleSignup = function(event) {
    event.preventDefault();
    const username = document.getElementById('signup-username').value;
    const password = document.getElementById('signup-password').value;

    // Simulate user registration (replace with actual backend call)
    const users = JSON.parse(localStorage.getItem('users') || '[]');
    if (users.some(u => u.username === username)) {
        showAlert('signup-alert', 'Username already exists');
        return;
    }

    users.push({ username, password });
    localStorage.setItem('users', JSON.stringify(users));
    showAlert('signup-alert', 'Account created successfully!', true);
    toggleForms();
}

// Handle logout
window.logout = function() {
    localStorage.removeItem('user');
    currentUser = null;
    document.getElementById('auth-container').style.display = 'flex';
    document.getElementById('dashboard').style.display = 'none';
}

// Show dashboard
function showDashboard() {
    document.getElementById('auth-container').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
}

// Process document
async function processDocument(file) {
    if (file.type === 'application/pdf') {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        let text = '';
        
        for (let i = 1; i <= pdf.numPages; i++) {
            const page = await pdf.getPage(i);
            const content = await page.getTextContent();
            text += content.items.map(item => item.str).join(' ') + ' ';
        }
        
        return text;
    } else {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.readAsText(file);
        });
    }
}

// Calculate similarity
async function calculateSimilarity(text1, text2) {
    const model = await loadModel();
    const embeddings = await model.embed([text1, text2]);
    const similarity = tf.matMul(embeddings.slice([0, 0], [1]), embeddings.slice([1, 0], [1]).transpose());
    const score = await similarity.data();
    return score[0];
}

// Handle document analysis
window.handleAnalysis = async function(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('file');
    const queryInput = document.getElementById('query');
    const responseSection = document.getElementById('response-section');
    const responseText = document.getElementById('response-text');
    
    try {
        const file = fileInput.files[0];
        const query = queryInput.value;
        
        // Show loading state
        responseSection.style.display = 'block';
        responseText.textContent = 'Analyzing document...';
        
        // Process document
        const documentText = await processDocument(file);
        const similarity = await calculateSimilarity(documentText, query);
        
        // Generate response
        let response;
        if (similarity > 0.5) {
            response = Similarity score: ${(similarity * 100).toFixed(2)}%\n\nResponse based on document content:\n${documentText.substring(0, 500)}...;
        } else {
            response = Similarity score: ${(similarity * 100).toFixed(2)}%\n\nLow similarity detected. Consider refining your query.;
        }
        
        responseText.textContent = response;
    } catch (error) {
        showAlert('dashboard-alert', 'Error analyzing document: ' + error.message);
        responseSection.style.display = 'none';
    }
}

// Initialize the application
checkAuth();
