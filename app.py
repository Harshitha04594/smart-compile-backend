import os
import requests
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) 

# --- AI CONFIGURATION ---
AI_API_KEY = os.getenv("AI_API_KEY")
if AI_API_KEY:
    # Stable configuration for Google AI
    genai.configure(api_key=AI_API_KEY)

# --- JUDGE0 CONFIGURATION ---
# The URL must include base64_encoded=true so Judge0 decodes the code before running it
JUDGE0_URL = "https://ce.judge0.com/submissions?wait=true&base64_encoded=true"

JUDGE0_LANG_IDS = {
    "python": 71, 
    "java": 62,   
    "c": 50,      
    "cpp": 54     
}

def decode_judge0(b64_data):
    """Safely decodes base64 output from Judge0."""
    if not b64_data: return ""
    try:
        return base64.b64decode(str(b64_data)).decode('utf-8')
    except:
        return str(b64_data)

def ai_modify_code(code, language, task, level="easy", raw_error=""):
    if not AI_API_KEY: 
        return "AI Error: API Key missing in Render environment."
    
    try:
        # Using Gemini 2.0 Flash
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompts = {
            "comment": f"Add professional inline comments to this {language} code. Return ONLY the code. No markdown formatting.",
            "format": f"Reformat this {language} code for clean style. Return ONLY the code. No markdown.",
            "explain": f"You are a computer science tutor for a {level} level student. Explain this error: {raw_error}. Code context: {code}",
            "static_check": f"Perform a professional code review for this {language} code at a {level} level.",
            "complexity": f"Analyze the Time and Space complexity (Big O notation) of this {language} code for a {level} level student."
        }
        
        instruction = prompts.get(task, "Review this code.")
        full_prompt = f"{instruction}\n\nCode:\n{code}"

        response = model.generate_content(full_prompt)
        
        if not response or not response.text:
            return "AI Error: Model returned an empty response."

        res_text = response.text
        # Clean up output (remove markdown code blocks)
        res_text = res_text.replace(f"```{language}", "").replace("```", "").strip()
        if res_text.startswith("```"):
             res_text = res_text.split("\n", 1)[-1].rsplit("\n", 1)[0]
             
        return res_text.strip()

    except Exception as e:
        if "429" in str(e):
            return "AI Error 429: Gemini 2.0 Limit Reached. Wait 1 minute and try again."
        return f"AI Error: {str(e)}"

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    lang_key = str(data.get("language", "python")).lower().strip()
    code = data.get("code", "").strip()
    
    if not code:
        return jsonify({'output': "Error: Editor is empty."})

    lang_id = JUDGE0_LANG_IDS.get(lang_key)
    if not lang_id:
        return jsonify({'output': f"Error: Language '{lang_key}' is not supported."})

    try:
        # Encode source code to base64 for Judge0
        source_base64 = base64.b64encode(code.encode('utf-8')).decode('utf-8')

        resp = requests.post(JUDGE0_URL, json={
            "source_code": source_base64,
            "language_id": lang_id
        }, timeout=20)
        
        result = resp.json()
        stdout = decode_judge0(result.get('stdout'))
        stderr = decode_judge0(result.get('stderr'))
        compile_out = decode_judge0(result.get('compile_output'))
        status = result.get('status', {}).get('description', 'Unknown')

        if status == "Accepted":
            final_output = stdout if stdout else "Code executed successfully (no output)."
            raw_err = ""
        elif status == "Compilation Error":
            final_output = f"Compilation Error:\n{compile_out}"
            raw_err = compile_out
        else:
            final_output = f"Error ({status}):\n{stderr}"
            raw_err = stderr

        return jsonify({'output': final_output.strip(), 'raw_error': raw_err.strip()})
    except Exception as e:
        return jsonify({'output': f"Backend Error: {str(e)}"})

@app.route('/code_review', methods=['POST'])
def code_review():
    data = request.json
    task = data.get("review_type", "static_check")
    res = ai_modify_code(data.get("code"), data.get("language"), task, data.get("level", "easy"))
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
    return jsonify({"status": "Online", "engine": "Judge0", "ai": "Gemini-2.0-Flash"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)