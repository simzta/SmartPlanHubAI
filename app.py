import datetime
import json
import logging
import os
import re
import uuid
import requests
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
app.logger.setLevel(logging.INFO)

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


def _fetch_doc_text(url: str) -> str:
  """Best-effort fetch of document text for public links."""
  def google_doc_export(u: str) -> str:
    match = re.search(r'/document/d/([A-Za-z0-9_-]+)', u)
    if not match:
      return ""
    doc_id = match.group(1)
    return f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

  def fetch(target: str) -> str:
    app.logger.info(f"[docs] Fetching text from {target}")
    resp = requests.get(target,
                        timeout=12,
                        headers={"User-Agent": "SmartPlanHub/1.0"})
    app.logger.info(f"[docs] Response {resp.status_code} {resp.reason} for {target} (ct={resp.headers.get('content-type')})")
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    text = resp.text
    if "text/html" in content_type:
      text = re.sub(r'<script.*?>.*?</script>', ' ', text, flags=re.S | re.I)
      text = re.sub(r'<style.*?>.*?</style>', ' ', text, flags=re.S | re.I)
      text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    lower = text.lower()
    permission_markers = [
        "you need access", "request access", "sign in", "sign-in",
        "permission denied", "you don’t have access", "you don't have access",
        "document is not available"
    ]
    if len(text) < 200 or any(p in lower for p in permission_markers):
      app.logger.warning(
          f"[docs] Content from {target} looks like a permission wall or is too short (len={len(text)}); treating as empty"
      )
      return ""
    app.logger.info(
        f"[docs] Retrieved {len(text)} characters from {target} (content-type={content_type})")
    return text[:6000]

  export_url = google_doc_export(url)
  tried = []
  for target in [export_url, url]:
    if not target or target in tried:
      continue
    tried.append(target)
    try:
      text = fetch(target)
      if text:
        return text
    except Exception as exc:
      app.logger.warning(f"[docs] Fetch failed for {target}: {exc}")
      continue
  return ""


def _hydrate_docs(docs):
  hydrated = []
  for doc in docs or []:
    d = dict(doc)
    if d.get("url") and not d.get("content"):
      fetched = _fetch_doc_text(d["url"])
      if fetched:
        d["content"] = fetched
        app.logger.info(f"[docs] Hydrated doc '{d.get('title') or d.get('url')}' len={len(fetched)}")
      else:
        app.logger.warning(f"[docs] No content fetched for '{d.get('title') or d.get('url')}'")
    hydrated.append(d)
  return hydrated


