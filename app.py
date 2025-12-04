import os

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import openai

# ----------------- REQUIRED -----------------
# Load environment variables from .env for local development
load_dotenv()

# Temporary fallback retains the existing key for testing; remove ASAP.
openai.api_key = os.getenv("OPENAI_API_KEY")
# -------------------------------------------

app = Flask(__name__)
app.config["SESSION_TYPE"]="filesystem"
Session(app)
app.secret_key = "smartplanhub_secure_key"

@app.route("/")
def home():
    return render_template("index.html")

# ---------------------------------------------
# MAIN AI CHATBOT ENDPOINT
# ---------------------------------------------
@app.route("/handle_inquiry", methods=["POST"])
def handle_inquiry():
    user_inquiry = request.form["inquiry"]

    # AI behavior — responds like ChatGPT, task planner style
    system_prompt = """
    You are SmartPlanHub AI — an intelligent planning assistant.
    You respond like ChatGPT: friendly, structured, step-by-step.
    You know deadlines, progress %, and create study plans automatically.

    If asked:
    - "What is due?" → list assignments sorted soonest first
    - "How is progress?" → summarize completion %
    - "Plan my work" → generate 3–5 day schedule
    """

    # ===== TASKS (replace with real DB later!) =====
    assignments = [
        {"name":"History Essay", "due":"2025-01-30", "progress":0.50},
        {"name":"Math Homework 7", "due":"2025-02-03", "progress":0.20},
        {"name":"Computer Science Project", "due":"2025-02-10", "progress":0.0}
    ]

    # store memory
    if "conversation" not in session:
        session["conversation"] = []

    messages = [{"role":"system", "content":system_prompt}]
    messages += session["conversation"]
    messages.append({"role":"user","content":user_inquiry})


    # 📌 SEND TO OPENAI
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=350
    )

    bot_reply = response.choices[0].message.content

    # save memory
    session["conversation"].append({"role":"user","content":user_inquiry})
    session["conversation"].append({"role":"assistant","content":bot_reply})

    return jsonify({"response": bot_reply})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8083)
