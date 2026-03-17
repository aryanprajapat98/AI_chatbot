from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from google import genai
import os
import pymongo
import time
from bson.objectid import ObjectId

app = Flask(__name__)

# --- 1. CONFIGURATION ---
app.secret_key = "aryan_super_secret_key"
GEMINI_API_KEY = "AIzaSyCUlzuvt7ClBYbLPm7oOk759tAqLpT2H7A" 
client_ai = genai.Client(api_key=GEMINI_API_KEY)

# MongoDB Connection
uri = "mongodb+srv://AI_CHATBOT:ARYAN2007@cluster0.b5cwh92.mongodb.net/?appName=Cluster0"
mongo_client = pymongo.MongoClient(uri)
db = mongo_client['chatbot_db']
collection = db['chat_history']

# Admin Credentials Setup
admin_coll = db['admin_creds']
if admin_coll.count_documents({}) == 0:
    admin_coll.insert_one({"username": "admin", "password": "12345"})

UPLOAD_FOLDER = r"c:\Users\dell\Music\hh"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

business_knowledge = ""

def load_data():
    global business_knowledge
    path = os.path.join(app.config['UPLOAD_FOLDER'], "Learn.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            business_knowledge = f.read()
    else:
        business_knowledge = "Default Business Info: Please upload Learn.txt"

load_data()

# --- 2. ROUTES ---

@app.route("/")
def index():
    return redirect(url_for('admin_dashboard'))

@app.route("/admin")
def admin_dashboard():
    if not session.get('logged_in'):
        return render_template("admin.html")
    
    try:
        numbers = collection.distinct("phone")
        selected_phone = request.args.get('phone')
        
        if selected_phone:
            chats = list(collection.find({"phone": selected_phone}).sort("_id", -1))
        else:
            chats = list(collection.find().sort("_id", -1))
            
        return render_template("admin.html", chats=chats, numbers=numbers, selected=selected_phone)
    except Exception as e:
        return f"Database Error: {e}"

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    
    # Database se credentials check karna
    admin = admin_coll.find_one({"username": username, "password": password})
    
    if admin:
        session['logged_in'] = True
        return redirect(url_for('admin_dashboard'))
    return "Invalid Credentials! <a href='/admin'>Try Again</a>"

@app.route("/update_password", methods=["POST"])
def update_password():
    if not session.get('logged_in'):
        return redirect(url_for('admin_dashboard'))
    
    new_pass = request.form.get("new_password")
    if new_pass:
        admin_coll.update_one({}, {"$set": {"password": new_pass}})
        return "Password updated! <a href='/logout'>Login again with new password</a>"
    return "Error updating password."

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('admin_dashboard'))

@app.route("/upload_file", methods=["POST"])
def upload_file():
    if not session.get('logged_in'):
        return redirect(url_for('admin_dashboard'))
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            path = os.path.join(app.config['UPLOAD_FOLDER'], "Learn.txt")
            file.save(path)
            load_data()
    return redirect(url_for('admin_dashboard'))

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_input = data.get("message", "")
    sender = data.get("sender", "Unknown")

    try:
        past_chats = list(collection.find({"phone": sender}).sort("_id", -1).limit(5))
        chat_history = ""
        for chat_node in reversed(past_chats):
            chat_history += f"User: {chat_node['user_message']}\nAI: {chat_node['bot_reply']}\n"

        prompt = f"""
        System: You are a friendly AI. Use the Chat History to remember details like names.
        Business Context: {business_knowledge}
        Chat History:
        {chat_history}
        Current User Question: {user_input}
        """
        
        response = client_ai.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt
        )
        bot_reply = response.text.strip()

        collection.insert_one({
            "phone": sender,
            "user_message": user_input,
            "bot_reply": bot_reply,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"reply": bot_reply})
        
    except Exception as e:
        if "429" in str(e):
            return jsonify({"reply": "Bhai, 1 minute ruko! API limit cross ho gayi hai. ⏳"})
        return jsonify({"reply": "System busy hai, please refresh karein."})

@app.route("/delete/<chat_id>")
def delete_chat(chat_id):
    if session.get('logged_in'):
        collection.delete_one({"_id": ObjectId(chat_id)})
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)