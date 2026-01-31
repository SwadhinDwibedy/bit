#!/usr/bin/env python
import subprocess
import sys
import os
import io
from dotenv import load_dotenv
from google import genai
from google.genai import types

# =============================
# UTF-8 SAFE OUTPUT (Windows)
# =============================
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# =============================
# ENV + GEMINI
# =============================
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("❌ Bit: GEMINI_API_KEY missing")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_KEY)

# =============================
# SAFE SUBPROCESS WRAPPER
# =============================
def run(cmd, check=False):
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=check
        )
    except subprocess.CalledProcessError as e:
        return e

# =============================
# PROJECT TYPE
# =============================
def detect_project():
    files = os.listdir(".")
    if "package.json" in files:
        return "node"
    if "requirements.txt" in files or any(f.endswith(".py") for f in files):
        return "python"
    if any(f.endswith(".rs") for f in files):
        return "rust"
    return "generic"

# =============================
# .GITIGNORE AUTO HEAL
# =============================
def ensure_gitignore():
    rules = {
        "python": "__pycache__/\n*.pyc\nvenv/\n.env\n",
        "node": "node_modules/\n.env\n",
        "rust": "target/\n.env\n",
        "generic": ".env\n",
    }

    project = detect_project()
    content = rules[project] + "bit-/\n"

    existing = ""
    if os.path.exists(".gitignore"):
        existing = open(".gitignore", encoding="utf-8").read()

    if content.strip() not in existing:
        with open(".gitignore", "a", encoding="utf-8") as f:
            f.write("\n" + content)
        print("✅ Bit: .gitignore updated")

# =============================
# AI HELPER
# =============================
def ai_suggest(title, context=""):
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"{title}\n{context}",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="low")
            ),
        )
        return r.text.strip()
    except Exception:
        return "⚠ AI suggestion unavailable."

# =============================
# INIT
# =============================
def bit_init():
    ensure_gitignore()
    run(["git", "init"], check=True)
    print("🎉 Bit: Repository initialized")

# =============================
# COMMIT
# =============================
def bit_commit():
    ensure_gitignore()

    staged = run(["git", "diff", "--cached", "--name-only"]).stdout.strip()

    if not staged:
        has_commit = run(["git", "rev-parse", "--verify", "HEAD"]).returncode == 0
        if has_commit:
            print("ℹ Bit: Auto staging changes")
            files = run(["git", "diff", "--name-only"]).stdout.splitlines()
            for f in files:
                if f.startswith("bit-/"):
                    continue
                run(["git", "add", f])

    diff = run(["git", "diff", "--cached"]).stdout.strip()
    if not diff:
        print("⚠ Bit: Nothing to commit")
        return

    print("🤖 Bit: Generating commit message...")
    msg = ai_commit(diff)
    print("✅", msg)
    run(["git", "commit", "-m", msg], check=True)
    print("🎉 Bit: Commit successful")

def ai_commit(diff):
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Generate ONE conventional commit:\n{diff}",
        )
        return r.text.strip().split("\n")[0]
    except Exception:
        return "chore: update code"

# =============================
# PUSH (NEW)
# =============================
def bit_push():
    print("🚀 Bit: Pushing to remote...")
    r = run(["git", "push"])
    if r.returncode == 0:
        print("✅ Bit: Push successful")
    else:
        print(r.stderr or "❌ Bit: Push failed")

# =============================
# CLONE
# =============================
def bit_clone(url, target=None):
    folder = target or url.split("/")[-1].replace(".git", "")
    if os.path.exists(folder) and os.listdir(folder):
        print(f"⚠ Bit: '{folder}' exists, skipping clone")
        return
    run(["git", "clone", url, folder], check=True)
    print("✅ Bit: Clone complete")

# =============================
# PASSTHROUGH
# =============================
def bit_passthrough(args):
    print(f"🔹 Bit → git {' '.join(args)}")
    r = run(["git"] + args)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        print(r.stderr)
    print("💡", ai_suggest("git " + " ".join(args), r.stdout))

# =============================
# CLI
# =============================
def main():
    if len(sys.argv) < 2:
        print("Usage: bit <init|commit|push|clone|git-cmd>")
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "init":
        bit_init()
    elif cmd == "commit":
        bit_commit()
    elif cmd == "push":
        bit_push()
    elif cmd == "clone":
        bit_clone(args[0], args[1] if len(args) > 1 else None)
    else:
        bit_passthrough([cmd] + args)

if __name__ == "__main__":
    main()
