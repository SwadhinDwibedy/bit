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
# Force UTF-8 output for Windows
# -----------------------------
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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
    files = os.listdir(".")
    if "package.json" in files:
        return "node"
    if "requirements.txt" in files or any(f.endswith(".py") for f in files):
        return "python"
    if any(f.endswith(".rs") for f in files):
        return "rust"
    return "generic"

# -----------------------------
# Create / Update .gitignore
# -----------------------------
def create_gitignore(project_type):
    gitignore = ".gitignore"
    defaults = {
        "python": "__pycache__/\n*.pyc\nvenv/\n.env\n",
        "node": "node_modules/\n.env\n",
        "rust": "target/\n.env\n",
        "generic": ".env\n",
    }

    existing = ""
    if os.path.exists(gitignore):
        existing = open(gitignore, encoding="utf-8").read()

    content = ""
    if defaults[project_type] not in existing:
        content += defaults[project_type]
    if "bit-/" not in existing:
        content += "bit-/\n"

    if content:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write(content)

    print(f"✅ 🔹 Bit: .gitignore updated ({project_type})")

# -----------------------------
# AI Suggestion Helper
# -----------------------------
def ai_suggest(command, context=""):
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"""
You are an expert Git assistant.
Command: {command}
Context: {context}
Give short helpful advice.
""",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="low")
            ),
        )
        return r.text.strip()
    except Exception:
        return "⚠ 🔹 Bit AI suggestion unavailable."

# -----------------------------
# Init
# -----------------------------
def bit_init():
    print("🔹 Bit: Initializing repository...")
    create_gitignore(detect_project_type())
    subprocess.run(["git", "init"], check=True)
    print("💡", ai_suggest("git init"))
    print("✅ 🔹 Bit: Repo initialized")

# -----------------------------
# Gemini Commit Message
# -----------------------------
def commit_with_gemini(diff):
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Generate ONE Conventional Commit message:\n{diff}",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="low")
            ),
        )
        return r.text.strip().split("\n")[0]
    except Exception:
        return "chore: update code (AI unavailable)"

# -----------------------------
# Commit (SAFE + SELF-HEALING)
# -----------------------------
def bit_commit():
    # 🔥 Ensure bit temp folder is ignored
    if os.path.exists("bit-/"):
        if subprocess.run(["git", "check-ignore", "-q", "bit-/"]).returncode != 0:
            with open(".gitignore", "a", encoding="utf-8") as f:
                f.write("\nbit-/\n")
            print("ℹ 🔹 Bit: Auto-ignored bit-/ folder")

    # Check staged changes
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()

    if not staged:
        # Only auto-add if repo already has commits
        if subprocess.run(["git", "rev-parse", "--verify", "HEAD"],
                          capture_output=True,
                          encoding="utf-8",
                          errors="replace",
                          text=True).returncode == 0:
            try:
                subprocess.run(["git", "add", "."], check=True)
            except subprocess.CalledProcessError:
                print("⚠ 🔹 Bit: git add . failed, adding files individually")
                modified = subprocess.run(
                    ["git", "diff", "--name-only"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                ).stdout.strip()
                for f in modified.splitlines():
                    try:
                        subprocess.run(["git", "add", f], check=True)
                    except subprocess.CalledProcessError:
                        print(f"⚠ 🔹 Skipped: {f}")

    diff = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()

    if not diff:
        print("⚠ 🔹 Bit: Nothing to commit")
        return

    print("🤖 🔹 Bit: Generating commit message...")
    msg = commit_with_gemini(diff)
    print("✅", msg)
    subprocess.run(["git", "commit", "-m", msg], check=True)
    print("🎉 🔹 Bit: Commit successful")

# -----------------------------
# Clone safely
# -----------------------------
def bit_clone(url, target=None):
    folder = target or url.split("/")[-1].replace(".git", "")
    if os.path.exists(folder) and os.listdir(folder):
        print(f"⚠ 🔹 Bit: Destination '{folder}' exists, skipping clone")
        return
    subprocess.run(["git", "clone", url, folder], check=True)
    print("✅ 🔹 Bit: Clone successful")

# -----------------------------
# Passthrough
# -----------------------------
def bit_passthrough(args):
    print(f"🔹 Bit → git {' '.join(args)}")
    r = subprocess.run(["git"] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        print(r.stderr)
    print("💡", ai_suggest(f"git {' '.join(args)}", r.stdout))

# -----------------------------
# CLI
# -----------------------------
def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: bit <init|commit|clone|git-command>")
        return

    cmd = args[0]
    if cmd == "init":
        bit_init()
    elif cmd == "commit":
        bit_commit()
    elif cmd == "clone":
        bit_clone(args[1], args[2] if len(args) > 2 else None)
    else:
        bit_passthrough(args)

if __name__ == "__main__":
    main()
