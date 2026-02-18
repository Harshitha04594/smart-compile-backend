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
        return "AI Error: API Key missing."
    
    # Models to try in order of preference
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash']
    
    prompts = {
        "comment": f"Add professional inline comments to this {language} code. Return ONLY the code.",
        "format": f"Reformat this {language} code for clean style. Return ONLY the code.",
        "explain": f"Explain this error as a tutor: {raw_error}. Code: {code}",
        "static_check": f"Perform a code review for this {language} code at {level} level.",
        "complexity": f"Analyze the Time/Space complexity (Big O) of this {language} code."
    }
    
    instruction = prompts.get(task, "Review this code.")
    full_prompt = f"{instruction}\n\nCode:\n{code}"

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            # Add a tiny delay between attempts if retrying
            response = model.generate_content(full_prompt)
            
            if response and response.text:
                res_text = response.text.replace(f"```{language}", "").replace("```", "").strip()
                return res_text
        
        except exceptions.ResourceExhausted:
            # If 429 happens on 2.0, this loop continues to 1.5
            continue 
        except Exception as e:
            return f"AI Error ({model_name}): {str(e)}"

    return "All AI models are currently busy (Quota reached). Please try again in 60 seconds."

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    lang_key = str(data.get("language", "python")).lower().strip()
    code = data.get("code", "").strip()
    lang_id = JUDGE0_LANG_IDS.get(lang_key)
    if not lang_id: return jsonify({'output': "Unsupported Language"})

    try:
        source_base64 = base64.b64encode(code.encode('utf-8')).decode('utf-8')
        resp = requests.post(JUDGE0_URL, json={"source_code": source_base64, "language_id": lang_id}, timeout=20)
        result = resp.json()
        
        stdout = decode_judge0(result.get('stdout'))
        stderr = decode_judge0(result.get('stderr'))
        compile_out = decode_judge0(result.get('compile_output'))
        status = result.get('status', {}).get('description', 'Unknown')

        if status == "Accepted":
            final_output = stdout if stdout else "Success (No Output)"
            raw_err = ""
        else:
            final_output = f"{status}\n{compile_out if status == 'Compilation Error' else stderr}"
            raw_err = final_output

        return jsonify({'output': final_output.strip(), 'raw_error': raw_err.strip()})
    except Exception as e:
        return jsonify({'output': f"Execution Error: {str(e)}"})

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

# Added simple health check for Render
@app.route("/", methods=["GET"])
def health():
    return "Smart Compile Backend Active"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))