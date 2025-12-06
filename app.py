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
app.config["CHATBOT_DEBUG_ERRORS"] = os.getenv("CHATBOT_DEBUG_ERRORS", "").lower() in (
    "1", "true", "yes")
Session(app)
app.logger.setLevel(logging.INFO)

openai.api_key = os.getenv("OPENAI_API_KEY", "")

app.secret_key = os.getenv("FLASK_SECRET_KEY", "smartplanhub_secure_key")

DEFAULT_ASSIGNMENTS = [
    {
        "name": "History Essay",
        "due": "2025-01-30",
        "progress": 0.50
    },
    {
        "name": "Math Homework 7",
        "due": "2025-02-03",
        "progress": 0.20
    },
    {
        "name": "Computer Science Project",
        "due": "2025-02-10",
        "progress": 0.0
    }
]


def _parse_due_date(date_str):
  try:
    return datetime.date.fromisoformat(date_str)
  except Exception:
    return None


def _days_until_due(date_str, today=None):
  today = today or datetime.date.today()
  due = _parse_due_date(date_str)
  if not due:
    return None
  return (due - today).days


def _percent_text(progress_float):
  try:
    pct = int(round(progress_float * 100))
  except Exception:
    pct = 0
  return max(0, min(100, pct))


def _format_due_summary(assignments, today=None):
  today = today or datetime.date.today()
  lines = ["Here's what I can see on your calendar:"]
  for item in sorted(assignments,
                     key=lambda a: _parse_due_date(a.get("due")) or datetime.date.max):
    days = _days_until_due(item.get("due"), today)
    pct = _percent_text(item.get("progress", 0))
    due_date = _parse_due_date(item.get("due"))
    due_label = due_date.strftime("%b %d") if due_date else item.get("due", "unknown date")
    if days is None:
      deadline_text = "deadline not set"
    elif days > 1:
      deadline_text = f"due in {days} days"
    elif days == 1:
      deadline_text = "due tomorrow"
    elif days == 0:
      deadline_text = "due today"
    else:
      deadline_text = f"overdue by {abs(days)} days"
    lines.append(f"- {item['name']}: {due_label} ({deadline_text}, {pct}% complete)")
  return "\n".join(lines)


def _format_progress_summary(assignments, today=None):
  today = today or datetime.date.today()
  lines = ["Progress snapshot:"]
  for item in sorted(assignments,
                     key=lambda a: _parse_due_date(a.get("due")) or datetime.date.max):
    pct = _percent_text(item.get("progress", 0))
    days = _days_until_due(item.get("due"), today)
    urgency = ""
    if days is not None:
      if days <= 2:
        urgency = " — urgent"
      elif days <= 5:
        urgency = " — coming up soon"
    lines.append(f"- {item['name']}: {pct}% done{urgency}")
  return "\n".join(lines)


def _match_assignment(lower_text, assignments):
  for item in assignments:
    name_lower = item["name"].lower()
    if name_lower in lower_text:
      return item
    tokens = [tok for tok in re.findall(r'\w+', name_lower) if len(tok) > 3]
    if any(tok in lower_text for tok in tokens):
      return item
  if "history" in lower_text:
    return next((a for a in assignments if "history" in a["name"].lower()), None)
  if "math" in lower_text:
    return next((a for a in assignments if "math" in a["name"].lower()), None)
  if "computer" in lower_text or "cs" in lower_text:
    return next((a for a in assignments if "computer" in a["name"].lower()), None)
  return None


def _extract_hint_numbers(text):
  lower = text.lower()
  days_hint = None
  pct_hint = None
  days_match = re.search(r'(\d+)\s*(?:day|days)', lower)
  if days_match:
    days_hint = max(1, int(days_match.group(1)))
  pct_match = re.search(r'(\d+)\s*%', lower)
  if pct_match:
    pct_hint = max(0, min(100, int(pct_match.group(1))))
  return days_hint, pct_hint


