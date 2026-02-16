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
            "explain": f"Explain this error for a {level} student: {raw_error}. Code: {code}",
            "review": f"Review this {language} code and suggest improvements.",
            "complexity": f"Analyze the time and space complexity of this {language} code."
        }
        
        # Using 1.5-flash for 1,500 requests per day limit
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=code if task not in ["explain", "review", "complexity"] else prompts.get(task),
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
        compile_info = result.get('compile', {})
        
        # AGGRESSIVE EXTRACTION: Check every possible field
        stdout = run_info.get('stdout', '')
        stderr = run_info.get('stderr', '')
        output_field = run_info.get('output', '') # Piston often puts combined output here
        compile_err = compile_info.get('stderr', '')

        # Determine what to show the user (Priority Order)
        if compile_err and compile_err.strip():
            final_output = compile_err
        elif stderr and stderr.strip():
            final_output = stderr
        elif stdout and stdout.strip():
            final_output = stdout
        elif output_field and output_field.strip():
            final_output = output_field
        else:
            final_output = "Code executed successfully with no print output."

        return jsonify({'output': final_output.strip(), 'raw_error': compile_err or stderr})

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

@app.route('/ai_review', methods=['POST'])
def ai_review():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "review")
    return jsonify({"output": res})

@app.route('/complexity', methods=['POST'])
def complexity():
    data = request.json
    res = ai_modify_code(data.get("code"), data.get("language"), "complexity")
    return jsonify({"output": res})

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Online", "engine": "Piston + Gemini 1.5"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)