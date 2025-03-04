from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import numpy as np
import joblib
import sqlite3
import os
import json
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
from sklearn.ensemble import VotingClassifier
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'autism_detection_secret_key'  # Secret key for session management

# Create database if it doesn't exist
def init_db():
    conn = sqlite3.connect('autism_app.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        email TEXT,
        age INTEGER,
        gender TEXT
    )
    ''')
    
    # Create assessments table to store patient test results
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        result TEXT,
        probability REAL,
        a1 INTEGER, a2 INTEGER, a3 INTEGER, a4 INTEGER, a5 INTEGER,
        a6 INTEGER, a7 INTEGER, a8 INTEGER, a9 INTEGER, a10 INTEGER,
        age INTEGER, gender TEXT, jaundice INTEGER, autism_history INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Load trained models
best_xgb = joblib.load("models/best_xgb.pkl")
best_lgbm = joblib.load("models/best_lgbm.pkl")
best_catboost = joblib.load("models/best_catboost.pkl")

print("✅ Models loaded successfully!")

# Create VotingClassifier without requiring `.fit()`
ensemble = VotingClassifier(
    estimators=[
        ('xgb', best_xgb),
        ('lgbm', best_lgbm),
        ('catboost', best_catboost)
    ],
    voting='soft'
)
ensemble.estimators_ = [best_xgb, best_lgbm, best_catboost]  # Assign pre-trained models manually

# Load chatbot responses
def load_chatbot_responses():
    with open('static/chatbot_data.json', 'r') as f:
        return json.load(f)

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return render_template('home.html', logged_in=True, username=session.get('username'))
    return render_template('home.html', logged_in=False)

@app.route('/about')
def about():
    if 'user_id' in session:
        return render_template('about.html', logged_in=True, username=session.get('username'))
    return render_template('about.html', logged_in=False)

@app.route('/assessment')
def assessment():
    if 'user_id' in session:
        return render_template('assessment.html', logged_in=True, username=session.get('username'))
    return render_template('assessment.html', logged_in=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('autism_app.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('home'))
        else:
            error = 'Invalid username or password'
    
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        email = request.form['email']
        age = request.form['age']
        gender = request.form['gender']
        
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect('autism_app.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO users (username, password, name, email, age, gender) VALUES (?, ?, ?, ?, ?, ?)",
                (username, hashed_password, name, email, age, gender)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = 'Username already exists'
        finally:
            conn.close()
    
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = []
        form_data = {}  # Store original form data for database
        gender_map = {'m': 0, 'f': 1, 'other': 2}  # Gender mapping

        for key, value in request.form.items():
            form_data[key] = value
            if key == 'gender':  
                data.append(gender_map.get(value.lower(), 2))  # Convert gender to numeric values
            elif value.lower() == 'yes':  
                data.append(1)  # Convert Yes → 1
            elif value.lower() == 'no':  
                data.append(0)  # Convert No → 0
            else:
                try:
                    data.append(float(value))  # Convert numerical values
                except ValueError:
                    return render_template('assessment.html', 
                                           prediction_text=f"Invalid input: {key} -> {value}",
                                           logged_in='user_id' in session,
                                           username=session.get('username'))

        # **DEBUGGING: PRINT INPUT DATA BEFORE PREDICTION**
        print("\n🔍 Processed Input Data:", data)

        # Ensure correct input length
        if len(data) != 14:
            return render_template('assessment.html', 
                                  prediction_text=f"Error: Expected 14 features, got {len(data)}",
                                  logged_in='user_id' in session,
                                  username=session.get('username'))

        # Convert to NumPy array
        features = np.array([data])

        # **DEBUGGING: PRINT PROBABILITIES BEFORE DECISION**
        probabilities = ensemble.predict_proba(features)[0]
        print(f"Model Probability Output: {probabilities}")

        # Make prediction
        probability = probabilities[1] * 100  # Probability of having autism
        prediction = "Yes, diagnosed with autism" if probability > 50 else "No, not diagnosed with autism"

        print(f"Final Prediction: {prediction} (Confidence: {probability:.2f}%)")  # Debugging
        
        # Save assessment if user is logged in
        if 'user_id' in session:
            conn = sqlite3.connect('autism_app.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO assessments 
                (user_id, result, probability, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, age, gender, jaundice, autism_history)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['user_id'], 
                prediction, 
                probability,
                form_data.get('A1_Score', 0),
                form_data.get('A2_Score', 0),
                form_data.get('A3_Score', 0),
                form_data.get('A4_Score', 0),
                form_data.get('A5_Score', 0),
                form_data.get('A6_Score', 0),
                form_data.get('A7_Score', 0),
                form_data.get('A8_Score', 0),
                form_data.get('A9_Score', 0),
                form_data.get('A10_Score', 0),
                form_data.get('age', 0),
                form_data.get('gender', ''),
                form_data.get('jaundice', 0),
                form_data.get('autism', 0)
            ))
            conn.commit()
            conn.close()

        return render_template('assessment.html', 
                              prediction_text=f'{prediction} (Confidence: {probability:.2f}%)',
                              logged_in='user_id' in session,
                              username=session.get('username'))

    except Exception as e:
        print("Error during prediction:", str(e))  # Debugging
        return render_template('assessment.html', 
                              prediction_text=f'Error: {str(e)}',
                              logged_in='user_id' in session,
                              username=session.get('username'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('autism_app.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM assessments WHERE user_id = ? ORDER BY assessment_date DESC
    ''', (session['user_id'],))
    assessments = cursor.fetchall()
    conn.close()
    
    return render_template('history.html', 
                          assessments=assessments,
                          logged_in=True,
                          username=session.get('username'))