def _plan_for_assignment(assignment, user_inquiry, today=None):
  today = today or datetime.date.today()
  if not assignment:
    return None
  days_hint, pct_hint = _extract_hint_numbers(user_inquiry or "")
  pct = pct_hint if pct_hint is not None else _percent_text(assignment.get("progress", 0))
  due_date = _parse_due_date(assignment.get("due"))
  days_left = days_hint
  if days_left is None and due_date:
    days_left = max(1, (due_date - today).days)
  days_left = days_left or 5
  plan_window = max(1, min(days_left, 5))
  remaining = max(0, 100 - pct)
  chunk = max(1, remaining // plan_window) if remaining else 0
  stage_focus = [
      "tighten your outline & thesis",
      "write the next body section with evidence",
      "revise earlier paragraphs for flow",
      "cite sources + polish transitions",
      "proofread, format, and submit"
  ]
  plan_lines = []
  for idx in range(plan_window):
    target_pct = min(100, pct + chunk * (idx + 1)) if remaining else 100
    focus = stage_focus[min(idx, len(stage_focus) - 1)]
    day_label = (today + datetime.timedelta(days=idx)).strftime("%a %b %d")
    plan_lines.append(f"{day_label}: aim for ~{target_pct}% complete — {focus}.")
  header_due = due_date.strftime("%b %d") if due_date else assignment.get("due", "soon")
  summary = (
      f"Here's a quick plan for {assignment['name']} (due {header_due}, "
      f"{days_left} day(s) left, currently ~{pct}% complete):"
  )
  buffer_line = "Leave the final day for a clean read-through and submission checklist."
  return "\n".join([summary, ""] + plan_lines + ["", buffer_line])


def _extract_due_date_hint(text, today=None):
  today = today or datetime.date.today()
  if not text:
    return None
  lower = text.lower()

  iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", lower)
  if iso:
    year, month, day = map(int, iso.groups())
    try:
      return datetime.date(year, month, day).isoformat()
    except ValueError:
      pass

  month_lookup = {
      'jan': 1,
      'feb': 2,
      'mar': 3,
      'apr': 4,
      'may': 5,
      'jun': 6,
      'jul': 7,
      'aug': 8,
      'sep': 9,
      'sept': 9,
      'oct': 10,
      'nov': 11,
      'dec': 12,
  }
  month_match = re.search(r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:\s*,?\s*(\d{4}))?",
                          lower)
  if month_match:
    month_name, day_str, year_str = month_match.groups()
    month = month_lookup[month_name[:3]]
    day = int(day_str)
    year = int(year_str) if year_str else today.year
    try:
      candidate = datetime.date(year, month, day)
      if candidate < today and not year_str:
        candidate = datetime.date(year + 1, month, day)
      return candidate.isoformat()
    except ValueError:
      pass

  slash = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", lower)
  if slash:
    month, day, year_str = slash.groups()
    month = int(month)
    day = int(day)
    if 1 <= month <= 12 and 1 <= day <= 31:
      year = int(year_str) if year_str else today.year
      if year < 100:
        year += 2000
      try:
        candidate = datetime.date(year, month, day)
        if candidate < today and not year_str:
          candidate = datetime.date(year + 1, month, day)
        return candidate.isoformat()
      except ValueError:
        pass
  return None


def _extract_assignment_name(user_inquiry):
  if not user_inquiry:
    return "your assignment"
  cleaned = re.sub(r"(\d{4}-\d{2}-\d{2})", " ", user_inquiry)
  cleaned = re.sub(r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", " ", cleaned)
  cleaned = re.sub(r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)",
                   " ", cleaned,
                   flags=re.I)
  tokens = re.findall(r"[A-Za-z0-9']+", cleaned)
  stopwords = {
      "plan", "schedule", "work", "assignment", "task", "project", "essay",
      "homework", "please", "help", "focus", "on", "for", "the", "my",
      "a", "an", "to", "do", "finish", "complete", "due", "done",
  }
  filtered = [tok for tok in tokens if tok.lower() not in stopwords and not tok.isdigit()]
  if not filtered:
    filtered = tokens or ["assignment"]
  name = " ".join(filtered).strip()
  name = name[:60]
  return name.title() or "your assignment"


