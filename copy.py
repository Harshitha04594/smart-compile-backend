from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import uuid
import shutil
import sys
from google import genai 
from dotenv import load_dotenv # Import to load .env file

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# --- GLOBAL SETTINGS ---
# Securely retrieve the key from environment variables
# If the key is not found, it defaults to None
AI_API_KEY = os.getenv("AI_API_KEY")

# Configuration for Docker image names
RUNNERS = {
    "python": "python-runner",
    "java": "java-runner",
    "c": "c-runner",
    "cpp": "cpp-runner"
}

# --- AI Utility Functions ---

def get_ai_explanation(code, language, error_message, level):
    if not AI_API_KEY:
        return "AI Service Error: API Key not found in environment variables."
    
    try:
        client = genai.Client(api_key=AI_API_KEY) 
        
        # --- DYNAMIC SYSTEM PROMPT BASED ON LEVEL ---
        if level == 'easy':
            system_prompt = (
                "You are a friendly and patient programming tutor for a beginner (7th grade level). "
                "Explain the error using simple language and analogies. Provide the exact fixed code block."
            )
        elif level == 'medium':
            system_prompt = (
                "You are an intermediate instructor. Use standard technical terms (like 'scope', 'variable initialization', 'data type') to explain the error. "
                "Provide conceptual guidance and specific hints, but DO NOT provide the complete fixed code."
            )
        elif level == 'hard':
            system_prompt = (
                "You are a critical peer-reviewer for an advanced B.Tech student. Use precise, high-level technical jargon. "
                "Explain the underlying computer science principles causing the error. Provide minimal direct guidance."
            )
        else:
            system_prompt = "You are an expert programming tutor."

        user_prompt = (
            f"Code Language: {language}\n"
            f"User Code:\n---\n{code}\n---\n"
            f"Raw Compiler Error:\n---\n{error_message}\n---\n"
            "Please analyze the error and respond according to your persona and task."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        return response.text
    except Exception as e:
        return f"AI Service Error: Failed to call the Gemini API. Detail: {e}"


def run_ai_code_review(code, language, review_type, level):
    if not AI_API_KEY:
        return "AI Service Error: API Key not found in environment variables."

    try:
        client = genai.Client(api_key=AI_API_KEY) 

        if review_type == "static_check":
            if level == 'easy':
                 system_prompt = (
                    "You are a friendly guide for a beginner. Provide 3 simple and actionable style improvements focused on variable naming and basic readability. Use encouraging language."
                )
            elif level == 'medium':
                 system_prompt = (
                    "You are a helpful team lead. Analyze the code for standard best practices (e.g., Python PEP 8, Java standard conventions). Provide 5 specific, professional improvements."
                )
            elif level == 'hard':
                 system_prompt = (
                    "You are a senior architect. Perform a rigorous review focusing on performance traps, modularity, and object-oriented design principles. Provide deep, challenging feedback."
                )
            else:
                 system_prompt = "You are an expert static analysis tool."
            user_prompt_suffix = "Provide a detailed code review."
            
        elif review_type == "complexity":
            if level == 'easy':
                 system_prompt = (
                    "You are a simple math tutor. Explain Big O notation (O()) and the complexity of the code using non-technical terms like 'steps' or 'growth rate'. Focus on the simple operations."
                )
            elif level == 'medium':
                 system_prompt = (
                    "You are a data structures and algorithms expert. State the exact time/space complexity (e.g., O(n log n)) and explain the derivation using loops, recursion, or array access. Suggest one optimization."
                )
            elif level == 'hard':
                 system_prompt = (
                    "You are a theoretical computer scientist. Analyze the code for worst-case, average-case, and amortized complexity. Discuss cache performance or concurrency implications if applicable."
                )
            else:
                 system_prompt = "You are an expert computer science professor."
            user_prompt_suffix = "Analyze the time and space complexity."
        else:
            return "Invalid review type."


        user_query = (
            f"Code Language: {language}\n"
            f"User Code:\n---\n{code}\n---\n"
            f"{user_prompt_suffix}"
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_query,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        return response.text
    except Exception as e:
        return f"AI Service Error: Failed to call the Gemini API for code review. Detail: {e}"


def generate_auto_comment(code, language):
    if not AI_API_KEY:
        return "AI Service Error: API Key not found."

    try:
        client = genai.Client(api_key=AI_API_KEY) 
        
        system_prompt = (
            "You are an expert technical writer. Analyze the user's code and add clear, "
            "descriptive, and helpful inline comments to every part of the code that performs a distinct step or calculation. "
            "The final output MUST ONLY contain the commented code. Do not add any conversational text, headers, or explanations."
        )

        user_prompt = (
            f"Code Language: {language}\n"
            f"User Code:\n---\n{code}\n---\n"
            "Please generate the code with detailed inline comments."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        return response.text
    except Exception as e:
        return f"AI Service Error: Failed to call the Gemini API for commenting. Detail: {e}"

def format_code_ai(code, language):
    if not AI_API_KEY:
        return "AI Service Error: API Key not found."

    try:
        client = genai.Client(api_key=AI_API_KEY) 
        
        system_prompt = (
            "You are an expert code formatter. Take the raw code input and return it perfectly "
            "formatted, indented according to standard best practices (e.g., 4 spaces for Python, "
            "Java/C++/C standard bracing and indentation). The final output MUST ONLY contain the formatted code. "
            "Do not add any comments, explanations, headers, or markdown formatting blocks (like ```python)."
        )

        user_prompt = (
            f"Code Language: {language}\n"
            f"Raw Code:\n---\n{code}\n---"
            "Please format the code cleanly."
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )
        return response.text
    except Exception as e:
        return f"AI Service Error: Failed to call the Gemini API for formatting. Detail: {e}"


# --- API Endpoints ---

def execute_code(language, code):
    extensions = {
        "python": "py", "java": "java", "c": "c", "cpp": "cpp"
    }
    RUNNERS = {
        "python": "python-runner", "java": "java-runner", "c": "c-runner", "cpp": "cpp-runner"
    }

    main_filename = "Main.java" if language == "java" else f"main.{extensions.get(language)}"
    temp_dir = str(uuid.uuid4())

    try:
        os.makedirs(temp_dir)
        filepath = os.path.join(temp_dir, main_filename)

        with open(filepath, "w") as f:
            f.write(code)

        image_name = RUNNERS.get(language)
        if not image_name:
             return "Error: Unsupported language.", ""

        if language == "python":
            command = ["python", main_filename]
        elif language == "java":
            command = ["sh", "-c", f"javac {main_filename} && java Main"]
        elif language == "c":
            command = ["sh", "-c", f"gcc {main_filename} -o main && ./main"]
        elif language == "cpp":
            command = ["sh", "-c", f"g++ {main_filename} -o main && ./main"]

        result = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{os.getcwd()}/{temp_dir}:/app", image_name] + command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False
        )

        output = result.stdout
        error = result.stderr

        shutil.rmtree(temp_dir)

        return output, error

    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return f"An unexpected error occurred: {str(e)}", str(e)


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Backend is running!"})

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    code = data.get("code")
    language = data.get("language")

    if not code or not language:
        return jsonify({"output": "Error: Missing code or language.", "raw_error": ""}), 400

    output, raw_error = execute_code(language, code)
    
    return jsonify({
        'output': output,
        'raw_error': raw_error
    })

@app.route('/explain', methods=['POST'])
def explain_error():
    data = request.json
    code = data.get('code')
    language = data.get('language')
    raw_error = data.get('raw_error')
    level = data.get('level', 'easy')

    if not raw_error:
        return jsonify({"explanation": "Please run your code first to generate an error."})

    explanation = get_ai_explanation(code, language, raw_error, level)
    return jsonify({"explanation": explanation})


@app.route('/code_review', methods=['POST'])
def code_review():
    data = request.json
    code = data.get("code")
    language = data.get("language")
    review_type = data.get("review_type")
    level = data.get('level', 'easy')

    if not code or not language or not review_type:
        return jsonify({"output": "Error: Missing parameters for code review."}), 400

    analysis = run_ai_code_review(code, language, review_type, level)
    return jsonify({"output": analysis})


@app.route('/auto_comment', methods=['POST'])
def auto_comment():
    data = request.json
    code = data.get('code')
    language = data.get('language')

    if not code or not language:
        return jsonify({"explanation": "Missing code or language for commenting."})

    commented_code = generate_auto_comment(code, language)
    
    if commented_code.startswith('```'):
        end_index = commented_code.rfind('```')
        if end_index > 0:
            commented_code = commented_code[commented_code.find('\n')+1 : end_index].strip()

    return jsonify({"output": commented_code})


@app.route('/format_code', methods=['POST'])
def format_code_route():
    data = request.json
    code = data.get('code')
    language = data.get('language')

    if not code or not language:
        return jsonify({"explanation": "Missing code or language for formatting."})

    formatted_code = format_code_ai(code, language)
    
    if formatted_code.startswith('```'):
        end_index = formatted_code.rfind('```')
        if end_index > 0:
            formatted_code = formatted_code[formatted_code.find('\n')+1 : end_index].strip()


    return jsonify({"output": formatted_code})


if __name__ == '__main__':
    # It is recommended to keep debug=True during development
    app.run(host='0.0.0.0', port=5000, debug=True)