import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app) 

AI_API_KEY = os.getenv("AI_API_KEY")

PISTON_CONFIG = {
    "python": {"language": "python", "version": "3.10.0"},
    "java": {"language": "java", "version": "15.0.2"},
    "c": {"language": "c", "version": "10.2.0"},
    "cpp": {"language": "cpp", "version": "10.2.0"}
}

# --- AI Utility Functions ---

def get_ai_explanation(code, language, error_message, level):
    if not AI_API_KEY: return "API Key missing."
    try:
        client = genai.Client(api_key=AI_API_KEY) 
        prompts = {
            'easy': "You are a friendly beginner tutor. Use simple analogies and provide fixed code.",
            'medium': "You are an intermediate instructor. Provide hints and technical terms, not the full code.",
            'hard': "You are a critical peer-reviewer. Use high-level jargon and minimal guidance."
        }
        system_prompt = prompts.get(level, "You are an expert programming tutor.")
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=f"Language: {language}\nCode: {code}\nError: {error_message}",
            config=genai.types.GenerateContentConfig(system_instruction=system_prompt)
        )
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"

def run_ai_code_review(code, language, review_type, level):
    if not AI_API_KEY: return "API Key missing."
    try:
        client = genai.Client(api_key=AI_API_KEY)
        system_prompt = f"Analyze {language} code for {review_type} at a {level} level."
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=code,
            config=genai.types.GenerateContentConfig(system_instruction=system_prompt)
        )
        return response.text
    except Exception as e:
        return f"AI Review Error: {str(e)}"

def ai_modify_code(code, language, task):
    if not AI_API_KEY: return code
    try:
        client = genai.Client(api_key=AI_API_KEY)
        prompts = {
            "comment": f"Add helpful comments to this {language} code. Return ONLY the code.",
            "format": f"Reformat this {language} code for clean indentation. Return ONLY the code."
        }
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=code,
            config=genai.types.GenerateContentConfig(system_instruction=prompts[task])
        )
        # Clean up markdown code blocks
        return response.text.replace(f"```{language}", "").replace("```", "").strip()
    except:
        return code

# --- Execution Engine ---

def execute_code_piston(language, code):
    config = PISTON_CONFIG.get(language)
    if not config: return "Unsupported language.", ""
    try:
        resp = requests.post("https://emkc.org/api/v2/piston/execute", json={
            "language": config["language"], "version": config["version"], "files": [{"content": code}]
        }, timeout=10)
        data = resp.json()
        stdout = data.get('run', {}).get('stdout', '')
        stderr = (data.get('compile', {}).get('stderr', '') + "\n" + data.get('run', {}).get('stderr', '')).strip()
        return stdout, stderr
    except Exception as e:
        return f"System Error: {str(e)}", str(e)

# --- Endpoints (Matching your React code exactly) ---

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

@app.route('/auto_comment', methods=['POST'])
def auto_comment_route():
    data = request.json
    modified_code = ai_modify_code(data.get("code"), data.get("language"), "comment")
    return jsonify({"output": modified_code}) # Matches your setCode(data.output)

@app.route('/format_code', methods=['POST'])
def format_code_route():
    data = request.json
    modified_code = ai_modify_code(data.get("code"), data.get("language"), "format")
    return jsonify({"output": modified_code}) # Matches your setCode(data.output)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Online"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)