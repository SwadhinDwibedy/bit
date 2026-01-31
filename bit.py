#!/usr/bin/env python
BIT_VERSION = "2.0.0"
import subprocess
import sys
import os
import io
import threading
import time
import random
import json
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
# COLORS (restrained)
# =============================
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"      # primary accent
MAGENTA = "\033[95m"   # AI only
DIM = "\033[2m"

def ok(msg): print(f"{GREEN}✔ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}⚠ {msg}{RESET}")
def err(msg): print(f"{RED}✖ {msg}{RESET}")
def info(msg): print(f"{CYAN}{msg}{RESET}")
def meta(msg): print(f"{DIM}{msg}{RESET}")
def ai_msg(msg): print(f"{MAGENTA}{msg}{RESET}")

# =============================
# SPINNER (alive, not robotic)
# =============================
class Spinner:
    def __init__(self, steps):
        self.steps = steps
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin, daemon=True)
        self.thread.start()

    def spin(self):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇"
        i = 0
        step_index = 0
        last_switch = time.time()

        while self.running:
            if time.time() - last_switch > 1.2 and step_index < len(self.steps) - 1:
                step_index += 1
                last_switch = time.time()

            print(
                f"\r{MAGENTA}{self.steps[step_index]} {frames[i % len(frames)]}{RESET}",
                end="",
                flush=True
            )
            time.sleep(0.1)
            i += 1

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print("\r" + " " * 60 + "\r", end="", flush=True)

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
# GITIGNORE AUTO HEAL
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
        ok(".gitignore updated")

# =============================
# AI HELPERS
# =============================
def ai_commit(diff):
    if not client:
        return None

    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Generate ONE conventional commit:\n{diff}",
        )
        return r.text.strip().split("\n")[0]
    except Exception:
        return None

def ai_suggest(cmd, output):
    if not client:
        return None
    try:
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Command: {cmd}\nOutput:\n{output}\nGive short advice.",
        )
        return r.text.strip()
    except Exception:
        return None

# =============================
# GHOST BRANCH HELPERS
# =============================
BIT_DIR = ".bit"
GHOST_FILE = os.path.join(BIT_DIR, "ghosts.json")
CONFIG_FILE = os.path.join(BIT_DIR, "config.json")
LOG_FILE = os.path.join(BIT_DIR, "logs/history.log")

