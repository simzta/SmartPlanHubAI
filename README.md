# SmartPlanHub
An app that integrates time management and project planning with intelligent automation. The app should connect to users’ The app should connect to users’ calendars, identify documents related to specific projects, and automatically update progress tracking based on actual work completed. Based on that info, the app would create a planner for a user to go about. By leveraging the OpenAI API, it can dynamically adjust schedules and planning timelines, using it to create an assignment management application. This application will track the found work's progress. 

The application will include a dashboard that displays assignments, their progress status, and deadlines. Alongside this, there will be a ChatBot which a user can utilize to inquire about various assignments; when they are due, and what the current progress is. 

Questions as shown can be asked:
* “What is due”
* “What is my upcoming assignment”
* “What should I do to prepare”

Combining smart scheduling, progress tracking, and assistance using AI conversation, SMartPlanHub helps users manage time efficiently; staying on track with their academic goals.

## Combined branch overview
- Sima-styled front-end lives in `web/` and is served at `/` (start at `http://localhost:8080/`).
- Harshita chatbot remains available at `/chatbot`, using the topic prompt files in `topic_prompts/`.
- In-app calendar now supports creating events with attached document links and AI enrichment via `/api/events`.
  - If docs are public links, the backend will fetch their text on create or when you click “Update analysis” on an event card.

## Getting started
1. Install dependencies: `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` (and optionally `FLASK_SECRET_KEY`).
3. Run the app: `python app.py` (defaults to port 8080). Visit `/` for the Sima UI or `/chatbot` for the chatbot UI.

## In-app calendar API
- Create events: `POST /api/events` with JSON
  ```json
  {
    "title": "History essay draft",
    "date": "2025-01-20",
    "description": "First draft review",
    "docs": [
      {
        "title": "Essay outline",
        "url": "https://docs.google.com/...",
        "summary": "Outline + key arguments"
      }
    ]
  }
  ```
- List events: `GET /api/events` → `{ "events": [...] }`
- The backend calls OpenAI (if `OPENAI_API_KEY` is set) to add notes, next steps, and a `progress_percent` estimate per event. If the key is missing, a lightweight fallback is returned.
