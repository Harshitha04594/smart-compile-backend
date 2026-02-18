import os
import requests
import json
import base64
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) 

AI_API_KEY = os.getenv("AI_API_KEY")

if AI_API_KEY:
    genai.configure(api_key=AI_API_KEY)

JUDGE0_URL = "https://ce.judge0.com/submissions?wait=true&base64_encoded=true"
JUDGE0_LANG_IDS = {"python": 71, "java": 62, "c": 50, "cpp": 54}

def decode_judge0(b64_data):
    if not b64_data: return ""
    try:
        return base64.b64decode(str(b64_data)).decode('utf-8')
    except:
        return str(b64_data)

def ai_modify_code(code, language, task, level="easy", raw_error=""):
    if not AI_API_KEY: 
        return "AI Error: API Key missing in environment variables."
    
    # We try these model names in order. 
    # 'gemini-1.5-flash' is the most stable fallback.
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-latest']
    
    prompts = {
        "comment": f"Add professional inline comments to this {language} code. Return ONLY the code. No markdown.",
        "format": f"Reformat this {language} code for clean style. Return ONLY the code. No markdown.",
        "explain": f"As a computer science tutor for a {level} level student, explain this error: {raw_error}. Code context: {code}",
        "static_check": f"Perform a professional code review for this {language} code at a {level} level.",
        "complexity": f"Analyze the Time and Space complexity (Big O) of this {language} code for a {level} level student."
    }
    
    instruction = prompts.get(task, "Review this code.")
    full_prompt = f"{instruction}\n\nCode:\n{code}"

    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(full_prompt)
            
            if response and response.text:
                # Success! Clean up the response
                res_text = response.text
                res_text = res_text.replace(f"```{language}", "").replace("```", "").strip()
                if res_text.startswith("```"):
                     res_text = res_text.split("\n", 1)[-1].rsplit("\n", 1)[0]
                return res_text.strip()
        
        except exceptions.ResourceExhausted:
            # 429 Error: Try the next model in the list
            continue 
        except exceptions.NotFound:
            # 404 Error: Model name might be slightly different, try next
            last_error = f"Model {model_name} not found."
            continue
        except Exception as e:
            last_error = str(e)
            continue

    return f"AI Error: Could not connect to any Gemini models. Last error: {last_error}"

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    lang_key = str(data.get("language", "python")).lower().strip()
    code = data.get("code", "").strip()
    
    lang_id = JUDGE0_LANG_IDS.get(lang_key)
    if not lang_id:
        return jsonify({'output': "Unsupported Language Selection."})

    try:
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
            final_output = stdout if stdout else "Execution successful (no output)."
            raw_err = ""
        elif status == "Compilation Error":
            final_output = f"Compilation Error:\n{compile_out}"
            raw_err = compile_out
        else:
            final_output = f"Error ({status}):\n{stderr}"
            raw_err = stderr

        return jsonify({'output': final_output.strip(), 'raw_error': raw_err.strip()})
    except Exception as e:
        return jsonify({'output': f"Backend Execution Error: {str(e)}"})

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
    return jsonify({"status": "Active", "engine": "Judge0", "ai": "Gemini Multi-Tier Ready"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)