def _ai_enrich_event(event_payload):
  """Call OpenAI to generate notes/steps/progress for an event."""
  docs = event_payload.get("docs", [])
  docs_blob = "\n".join([
      f"- {d.get('title') or d.get('url') or 'Untitled'}: {d.get('summary') or d.get('content') or 'No content provided.'}"
      for d in docs
  ]) or "No documents provided."

  due_str = event_payload.get("date")
  due_in_days = None
  try:
    if due_str:
      due_dt = datetime.date.fromisoformat(due_str)
      due_in_days = (due_dt - datetime.date.today()).days
  except Exception:
    due_in_days = None

  doc_texts = [d.get("content") for d in docs if d.get("content")]
  doc_text_used = bool(doc_texts)
  docs_text_blob = "\n\n---\n\n".join(doc_texts)[:8000] if doc_texts else ""
  app.logger.info(
      f"[ai] Enriching event '{event_payload.get('title')}' with {len(docs)} doc(s); "
      f"doc_text_present={doc_text_used} due={due_str}")

  system_prompt = (
      "You are SmartPlanHub AI. Given an event, attached documents (including draft text), "
      "and description, return concise planning help and a completion estimate grounded in the actual document text. "
      "Treat progress_percent as how complete the work is right now based on the draft: "
      "rough outlines ~10-25%, partial draft ~30-60%, mostly complete ~70-90%, final polish ~95+. "
      "Also include: reasoning (why you picked that %), and guidance (concise tips aware of due date vs today). "
      "If doc_text is empty, state that you cannot analyze because the document content was unavailable; do not infer from titles alone. "
      "Respond as JSON with keys: {\"notes\": string, \"steps\": [strings], \"progress_percent\": integer 0-100, "
      "\"reasoning\": string, \"guidance\": [strings]}."
  )

  user_payload = {
      "title": event_payload.get("title"),
      "description": event_payload.get("description"),
      "date": event_payload.get("date"),
      "today": datetime.date.today().isoformat(),
      "due_in_days": due_in_days,
      "docs": docs,
      "docs_summary": docs_blob,
      "doc_text": docs_text_blob
  }

  if not openai.api_key:
    raise RuntimeError("AI analysis unavailable (missing OPENAI_API_KEY).")

  if not docs_text_blob:
    raise RuntimeError("Document text could not be fetched; ensure the link is public and retry.")

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
    app.logger.error(f"[ai] AI enrichment failed: {exc}")
    raise

  def clamp_percent(val, default=30):
    try:
      pct = int(val)
      return max(0, min(100, pct))
    except Exception:
      return default

  return {
      "notes": parsed.get("notes") or "No AI notes available.",
      "steps": parsed.get("steps") or ["Review documents and outline next steps."],
      "progress_percent": clamp_percent(parsed.get("progress_percent")),
      "reasoning": parsed.get("reasoning") or "Progress estimated from available documents.",
      "guidance": parsed.get("guidance") or [
          "Work backward from the due date to allocate time.",
          "Draft, then revise with citations.",
          "Re-check sources for gaps before finalizing."
      ],
      "doc_used": doc_text_used
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

  if request.method == 'DELETE':
    payload = request.get_json(silent=True) or {}
    event_id = str(payload.get("id"))
    if not event_id:
      return jsonify({'error': 'id is required to delete an event'}), 400
    events = _load_events()
    before = len(events)
    events = [e for e in events if str(e.get("id")) != event_id]
    if len(events) == before:
      return jsonify({'error': 'event not found'}), 404
    _save_events(events)
    app.logger.info(f"[events] Deleted event {event_id}")
    return jsonify({'status': 'deleted'})

  payload = request.get_json(silent=True) or {}
  title = payload.get("title")
  date_str = payload.get("date")
  if not title or not date_str:
    return jsonify({'error': 'title and date are required'}), 400

  docs = payload.get("docs") or []
  docs = _hydrate_docs(docs)
  event = {
      "id": str(uuid.uuid4()),
      "title": title,
      "description": payload.get("description", ""),
      "date": date_str,
      "start_time": payload.get("start_time"),
      "end_time": payload.get("end_time"),
      "docs": docs
  }

  app.logger.info(f"[events] Creating event '{title}' on {date_str} with {len(docs)} doc(s)")
  try:
    event["ai"] = _ai_enrich_event(event)
  except Exception as exc:
    app.logger.error(f"[events] Failed to analyze event '{title}': {exc}")
    return jsonify({"error": str(exc)}), 500

  events = _load_events()
  events.append(event)
  _save_events(events)

  return jsonify(event), 201


@app.route('/api/events/<event_id>/analyze', methods=['POST'])
def reanalyze_event(event_id):
  events = _load_events()
  id_str = str(event_id)
  match = next((e for e in events if str(e.get("id")) == id_str), None)
  if not match:
    return jsonify({
        'error': 'event not found',
        'known_ids': [e.get("id") for e in events]
    }), 404

  app.logger.info(f"[events] Re-analyzing event '{match.get('title')}' ({id_str})")
  match["docs"] = _hydrate_docs(match.get("docs") or [])
  try:
    match["ai"] = _ai_enrich_event(match)
  except Exception as exc:
    app.logger.error(f"[events] Failed to analyze event '{match.get('title')}': {exc}")
    return jsonify({"error": str(exc)}), 500
  _save_events(events)
  return jsonify(match)


if __name__ == '__main__':
  app.run(host="0.0.0.0", port=8080)
