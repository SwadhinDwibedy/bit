#!/usr/bin/env python
import subprocess
import sys
import os
import io
from time import sleep
from dotenv import load_dotenv
from google import genai
from google.genai import types

# -----------------------------
# Force UTF-8 output for Windows console
# -----------------------------
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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
# Create / Update .gitignore
# -----------------------------
def create_gitignore(project_type):
    gitignore_file = ".gitignore"
    content_map = {
        "python": "__pycache__/\n*.pyc\n.env\nvenv/\n",
        "node": "node_modules/\n.env\n",
        "rust": "target/\n.env\n",
        "generic": ".env\n"
    }
    existing = ""
    if os.path.exists(gitignore_file):
        with open(gitignore_file, "r", encoding="utf-8") as f:
            existing = f.read()

    content_to_add = content_map.get(project_type, ".env\n")
    if "bit-/" not in existing:
        content_to_add += "bit-/\n"  # Add known temp folder
    with open(gitignore_file, "a", encoding="utf-8") as f:
        f.write(content_to_add)
    print(f"✅ 🔹 Bit: Updated .gitignore for {project_type}")

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
        return "⚠ 🔹 Bit AI suggestion unavailable. Please try again later."

# -----------------------------
# Initialize repo
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
# Generate commit message with Gemini
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
                return "chore: update code (AI unavailable)"

# -----------------------------
# Commit code safely
# -----------------------------
def bit_commit():
    # Check staged changes
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout

    if not staged.strip():
        # Only auto-add if HEAD exists
        head_exists = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if head_exists.returncode == 0:
            print("ℹ 🔹 Bit: No staged changes detected. Running 'git add .' automatically.")
            try:
                subprocess.run(["git", "add", "."], check=True)
            except subprocess.CalledProcessError as e:
                print(f"⚠ 🔹 Bit: Auto-add failed: {e}")
                print("ℹ 🔹 Bit: Adding files individually...")
                modified = subprocess.run(
                    ["git", "diff", "--name-only"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace"
                ).stdout
                if modified.strip():
                    for f in modified.strip().split("\n"):
                        if f:
                            try:
                                subprocess.run(["git", "add", f], check=True, capture_output=True)
                            except subprocess.CalledProcessError:
                                print(f"⚠ 🔹 Bit: Skipping problematic file: {f}")
        else:
            print("ℹ 🔹 Bit: Repository has no commits yet, skipping auto-add.")

    diff = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout

    if not diff.strip():
        print("⚠ 🔹 Bit: Nothing to commit even after adding.")
        return

    print("🤖 🔹 Bit: Generating commit message with Gemini...")
    commit_message = commit_with_gemini(diff)
    print(f"\n✅ 🔹 Bit (Gemini) Commit message:\n{commit_message}\n")
    subprocess.run(["git", "commit", "-m", commit_message], check=True)
    print("🎉 🔹 Bit: Commit successful")

# -----------------------------
# Clone repository safely
# -----------------------------
def bit_clone(url, target=None):
    folder = target or url.split("/")[-1].replace(".git", "")
    if os.path.exists(folder) and os.listdir(folder):
        print(f"⚠ 🔹 Bit: Destination path '{folder}' already exists and is not empty. Skipping clone.")
        return
    print(f"🔹 Bit: Cloning repository {url} into {folder} ...")
    subprocess.run(["git", "clone", url, folder], check=True)
    print("✅ 🔹 Bit: Clone successful")

# -----------------------------
# Passthrough for other git commands
# -----------------------------
def bit_passthrough(args):
    cmd = ["git"] + args
    print(f"🔹 Bit: Passing through to Git: git {' '.join(args)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.stdout: print(result.stdout)
        if result.stderr: print(result.stderr)
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
        print("⚠ 🔹 Bit: Usage: bit <init | commit | clone | other-git-commands>")
        return

    command = args[0].lower()
    if command == "init":
        bit_init()
    elif command == "commit":
        bit_commit()
    elif command == "clone":
        url = args[1] if len(args) > 1 else None
        target = args[2] if len(args) > 2 else None
        if not url:
            print("⚠ 🔹 Bit: Usage: bit clone <repo-url> [target-folder]")
            return
        bit_clone(url, target)
    else:
        bit_passthrough(args)

if __name__ == "__main__":
    main()
