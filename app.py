import os
import requests
import json
import base64
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) 

AI_API_KEY = os.getenv("AI_API_KEY")

# --- JUDGE0 CONFIGURATION (Replacing the restricted Piston API) ---
# We use the Judge0 public instance for the demo
JUDGE0_URL = "https://ce.judge0.com/submissions?wait=true"

# Language IDs for Judge0
JUDGE0_LANG_IDS = {
    "python": 71, # Python (3.8.1)
    "java": 62,   # Java (OpenJDK 13.0.1)
    "c": 50,      # C (GCC 9.2.0)
    "cpp": 54     # C++ (GCC 9.2.0)
}

def ai_modify_code(code, language, task, level="easy", raw_error=""):
    if not AI_API_KEY: 
        return "AI Key missing in backend environment variables."
    
    try:
        client = genai.Client(api_key=AI_API_KEY)
        
        prompts = {
            "comment": f"Add helpful inline comments to this {language} code. Return ONLY the code. No markdown.",
            "format": f"Reformat this {language} code for professional style. Return ONLY the code. No markdown.",
            "explain": f"You are a computer science tutor for a {level} level student. Explain this error: {raw_error}. Code context: {code}",
            "static_check": f"Conduct a professional code review for this {language} code. Target level: {level}.",
            "complexity": f"Analyze the Time and Space complexity of this {language} code for a {level} level student."
        }
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=code if task not in ["explain", "static_check", "complexity"] else prompts.get(task),
            config=genai.types.GenerateContentConfig(system_instruction=prompts.get(task, ""))
        )
        
        return response.text.replace(f"```{language}", "").replace("```", "").strip()

    except Exception as e:
        return f"AI Error: {str(e)}"

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    raw_lang = data.get("language", "python")
    lang_key = str(raw_lang).lower().strip()
    code = data.get("code", "").strip()
    
    if not code:
        return jsonify({'output': "Error: Editor is empty."})

    lang_id = JUDGE0_LANG_IDS.get(lang_key)
    if not lang_id:
        return jsonify({'output': f"Error: Language '{raw_lang}' is not supported by backend."})

    try:
        # Judge0 requires base64 encoding for the code to handle special characters safely
        source_base64 = base64.b64encode(code.encode('utf-8')).decode('utf-8')

        # 1. Send Request to Judge0
        resp = requests.post(JUDGE0_URL, json={
            "source_code": source_base64,
            "language_id": lang_id,
            "base64_encoded": True
        }, timeout=20)
        
        result = resp.json()

        # 2. Extract results from Judge0 response
        # Judge0 also encodes its output in base64
        stdout_b64 = result.get('stdout')
        stderr_b64 = result.get('stderr')
        compile_b64 = result.get('compile_output')
        status = result.get('status', {}).get('description', 'Unknown')

        def decode_safe(b64_str):
            if not b64_str: return ""
            try:
                return base64.b64decode(b64_str).decode('utf-8')
            except:
                return str(b64_str)

        stdout = decode_safe(stdout_b64)
        stderr = decode_safe(stderr_b64)
        compile_err = decode_safe(compile_b64)

        # 3. Decision Logic
        if status == "Accepted":
            final_output = stdout if stdout else "Code executed successfully (no output)."
            raw_err = ""
        elif status == "Compilation Error":
            final_output = f"Compilation Error:\n{compile_err}"
            raw_err = compile_err
        else:
            final_output = f"{status}:\n{stderr}"
            raw_err = stderr

        return jsonify({'output': final_output, 'raw_error': raw_err})

    except Exception as e:
        return jsonify({'output': f"Execution Failed: {str(e)}", 'raw_error': str(e)})

@app.route('/code_review', methods=['POST'])
def code_review_route():
    data = request.json
    task = data.get("review_type", "static_check")
    res = ai_modify_code(data.get("code"), data.get("language"), task, data.get("level", "easy"))
    return jsonify({"output": res})

@app.route('/explain', methods=['POST'])
def explain_route():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "explain", data.get("level", "easy"), data.get("raw_error", ""))
    return jsonify({"explanation": res})

@app.route('/auto_comment', methods=['POST'])
def auto_comment_route():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "comment")
    return jsonify({"output": res})

@app.route('/format_code', methods=['POST'])
def format_code_route():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "format")
    return jsonify({"output": res})

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Online", "engine": "Judge0 (Migrated)"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)