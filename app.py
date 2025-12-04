import datetime
import json
import os
import uuid
from flask import (Flask, render_template, request, jsonify, session,
                   send_from_directory, redirect, url_for)
from flask_session import Session  # Import Session
from dotenv import load_dotenv
import openai

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DATA_DIR = os.path.join(BASE_DIR, "data")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")
os.makedirs(DATA_DIR, exist_ok=True)

load_dotenv()

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

openai.api_key = os.getenv("OPENAI_API_KEY", "")

app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

topic_options = [
    'code2college_courses', 'code2college_general_info', 'ai_course'
]


def _load_events():
  if not os.path.exists(EVENTS_FILE):
    return []
  try:
    with open(EVENTS_FILE, 'r') as f:
      return json.load(f)
  except Exception:
    return []


def _save_events(events):
  with open(EVENTS_FILE, 'w') as f:
    json.dump(events, f, indent=2)


def _ai_enrich_event(event_payload):
  """Call OpenAI to generate notes/steps/progress for an event."""
  docs = event_payload.get("docs", [])
  docs_blob = "\n".join([
      f"- {d.get('title') or d.get('url') or 'Untitled'}: {d.get('summary') or d.get('content') or 'No content provided.'}"
      for d in docs
  ]) or "No documents provided."

  system_prompt = (
      "You are SmartPlanHub AI. Given an event, attached documents, and description, "
      "return concise planning help and a completion estimate. Respond as JSON with keys: "
      "{\"notes\": string, \"steps\": [strings], \"progress_percent\": integer 0-100}."
  )

  user_payload = {
      "title": event_payload.get("title"),
      "description": event_payload.get("description"),
      "date": event_payload.get("date"),
      "docs": docs,
      "docs_summary": docs_blob
  }

  if not openai.api_key:
    return {
        "notes":
        "AI analysis unavailable (missing OPENAI_API_KEY).",
        "steps": ["Review the attached documents.", "Break work into actionable steps.",
                  "Estimate effort and update progress."],
        "progress_percent": 20
    }

  try:
    resp = openai.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        temperature=0.2,
        max_tokens=400,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": json.dumps(user_payload, indent=2)
            },
        ])
    content = resp.choices[0].message.content
    parsed = json.loads(content)
  except Exception as exc:
    app.logger.warning(f"AI enrichment failed, using fallback: {exc}")
    parsed = {}

  def clamp_percent(val, default=30):
    try:
      pct = int(val)
      return max(0, min(100, pct))
    except Exception:
      return default

  return {
      "notes": parsed.get("notes") or "No AI notes available.",
      "steps": parsed.get("steps") or ["Review documents and outline next steps."],
      "progress_percent": clamp_percent(parsed.get("progress_percent"))
  }


@app.route('/')
def spa_home():
  """Serve the styled SmartPlanHub front-end (Sima branch) by default."""
  if os.path.exists(os.path.join(WEB_DIR, "index.html")):
    return redirect(url_for('web_files', path='index.html'))
  return redirect(url_for('chatbot'))


@app.route('/web/')
def web_index():
  return redirect(url_for('web_files', path='index.html'))


@app.route('/web/<path:path>')
def web_files(path):
  return send_from_directory(WEB_DIR, path)


@app.route('/assets/<path:path>')
def asset_files(path):
  return send_from_directory(ASSETS_DIR, path)


@app.route('/chatbot')
def chatbot():
  return render_template('index.html', topic_options=topic_options)


@app.route('/get_conversation', methods=['GET'])
def get_conversation():
  if 'conversation' not in session:
    session['conversation'] = []
  return jsonify({'conversation': session['conversation']})


@app.route('/handle_inquiry', methods=['POST'])
def handle_inquiry():
  user_inquiry = request.form['inquiry']
  topic_selection = request.form[
      'topic']  # Retrieve the topic from the form data

  if 'conversation' not in session:
    session['conversation'] = []

  # Append the user's inquiry to the conversation
  session['conversation'].append({"role": "user", "content": user_inquiry})

  # Select the appropriate text file based on the user's dropdown selection
  text_file_path = f'topic_prompts/{topic_selection}.txt'
  if not os.path.exists(text_file_path):
    return jsonify({
        'response':
        'The selected topic is not available. Please choose another one.'
    })

  # Read the content of the text file
  with open(text_file_path, 'r') as file:
    topic_info = file.read()

  # The messages structure for the API call
  messages = [{
      "role": "system",
      "content": topic_info
  }] + session['conversation']

  try:
    # Make API call to OpenAI using the messages
    response = openai.chat.completions.create(model="gpt-3.5-turbo-1106",
                                              messages=messages)
    # Extract the content from the response
    gpt_response = response.choices[0].message.content

    # Append the GPT response to the conversation history
    session['conversation'].append({
        "role": "assistant",
        "content": gpt_response
    })

    # Return the GPT response
    return jsonify({'response': gpt_response})
  except Exception as e:
    # Log the error and return a message
    app.logger.error(f"An error occurred: {e}")
    return jsonify({'error': str(e)}), 500


@app.route('/clear_session', methods=['GET'])
def clear_session():
  # Clear the session
  session.clear()
  return jsonify({'status': 'session cleared'})


@app.route('/api/events', methods=['GET', 'POST'])
def events_api():
  if request.method == 'GET':
    return jsonify({"events": _load_events()})

  payload = request.get_json(silent=True) or {}
  title = payload.get("title")
  date_str = payload.get("date")
  if not title or not date_str:
    return jsonify({'error': 'title and date are required'}), 400

  docs = payload.get("docs") or []
  event = {
      "id": str(uuid.uuid4()),
      "title": title,
      "description": payload.get("description", ""),
      "date": date_str,
      "start_time": payload.get("start_time"),
      "end_time": payload.get("end_time"),
      "docs": docs
  }

  event["ai"] = _ai_enrich_event(event)

  events = _load_events()
  events.append(event)
  _save_events(events)

  return jsonify(event), 201


if __name__ == '__main__':
  app.run(host="0.0.0.0", port=8080)
