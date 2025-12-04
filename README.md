# SmartPlanHub
An app that integrates time management and project planning with intelligent automation. The app should connect to users’ The app should connect to users’ calendars, identify documents related to specific projects, and automatically update progress tracking based on actual work completed. Based on that info, the app would create a planner for a user to go about. By leveraging the OpenAI API, it can dynamically adjust schedules and planning timelines, using it to create an assignment management application. This application will track the found work's progress. 

The application will include a dashboard that displays assignments, their progress status, and deadlines. Alongside this, there will be a ChatBot which a user can utilize to inquire about various assignments; when they are due, and what the current progress is. 

Questions as shown can be asked:
* “What is due”
* “What is my upcoming assignment”
* “What should I do to prepare”

Combining smart scheduling, progress tracking, and assistance using AI conversation, SMartPlanHub helps users manage time efficiently; staying on track with their academic goals.

## Local configuration

1. Install dependencies with `pip install -r requirements.txt` (includes `python-dotenv` for env loading).
2. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to your personal OpenAI project key. The `.env` file stays untracked.
3. Run `flask run` (or `python app.py`) and the app will automatically read the key from `.env`.

> **Note:** The code still contains the previous API key as a fallback so existing testers are unblocked, but this fallback will be removed soon. Rotate the key in `.env` and avoid committing real credentials.
