import os
import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv

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

def ai_modify_code(code, language, task, level="easy", raw_error=""):
    if not AI_API_KEY: return "AI Key missing."
    try:
        client = genai.Client(api_key=AI_API_KEY)
        prompts = {
            "comment": f"Add comments to this {language} code. Return ONLY code.",
            "format": f"Format this {language} code. Return ONLY code.",
            "explain": f"Explain this error for a {level} student: {raw_error}. Code: {code}"
        }
        # Using 1.5-flash for higher stability
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=code if task != "explain" else prompts["explain"],
            config=genai.types.GenerateContentConfig(system_instruction=prompts.get(task, ""))
        )
        return response.text.replace(f"```{language}", "").replace("```", "").strip()
    except Exception as e:
        return f"AI Error (Quota likely reached): {str(e)}"

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    raw_lang = data.get("language", "python")
    lang_key = str(raw_lang).lower().strip()
    code = data.get("code", "").strip()
    
    if not code:
        return jsonify({'output': "Error: The code editor is empty."})

    config = PISTON_CONFIG.get(lang_key)
    if not config:
        return jsonify({'output': f"Error: Language '{raw_lang}' is not supported."})

    try:
        resp = requests.post("https://emkc.org/api/v2/piston/execute", json={
            "language": config["language"],
            "version": config["version"],
            "files": [{"content": code}]
        }, timeout=15)
        
        result = resp.json()
        run_info = result.get('run', {})
        
        # AGGRESSIVE EXTRACTION
        stdout = run_info.get('stdout', '')
        stderr = run_info.get('stderr', '')
        combined_output = run_info.get('output', '') # This is usually where Piston hides the result
        compile_err = result.get('compile', {}).get('stderr', '')

        # 1. Check for compilation errors first
        if compile_err:
            return jsonify({'output': compile_err.strip()})
        
        # 2. Check for runtime errors
        if stderr:
            return jsonify({'output': stderr.strip()})

        # 3. Check for stdout
        if stdout and stdout.strip():
            return jsonify({'output': stdout.strip()})

        # 4. FALLBACK: Check the 'output' field if stdout was empty
        if combined_output and combined_output.strip():
            return jsonify({'output': combined_output.strip()})
            
        return jsonify({'output': "Code executed successfully with no output."})

    except Exception as e:
        return jsonify({'output': f"Backend Error: {str(e)}"})

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
    return jsonify({"status": "Online"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)