@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        message = request.json.get('message', '').lower()
        responses = load_chatbot_responses()
        
        # Find best matching response
        response = "I'm sorry, I don't understand that question about autism. Please try asking something else."
        
        # Check for exact keywords matches first
        for item in responses:
            for keyword in item['keywords']:
                if keyword.lower() in message:
                    response = item['response']
                    break
        
        return jsonify({"response": response})
    except Exception as e:
        print("Chatbot error:", str(e))
        return jsonify({"response": "Sorry, I encountered an error. Please try again."})

if __name__ == '__main__':
    # Create the chatbot data file if it doesn't exist
    if not os.path.exists('static'):
        os.makedirs('static')
    
    if not os.path.exists('static/chatbot_data.json'):
        chatbot_data = [
            {
                "keywords": ["what is autism", "autism definition", "define autism"],
                "response": "Autism, or Autism Spectrum Disorder (ASD), is a neurodevelopmental condition that affects how people perceive and interact with the world. It typically involves challenges with social communication, repetitive behaviors, and sometimes restricted interests."
            },
            {
                "keywords": ["symptoms", "signs", "indicators"],
                "response": "Common signs of autism include: difficulty with social interactions, delayed language development, repetitive behaviors, intense interests in specific topics, sensory sensitivities, and difficulty understanding nonverbal communication."
            },
            {
                "keywords": ["diagnosis", "diagnosed", "test"],
                "response": "Autism diagnosis typically involves comprehensive evaluation by healthcare professionals, including developmental screening, behavioral assessments, and medical tests. Early diagnosis is important for accessing appropriate support."
            },
            {
                "keywords": ["treatment", "therapy", "help"],
                "response": "While there's no 'cure' for autism, many supportive therapies can help, including behavioral therapy, speech therapy, occupational therapy, and educational interventions. Treatment plans are typically individualized based on specific needs."
            },
            {
                "keywords": ["cause", "causes", "why autism"],
                "response": "The exact causes of autism aren't fully understood, but research suggests it's likely due to a combination of genetic and environmental factors that affect brain development."
            },
            {
                "keywords": ["hello", "hi", "hey", "greetings"],
                "response": "Hello! I'm here to answer your questions about autism. How can I help you today?"
            }
        ]
        
        with open('static/chatbot_data.json', 'w') as f:
            json.dump(chatbot_data, f, indent=4)
    
    app.run(debug=True)