def _infer_assignment_from_text(user_inquiry, assignments, today=None):
  today = today or datetime.date.today()
  lower = (user_inquiry or "").lower()
  match = _match_assignment(lower, assignments)
  if match:
    return dict(match), False
  due_hint = _extract_due_date_hint(user_inquiry, today)
  inferred = {
      "name": _extract_assignment_name(user_inquiry),
      "due": due_hint or (today + datetime.timedelta(days=5)).isoformat(),
      "progress": 0.0
  }
  inferred["_is_custom"] = True
  inferred["_assumed_due"] = due_hint is None
  return inferred, True


def _offline_response(user_inquiry, assignments):
  lower = (user_inquiry or "").lower()
  today = datetime.date.today()
  assignments = assignments or []

  if not assignments and not lower:
    return "I'm offline right now, but I don't see any assignments tracked yet."

  needs_plan = any(
      keyword in lower
      for keyword in ["plan", "schedule", "break", "steps", "strategy", "how can i"]
  )
  if needs_plan:
    assignment, is_custom = _infer_assignment_from_text(user_inquiry, assignments, today)
    plan = _plan_for_assignment(assignment, user_inquiry, today)
    if not plan:
      return "I'm ready to plan—tell me the assignment name and due date for a tailored schedule."
    if is_custom and assignment.get("_assumed_due"):
      plan += ("\n\nI assumed the due date is about five days out—mention the actual date if it's different.")
    elif is_custom:
      plan += "\n\nIf you need tweaks, just share the updated due date or progress."
    else:
      plan += "\n\nNeed me to focus on another task? Just name it."
    return plan

  if "progress" in lower or "how am i doing" in lower:
    summary = _format_progress_summary(assignments, today)
    return summary + "\n\nNeed a plan for one of these? Just say 'plan' plus the assignment name."

  if "due" in lower or "deadline" in lower or "what do i have" in lower:
    due_summary = _format_due_summary(assignments, today)
    return due_summary + "\n\nI can also build a study schedule—just tell me which task."

  overview = [
      _format_due_summary(assignments, today),
      "",
      ("Need a plan for one of these? Ask me which task you'd like to focus on "
       "or say 'plan the Math homework'.")
  ]
  return "\n".join(overview)


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


def _fallback_ai_summary(event_payload, reason=None):
  """Return a lightweight, local summary so events can still be stored."""
  title = (event_payload.get("title") or "Event").strip()
  description = (event_payload.get("description") or "").strip()
  today = datetime.date.today()
  due_str = event_payload.get("date")
  days_until = None
  if due_str:
    try:
      days_until = (datetime.date.fromisoformat(due_str) - today).days
    except ValueError:
      days_until = None

  doc_titles = [
      d.get("title") for d in (event_payload.get("docs") or [])
      if d.get("title")
  ]
  notes_parts = [description or f"Prep work for {title}."]
  if days_until is not None:
    if days_until > 1:
      notes_parts.append(f"Due in {days_until} days.")
    elif days_until == 1:
      notes_parts.append("Due tomorrow.")
    elif days_until == 0:
      notes_parts.append("Due today.")
    else:
      notes_parts.append(f"Past due by {abs(days_until)} days.")
  if doc_titles:
    notes_parts.append(f"Docs referenced: {', '.join(doc_titles)}.")
  if reason:
    notes_parts.append(f"(AI helper offline: {reason})")
  notes = " ".join(notes_parts).strip()

  plan_horizon = 3
  if days_until is not None:
    plan_horizon = max(2, min(5, abs(days_until) or 1))
  steps = []
  labels = ["Outline priorities", "Make measurable progress", "Revise & polish", "QA / peer review", "Finalize & submit"]
  for idx in range(plan_horizon):
    focus = labels[min(idx, len(labels) - 1)]
    steps.append(f"Day {idx + 1}: {focus} for {title.lower()}.")

  if days_until is None:
    progress = 15 if description else 10
  elif days_until <= 0:
    progress = 70
  elif days_until <= 2:
    progress = 40
  else:
    progress = 20

  guidance = [
      "Break the work into daily blocks and log wins in the planner.",
      "Start with the toughest section while energy is high.",
      "Reserve buffer time for review before the deadline.",
  ]

  return {
      "notes": notes,
      "steps": steps,
      "progress_percent": max(0, min(100, progress)),
      "reasoning": "Local heuristic because AI analysis was unavailable.",
      "guidance": guidance,
      "doc_used": any(d.get("content") for d in (event_payload.get("docs") or []))
  }


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
        response_format={"type": "json_object"},
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
    msg = resp.choices[0].message
    parsed = getattr(msg, "parsed", None)
    if parsed is None:
      raw_content = msg.content
      if not raw_content or not str(raw_content).strip():
        raise RuntimeError("AI returned empty content while JSON was expected.")
      app.logger.error(f"[ai] Raw content from model (decode attempt): {raw_content!r}")
      parsed = json.loads(raw_content)
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
  return render_template('index.html')


