import os
import uuid
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv

# Load environment variables (API Keys)
load_dotenv()

app = Flask(__name__)
CORS(app) # For production, you can later restrict this to your Vercel URL

# Securely retrieve the key
AI_API_KEY = os.getenv("AI_API_KEY")

# Mapping project languages to Piston API identifiers
PISTON_CONFIG = {
    "python": {"language": "python", "version": "3.10.0"},
    "java": {"language": "java", "version": "15.0.2"},
    "c": {"language": "c", "version": "10.2.0"},
    "cpp": {"language": "cpp", "version": "10.2.0"}
}

# --- AI Utility Functions ---

def get_ai_explanation(code, language, error_message, level):
    if not AI_API_KEY:
        return "AI Service Error: API Key missing."
    try:
        client = genai.Client(api_key=AI_API_KEY) 
        
        # System Prompts based on User Level
        prompts = {
            'easy': "You are a friendly tutor for a beginner. Use simple language and analogies. Provide the fixed code.",
            'medium': "You are an intermediate instructor. Use technical terms like 'scope' or 'initialization'. Provide hints, NOT the full code.",
            'hard': "You are a critical peer-reviewer for a B.Tech student. Use high-level jargon and CS principles. Minimal guidance."
        }
        system_prompt = prompts.get(level, "You are an expert programming tutor.")

        user_prompt = f"Language: {language}\nCode: {code}\nError: {error_message}"
        
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(system_instruction=system_prompt)
        )
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

def run_ai_code_review(code, language, review_type, level):
    if not AI_API_KEY: return "API Key missing."
    try:
        client = genai.Client(api_key=AI_API_KEY)
        if review_type == "static_check":
            system_prompt = f"Perform a {level} level style and best practice review for {language}."
        else: # complexity
            system_prompt = f"Analyze time/space complexity (Big O) for this {language} code at a {level} level."

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=code,
            config=genai.types.GenerateContentConfig(system_instruction=system_prompt)
        )
        return response.text
    except Exception as e:
        return f"AI Review Error: {str(e)}"

# --- Piston Execution Engine (Replaces Docker) ---

def execute_code_piston(language, code):
    config = PISTON_CONFIG.get(language)
    if not config:
        return "Error: Unsupported language.", ""

    payload = {
        "language": config["language"],
        "version": config["version"],
        "files": [{"content": code}]
    }

    try:
        # Calling the public Piston API
        resp = requests.post("https://emkc.org/api/v2/piston/execute", json=payload, timeout=10)
        data = resp.json()
        
        run_data = data.get('run', {})
        compile_data = data.get('compile', {})
        
        stdout = run_data.get('stdout', '')
        stderr = (compile_data.get('stderr', '') + "\n" + run_data.get('stderr', '')).strip()
        
        return stdout, stderr
    except Exception as e:
        return f"System Error: {str(e)}", str(e)

# --- API Endpoints ---

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    output, raw_error = execute_code_piston(data.get("language"), data.get("code"))
    return jsonify({'output': output, 'raw_error': raw_error})

@app.route('/explain', methods=['POST'])
def explain_error():
    data = request.json
    explanation = get_ai_explanation(data.get('code'), data.get('language'), data.get('raw_error'), data.get('level'))
    return jsonify({"explanation": explanation})

@app.route('/code_review', methods=['POST'])
def code_review():
    data = request.json
    analysis = run_ai_code_review(data.get("code"), data.get("language"), data.get("review_type"), data.get('level'))
    return jsonify({"output": analysis})

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "Online", "mode": "Free Tier (Piston)"})

if __name__ == '__main__':
    # Render and other hosts provide a PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)