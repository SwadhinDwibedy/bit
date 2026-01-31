#!/usr/bin/env python
import subprocess
import sys
import os
import io
import threading
import time
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
# COLORS
# =============================
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
DIM = "\033[2m"

def ok(msg): print(f"{GREEN}✔ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}⚠ {msg}{RESET}")
def err(msg): print(f"{RED}✖ {msg}{RESET}")
def info(msg): print(f"{CYAN}ℹ {msg}{RESET}")
def ai(msg): print(f"{MAGENTA}💡 {msg}{RESET}")

# =============================
# SPINNER
# =============================
class Spinner:
    def __init__(self, text="Working"):
        self.text = text
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()

    def spin(self):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇"
        i = 0
        while self.running:
            print(f"\r{MAGENTA}{self.text} {frames[i % len(frames)]}{RESET}", end="", flush=True)
            time.sleep(0.1)
            i += 1

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print("\r" + " " * 50 + "\r", end="", flush=True)

# =============================
# ENV + GEMINI
# =============================
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

# =============================
# SAFE SUBPROCESS
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
        ok("Updated .gitignore")

# =============================
# AI HELPER
# =============================
def ai_suggest(title, context=""):
    if not client:
        return "AI disabled (no API key)"

    spinner = Spinner("Bit AI thinking")
    spinner.start()
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"{title}\n{context}",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="low")
            ),
        )
        spinner.stop()
        return r.text.strip()
    except Exception:
        spinner.stop()
        return "AI suggestion unavailable"

# =============================
# INIT
# =============================
def bit_init():
    ensure_gitignore()
    run(["git", "init"], check=True)
    ok("Repository initialized")

# =============================
# COMMIT
# =============================
def bit_commit():
    ensure_gitignore()

    staged = run(["git", "diff", "--cached", "--name-only"]).stdout.strip()

    if not staged:
        info("Auto-staging modified files")
        files = run(["git", "diff", "--name-only"]).stdout.splitlines()
        for f in files:
            if not f.startswith("bit-/"):
                run(["git", "add", f])

    diff = run(["git", "diff", "--cached"]).stdout.strip()
    if not diff:
        warn("Nothing to commit")
        return

    spinner = Spinner("Generating commit message")
    spinner.start()
    msg = ai_commit(diff)
    spinner.stop()

    info(f"Commit message → {msg}")
    run(["git", "commit", "-m", msg], check=True)
    ok("Commit created")

def ai_commit(diff):
    if not client:
        return "chore: update code"
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Generate ONE conventional commit:\n{diff}",
        )
        return r.text.strip().split("\n")[0]
    except Exception:
        return "chore: update code"

# =============================
# PUSH
# =============================
def bit_push():
    info("Pushing to remote")
    r = run(["git", "push"])
    if r.returncode == 0:
        ok("Push successful")
    else:
        warn(r.stderr.strip())

# =============================
# CLONE
# =============================
def bit_clone(url, target=None):
    folder = target or url.split("/")[-1].replace(".git", "")
    if os.path.exists(folder) and os.listdir(folder):
        warn(f"'{folder}' already exists, skipping clone")
        return
    run(["git", "clone", url, folder], check=True)
    ok("Clone complete")

# =============================
# PASSTHROUGH
# =============================
def bit_passthrough(args):
    print(f"{CYAN}➜ git {' '.join(args)}{RESET}")
    r = run(["git"] + args)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        print(r.stderr)
    ai(ai_suggest("git " + " ".join(args), r.stdout))

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
