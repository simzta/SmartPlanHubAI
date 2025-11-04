from flask import Flask, render_template, request, jsonify, session
from flask_session import Session  # Import Session
import openai
import os

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

openai.api_key = ''

app.secret_key = 'supersecretkey'

topic_options = [
    'code2college_courses', 'code2college_general_info'
    'ai_course'
]


@app.route('/')
def home():
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


if __name__ == '__main__':
  app.run(host="0.0.0.0", port=8080)
