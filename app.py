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

# Mapping project languages to Piston API identifiers
PISTON_CONFIG = {
    "python": {"language": "python", "version": "3.10.0"},
    "java": {"language": "java", "version": "15.0.2"},
    "c": {"language": "c", "version": "10.2.0"},
    "cpp": {"language": "cpp", "version": "10.2.0"}
}

# --- AI Helper (Using stable 1.5-flash for higher limits) ---
def ai_modify_code(code, language, task, level="easy", raw_error=""):
    if not AI_API_KEY: return "AI Key missing in backend."
    try:
        client = genai.Client(api_key=AI_API_KEY)
        prompts = {
            "comment": f"Add professional comments to this {language} code. Return ONLY code.",
            "format": f"Reformat this {language} code for clean indentation. Return ONLY code.",
            "explain": f"You are a {level} level tutor. Explain this error: {raw_error}. Code: {code}"
        }
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=code if task != "explain" else prompts["explain"],
            config=genai.types.GenerateContentConfig(system_instruction=prompts.get(task, ""))
        )
        return response.text.replace(f"```{language}", "").replace("```", "").strip()
    except Exception as e:
        return f"AI Error (Quota likely exceeded): {str(e)}"

# --- Execution Engine (Ultra-Robust) ---

def execute_code_piston(language, code):
    # Fix: Convert "Python" to "python" to match config keys
    lang_key = str(language).lower()
    config = PISTON_CONFIG.get(lang_key)
    
    if not config:
        return f"Error: Language '{language}' is not supported.", ""

    payload = {
        "language": config["language"],
        "version": config["version"],
        "files": [{"content": code}]
    }

    try:
        resp = requests.post("https://emkc.org/api/v2/piston/execute", json=payload, timeout=10)
        data = resp.json()
        
        # Deep Extraction: Check all possible output locations in Piston response
        run_data = data.get('run', {})
        compile_data = data.get('compile', {})
        
        stdout = run_data.get('stdout', '')
        stderr = run_data.get('stderr', '')
        compile_err = compile_data.get('stderr', '')
        combined = run_data.get('output', '')

        # Priority: Compilation Error > Runtime Error > Standard Output
        if compile_err:
            return compile_err.strip(), compile_err.strip()
        if stderr:
            return stderr.strip(), stderr.strip()
        if stdout:
            return stdout.strip(), ""
        if combined:
            return combined.strip(), ""
            
        return "Code executed successfully (no output).", ""
    except Exception as e:
        return f"System Error: {str(e)}", str(e)

# --- API Endpoints ---

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    output, raw_error = execute_code_piston(data.get("language"), data.get("code"))
    # Always return 'output' key to match your React App.js
    return jsonify({'output': output, 'raw_error': raw_error})

@app.route('/auto_comment', methods=['POST'])
def auto_comment():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "comment")
    return jsonify({"output": res})

@app.route('/format_code', methods=['POST'])
def format_code():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "format")
    return jsonify({"output": res})

@app.route('/explain', methods=['POST'])
def explain():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "explain", data.get("level"), data.get("raw_error"))
    return jsonify({"explanation": res})

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Online", "mode": "Free Tier (Piston)"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)