import os
import requests
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) 

AI_API_KEY = os.getenv("AI_API_KEY")

# --- JUDGE0 CONFIGURATION ---
JUDGE0_URL = "https://ce.judge0.com/submissions?wait=true"

# Refined Language IDs for Judge0
JUDGE0_LANG_IDS = {
    "python": 71, 
    "java": 62,   
    "c": 50,      
    "cpp": 54     
}

def decode_judge0(b64_data):
    """
    Universally decodes any base64 data returned by Judge0.
    Judge0 encodes stdout, stderr, and compile_output.
    """
    if not b64_data:
        return ""
    try:
        # Decode base64 to bytes, then bytes to utf-8 string
        return base64.b64decode(str(b64_data)).decode('utf-8')
    except Exception:
        # Fallback if it's already plain text
        return str(b64_data)

def ai_modify_code(code, language, task, level="easy", raw_error=""):
    if not AI_API_KEY: return "AI Key missing."
    try:
        client = genai.Client(api_key=AI_API_KEY)
        prompts = {
            "comment": f"Add comments to this {language} code. Return ONLY code.",
            "format": f"Format this {language} code. Return ONLY code.",
            "explain": f"You are a computer science tutor for a {level} level student. Explain this error: {raw_error}. Code: {code}",
            "static_check": f"Review this {language} code for a {level} student.",
            "complexity": f"Analyze complexity of this {language} code for a {level} student."
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
        return jsonify({'output': f"Error: Language '{raw_lang}' is not supported."})

    try:
        # 1. Encode your code to base64 so Judge0 can read it safely
        source_base64 = base64.b64encode(code.encode('utf-8')).decode('utf-8')

        # 2. Call Judge0
        resp = requests.post(JUDGE0_URL, json={
            "source_code": source_base64,
            "language_id": lang_id,
            "base64_encoded": True
        }, timeout=20)
        
        result = resp.json()
        
        # 3. DECODE EVERYTHING from Judge0
        stdout = decode_judge0(result.get('stdout'))
        stderr = decode_judge0(result.get('stderr'))
        compile_out = decode_judge0(result.get('compile_output'))
        message = decode_judge0(result.get('message'))
        status = result.get('status', {}).get('description', 'Unknown')

        # 4. Build the user-friendly output
        if status == "Accepted":
            final_output = stdout if stdout else "Code executed successfully (no output)."
            raw_err = ""
        elif status == "Compilation Error":
            final_output = f"Compilation Error:\n{compile_out}"
            raw_err = compile_out
        elif "Runtime Error" in status or "NZEC" in status:
            # We combine message and stderr to give full context
            final_output = f"Runtime Error ({status}):\n{message}\n{stderr}"
            raw_err = f"{message}\n{stderr}"
        else:
            final_output = f"Status: {status}\n{message}\n{stderr}"
            raw_err = stderr

        return jsonify({'output': final_output.strip(), 'raw_error': raw_err.strip()})

    except Exception as e:
        return jsonify({'output': f"Backend Error: {str(e)}"})

@app.route('/code_review', methods=['POST'])
def code_review():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), data.get("review_type", "static_check"), data.get("level", "easy"))
    return jsonify({"output": res})

@app.route('/explain', methods=['POST'])
def explain():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "explain", data.get("level"), data.get("raw_error"))
    return jsonify({"explanation": res})

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

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Online", "engine": "Judge0 (Fully Decoded)"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)