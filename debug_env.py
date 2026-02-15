import os
from dotenv import load_dotenv

# Try to load the file
load_dotenv()

print("--- Environment Debugger ---")
print(f"Current Working Directory: {os.getcwd()}")

# Check if .env file exists in this folder
if os.path.exists(".env"):
    print("✅ Found file named: .env")
else:
    print("❌ Could NOT find a file named '.env' in this folder.")
    # List all files to see if it's named something else
    print(f"Files in this folder: {os.listdir('.')}")

# Check the key
key = os.getenv("AI_API_KEY")
if key:
    print(f"✅ AI_API_KEY loaded successfully! (Starts with: {key[:5]}...)")
else:
    print("❌ AI_API_KEY is still empty.")