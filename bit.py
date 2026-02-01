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
        return {"active": None, "branches": {}}
    try:
        with open(GHOST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active": None, "branches": {}}

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
    # SAFETY CHECK: Block push while on ghost branch
    active_ghost = get_active_ghost()
    if active_ghost:
        warn(f"⚠ You are on a Ghost Branch ({active_ghost})")
        err("Ghost branches cannot be pushed.")
        print()
        info("Use: bit ghost apply <ghost-name> to materialize it first.")
        return
    
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
# GHOST BRANCH COMMANDS
# =============================
def bit_ghost_create(name):
    if not name:
        err("Ghost name missing")
        return
    
    # Check for existing ghost
    data = load_ghosts()
    if name in data["branches"]:
        warn(f"Ghost branch 👻 {name} already exists")
        return
    
    # STEP A: Get current commit
    base_commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    if not base_commit:
        err("Cannot get current commit. Are you in a git repository?")
        return
    
    # STEP B: Save ghost metadata with formatted timestamp
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    data["branches"][name] = {
        "base_commit": base_commit,
        "created_at": created_at
    }
    data["active"] = name
    save_ghosts(data)
    
    # STEP C: Detach HEAD (the magic)
    run(["git", "checkout", "--detach"], check=True)
    
    ok(f"Ghost branch 👻 {name} created")
    info("You're now in Ghost Mode - make commits freely!")
    meta(f"Base commit: {base_commit[:8]}")

def bit_ghost_apply(name):
    if not name:
        err("Ghost name missing")
        return
    
    data = load_ghosts()
    
    # Check if ghost exists
    if name not in data["branches"]:
        err(f"Ghost branch 👻 {name} not found")
        return
    
    # STEP A: Create real branch from current state
    run(["git", "checkout", "-b", name], check=True)
    
    # STEP B: Update ghosts.json (remove ghost and mark as applied)
    del data["branches"][name]
    data["active"] = None
    save_ghosts(data)
    
    ok(f"Ghost 👻 {name} materialized as real branch")
    info("You can now push safely")

def bit_ghost_discard(name):
    if not name:
        err("Ghost name missing")
        return
    
    data = load_ghosts()
    
    # Check if ghost exists
    if name not in data["branches"]:
        err(f"Ghost branch 👻 {name} not found")
        return
    
    # Switch back to main (or another branch)
    run(["git", "checkout", "main"], check=True)
    
    # Remove the ghost
    del data["branches"][name]
    if data["active"] == name:
        data["active"] = None
    save_ghosts(data)
    
    ok(f"Ghost 👻 {name} discarded")
    info("Clean exit - no repo pollution")

def ghost_handler(args):
    if not args or len(args) < 1:
        err("Usage: bit ghost <create|apply|discard> <name>")
        return
    
    subcommand = args[0]
    name = args[1] if len(args) > 1 else None
    
    if subcommand == "create":
        bit_ghost_create(name)
    elif subcommand == "apply":
        bit_ghost_apply(name)
    elif subcommand == "discard":
        bit_ghost_discard(name)
    else:
        err(f"Unknown ghost command: {subcommand}")
        info("Available: create, apply, discard")

# =============================
# BRANCH (with ghosts)
# =============================
def bit_branch():
    # Show git branch status
    r = run(["git", "branch"])
    print(r.stdout)
    
    # Check if we're in detached HEAD state (ghost mode)
    status = run(["git", "status", "--short", "--branch"]).stdout.strip()
    if "HEAD detached" in status or "No commits yet" in status:
        active_ghost = get_active_ghost()
        if active_ghost:
            meta(f"(HEAD detached at {run(['git', 'rev-parse', '--short', 'HEAD']).stdout.strip()})")

    # Show ghost branches
    data = load_ghosts()
    ghosts = data.get("branches", {})
    active = data.get("active")

    if ghosts:
        print()
        info("Ghost branches:")
        for name in ghosts:
            marker = "👻 *" if name == active else "👻"
            base = ghosts[name].get("base_commit", "")[:8]
            created = ghosts[name].get("created_at", "")
            print(f"  {marker} {name} (base: {base})")
            if created:
                meta(f"     created: {created}")

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
        print("Usage: bit <init|commit|push|clone|branch|ghost|git-cmd>")
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
    elif cmd == "branch":
        bit_branch()
    elif cmd == "ghost":
        ghost_handler(args)
    else:
        bit_passthrough([cmd] + args)
    
    # Log this command to history
    try:
        log_history(cmd, args)
    except Exception:
        pass  # Don't break functionality if logging fails

if __name__ == "__main__":
    main()