def load_ghosts():
    if not os.path.exists(GHOST_FILE):
        return {"active": None, "ghosts": {}}
    try:
        with open(GHOST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active": None, "ghosts": {}}

def save_ghosts(data):
    os.makedirs(BIT_DIR, exist_ok=True)
    with open(GHOST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_active_ghost():
    data = load_ghosts()
    return data.get("active")

# =============================
# CONFIG
# =============================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_config(data):
    os.makedirs(BIT_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def ensure_config():
    os.makedirs(BIT_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        # Create initial config
        data = {
            "version": BIT_VERSION,
            "initialized_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ghost_enabled": False,
            "project_root": os.path.abspath(".")
        }
        save_config(data)
    else:
        # Update version and project root on re-init
        data = load_config()
        data["version"] = BIT_VERSION
        if "project_root" not in data:
            data["project_root"] = os.path.abspath(".")
        if "initialized_at" not in data:
            data["initialized_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if "ghost_enabled" not in data:
            data["ghost_enabled"] = False
        save_config(data)

# =============================
# HISTORY LOGGING
# =============================
def log_history(command, args=[]):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    args_str = " ".join(args) if args else ""
    entry = f"[{timestamp}] bit {command} {args_str}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

# =============================
# INIT
# =============================
def bit_init():
    ensure_gitignore()
    ensure_config()
    run(["git", "init"], check=True)
    ok("Repository initialized")
    # Display config info
    config = load_config()
    meta(f"Bit v{config.get('version', 'unknown')} initialized at {config.get('initialized_at', 'unknown')}")

# =============================
# COMMIT
# =============================
def bit_commit():
    ensure_gitignore()

    staged = run(["git", "diff", "--cached", "--name-only"]).stdout.strip()

    if not staged:
        meta("Auto-staging modified files")
        for f in run(["git", "diff", "--name-only"]).stdout.splitlines():
            if not f.startswith("bit-/"):
                run(["git", "add", f])

    diff = run(["git", "diff", "--cached"]).stdout.strip()
    if not diff:
        warn("Nothing to commit")
        return

    spinner = Spinner([
        "Analyzing changes",
        "Understanding intent",
        "Crafting commit message",
        "Almost done"
    ])
    spinner.start()
    msg = ai_commit(diff)
    spinner.stop()

    if msg:
        ai_msg("AI assisted ✓")
    else:
        ai_msg("AI skipped ✓")
        msg = "chore: update code"

    info(f"Commit → {msg}")
    time.sleep(0.3)
    run(["git", "commit", "-m", msg], check=True)
    ok("Commit created")

# =============================
# PUSH
# =============================
PUSH_MESSAGES = [
    "All set. Code is safely in the cloud ☁️",
    "Push complete. Ship it 🚢",
    "Sent it. No turning back now.",
    "Pushed clean. No drama.",
    "Main branch updated. Respectfully.",
    "Synced."
]

def bit_push():
    meta("Pushing to remote…")
    r = run(["git", "push"])
    time.sleep(0.4)

    if r.returncode == 0:
        ok(random.choice(PUSH_MESSAGES))
    else:
        warn(r.stderr.strip())

# =============================
# CLONE
# =============================
def bit_clone(url, target=None):
    folder = target or url.split("/")[-1].replace(".git", "")
    if os.path.exists(folder) and os.listdir(folder):
        warn(f"'{folder}' already exists — skipping clone")
        return
    run(["git", "clone", url, folder], check=True)
    ok("Clone complete")

# =============================
# GHOST CHECKOUT
# =============================
def bit_checkout_ghost(args):
    if len(args) < 2:
        err("Ghost name missing")
        return

    ghost_name = args[1]

    data = load_ghosts()

    if ghost_name not in data["ghosts"]:
        # create new ghost
        base = run(["git", "rev-parse", "HEAD"]).stdout.strip()
        data["ghosts"][ghost_name] = {
            "base": base,
            "created_at": time.time()
        }
        info(f"Created ghost branch 👻 {ghost_name}")

    # detach HEAD
    run(["git", "checkout", "--detach"], check=True)

    data["active"] = ghost_name
    save_ghosts(data)

    ok(f"Switched to ghost branch 👻 {ghost_name}")

# =============================
# BRANCH (with ghosts)
# =============================
def bit_branch():
    # show normal branches
    r = run(["git", "branch"])
    print(r.stdout)

    # show ghosts
    data = load_ghosts()
    ghosts = data.get("ghosts", {})
    active = data.get("active")

    if ghosts:
        info("Ghost branches:")
        for name in ghosts:
            marker = "👻 *" if name == active else "👻"
            print(f"  {marker} {name}")

# =============================
# PASSTHROUGH
# =============================
def bit_passthrough(args):
    meta(f"➜ git {' '.join(args)}")
    r = run(["git"] + args)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        print(r.stderr)

    suggestion = ai_suggest("git " + " ".join(args), r.stdout)
    if suggestion:
        ai_msg(suggestion)
    else:
        ai_msg("AI skipped ✓")

# =============================
# CLI
# =============================
def main():
    if len(sys.argv) < 2:
        print("Usage: bit <init|commit|push|clone|checkout|branch|git-cmd>")
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
    elif cmd == "checkout" and "--ghost" in args:
        bit_checkout_ghost([cmd] + args)
    elif cmd == "branch":
        bit_branch()
    else:
        bit_passthrough([cmd] + args)
    
    # Log this command to history
    try:
        log_history(cmd, args)
    except Exception:
        pass  # Don't break functionality if logging fails

if __name__ == "__main__":
    main()
