#!/usr/bin/env python
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
    print("❌ 🔹 Bit: GEMINI_API_KEY not found in .env")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_KEY)

# -----------------------------
# Detect Project Type
# -----------------------------
def detect_project_type():
    files = os.listdir('.') if os.path.exists('.') else []
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
    print(f"✅ 🔹 Bit: Created .gitignore for {project_type}")

# -----------------------------
# AI Suggestion Helper
# -----------------------------
def ai_suggest(command_str, context=""):
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"""
You are an expert Git assistant.
User just ran this command: {command_str}
Context: {context}

Provide helpful suggestions, warnings, or improvements in short sentences.
""",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="low")
            )
        )
        return response.text.strip()
    except Exception:
        # Fallback if AI is overloaded or fails
        return "⚠ 🔹 Bit AI suggestion unavailable. Please try again later."

# -----------------------------
# Bit init
# -----------------------------
def bit_init():
    print("🔹 Bit: Initializing repository with AI assistance...")
    project_type = detect_project_type()
    create_gitignore(project_type)
    subprocess.run(["git", "init"], check=True)
    ai_text = ai_suggest("git init", context="Suggest gitignore and folder protection for this project.")
    print(f"💡 🔹 Bit AI Suggestion: {ai_text}")
    print("✅ 🔹 Bit: Repository initialized")

# -----------------------------
# Gemini commit generator
# -----------------------------
def commit_with_gemini(diff, retries=3, wait_sec=2):
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
            print(f"⚠ 🔹 Bit: Gemini attempt {attempt} failed: {e}")
            if attempt < retries:
                print(f"💡 🔹 Bit: Retrying in {wait_sec} seconds...")
                sleep(wait_sec)
            else:
                # Fallback commit message if AI fails completely
                return "chore: update code (AI unavailable)"

# -----------------------------
# Bit commit
# -----------------------------
def bit_commit():
    # Auto-stage all if nothing staged
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    ).stdout

    if not staged or not staged.strip():
        print("ℹ 🔹 Bit: No staged changes detected. Running 'bit add .' automatically.")
        subprocess.run(["git", "add", "."], check=True)

    diff = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    ).stdout

    if not diff or not diff.strip():
        print("⚠ 🔹 Bit: Nothing to commit even after adding.")
        return

    print("🤖 🔹 Bit: Generating commit message with Gemini...")
    try:
        commit_message = commit_with_gemini(diff)
        print(f"\n✅ 🔹 Bit (Gemini) Commit message:\n{commit_message}\n")
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        print("🎉 🔹 Bit: Commit successful")
    except Exception as e:
        print(f"❌ 🔹 Bit: AI commit failed: {e}")

# -----------------------------
# Bit passthrough for all other commands
# -----------------------------
def bit_passthrough(args):
    cmd = ["git"] + args
    print(f"🔹 Bit: Passing through to Git: git {' '.join(args)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        # AI suggestion for any command
        suggestions = ai_suggest(f"git {' '.join(args)}", context=result.stdout)
        print(f"\n💡 🔹 Bit AI Suggestion:\n{suggestions}\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ 🔹 Bit: Git command failed with exit code {e.returncode}")

# -----------------------------
# CLI Router
# -----------------------------
def main():
    args = sys.argv[1:]
    if not args:
        print("⚠ 🔹 Bit: Usage: bit <init | commit | other-git-commands>")
        return

    command = args[0].lower()
    if command == "init":
        bit_init()
    elif command == "commit":
        bit_commit()
    else:
        bit_passthrough(args)

if __name__ == "__main__":
    main()