@app.route('/get_conversation', methods=['GET'])
def get_conversation():
  if 'conversation' not in session:
    session['conversation'] = []
  return jsonify({'conversation': session['conversation']})


@app.route('/handle_inquiry', methods=['POST'])
def handle_inquiry():
  user_inquiry = request.form['inquiry']

  system_prompt = """
  You are SmartPlanHub AI — an intelligent planning assistant.
  You respond like ChatGPT: friendly, structured, step-by-step.
  You know deadlines, progress %, and create study plans automatically.

  If asked:
  - "What is due?" → list assignments sorted soonest first
  - "How is progress?" → summarize completion %
  - "Plan my work" → generate 3–5 day schedule
  """

  assignments = [dict(item) for item in DEFAULT_ASSIGNMENTS]

  if 'conversation' not in session:
    session['conversation'] = []
  conversation = session['conversation']
  error_detail = None
  gpt_response = None

  messages = [{"role": "system", "content": system_prompt}]
  messages += session['conversation']
  messages.append({"role": "user", "content": user_inquiry})

  if openai.api_key:
    try:
      response = openai.chat.completions.create(model="gpt-4o-mini",
                                                temperature=0.7,
                                                max_tokens=350,
                                                messages=messages)
      gpt_response = response.choices[0].message.content
      if not gpt_response or not str(gpt_response).strip():
        error_detail = "OpenAI returned an empty response."
        app.logger.warning("[chatbot] Empty response from OpenAI; falling back to local reply.")
        gpt_response = None
    except Exception as e:
      app.logger.error(f"[chatbot] OpenAI call failed: {e}")
      error_detail = str(e)
  else:
    app.logger.info("[chatbot] OPENAI_API_KEY not configured; running in offline mode.")
    error_detail = "OpenAI API key missing."

  if not gpt_response:
    gpt_response = _offline_response(user_inquiry, assignments)

  conversation.append({"role": "user", "content": user_inquiry})
  conversation.append({"role": "assistant", "content": gpt_response})

  payload = {'response': gpt_response}
  if error_detail and app.config.get("CHATBOT_DEBUG_ERRORS"):
    payload['error'] = error_detail
  return jsonify(payload)


@app.route('/clear_session', methods=['GET'])
def clear_session():
  # Clear the session
  session.clear()
  return jsonify({'status': 'session cleared'})


@app.route('/api/events', methods=['GET', 'POST', 'DELETE'])
def events_api():
  if request.method == 'GET':
    return jsonify({"events": _load_events()})

  if request.method == 'DELETE':
    payload = request.get_json(silent=True) or {}
    raw_id = payload.get("id")
    if not raw_id:
      return jsonify({'error': 'id is required to delete an event'}), 400
    event_id = str(raw_id)
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
    app.logger.warning(f"[events] AI enrichment unavailable for '{title}': {exc}")
    event["ai"] = _fallback_ai_summary(event, reason=str(exc))

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
    app.logger.warning(f"[events] AI enrichment unavailable for '{match.get('title')}': {exc}")
    match["ai"] = _fallback_ai_summary(match, reason=str(exc))
  _save_events(events)
  return jsonify(match)


if __name__ == '__main__':
  app.run(host="0.0.0.0", port=8080)
