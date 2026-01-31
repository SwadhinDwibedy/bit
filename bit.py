import subprocess
import sys
import os
from time import sleep
from dotenv import load_dotenv
from google import genai
from google.genai import types

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    print("❌ GEMINI_API_KEY not found in .env")
    sys.exit(1)

# -----------------------------
# Detect Project Type
# -----------------------------
def detect_project_type():
    files = os.listdir('.')
    if 'package.json' in files:
        return 'node'
    elif 'requirements.txt' in files or any(f.endswith('.py') for f in files):
        return 'python'
    elif any(f.endswith('.rs') for f in files):
        return 'rust'
    return 'generic'

# -----------------------------
# Create .gitignore
# -----------------------------
def create_gitignore(project_type):
    content_map = {
        "python": "__pycache__/\n*.pyc\n.env\nvenv/\n",
        "node": "node_modules/\n.env\n",
        "rust": "target/\n.env\n",
        "generic": ".env\n"
    }

    with open(".gitignore", "w", encoding="utf-8") as f:
        f.write(content_map[project_type])

    print(f"✅ Created .gitignore for {project_type}")

# -----------------------------
# Initialize Git
# -----------------------------
def bit_init():
    project_type = detect_project_type()
    print(f"🔍 Detected project type: {project_type}")

    create_gitignore(project_type)
    subprocess.run(["git", "init"], check=True)
    print("✅ Git repository initialized")

# -----------------------------
# Gemini commit generation with retry
# -----------------------------
def commit_with_gemini(diff, retries=3, wait_sec=2):
    client = genai.Client(api_key=GEMINI_KEY)
    attempt = 0

    while attempt < retries:
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=f"""
You are a Git commit assistant.
Generate ONE short Conventional Commit message for this git diff:

{diff}
""",
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                )
            )
            text = response.text.strip().split("\n")[0]
            if text:
                return text
            else:
                raise ValueError("Empty response from Gemini")
        except Exception as e:
            attempt += 1
            print(f"⚠ Gemini attempt {attempt} failed: {e}")
            if attempt < retries:
                print(f"💡 Retrying in {wait_sec} seconds...")
                sleep(wait_sec)
            else:
                raise

# -----------------------------
# Bit commit
# -----------------------------
def bit_commit():
    diff = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    ).stdout

    if not diff.strip():
        print("⚠ No staged changes. Run: git add .")
        return

    print("🤖 Generating commit message with Gemini...")

    try:
        commit_message = commit_with_gemini(diff)
        print(f"\n✅ (Gemini) Commit message:\n{commit_message}\n")
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        print("🎉 Commit successful")
    except Exception as e:
        print(f"❌ AI commit failed: {e}")

# -----------------------------
# CLI Router
# -----------------------------
def main():
    args = sys.argv[1:]

    if not args:
        print("⚠ Usage: python bit.py <init | commit | git-command>")
        return

    if args[0] == "init":
        bit_init()
    elif args[0] == "commit":
        bit_commit()
    else:
        subprocess.run(["git"] + args)

if __name__ == "__main__":
    main()
