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
import ast

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

# =============================
# GHOST COLORS
# =============================
GHOST = "\033[94m"        # soft blue-violet
GHOST_ACTIVE = "\033[95m" # magenta (active ghost)
GHOST_META = "\033[90m"   # dim gray

def ok(msg): print(f"{GREEN}✔ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}⚠ {msg}{RESET}")
def err(msg): print(f"{RED}✖ {msg}{RESET}")
def info(msg): print(f"{CYAN}{msg}{RESET}")
def meta(msg): print(f"{DIM}{msg}{RESET}")
def ai_msg(msg): print(f"{MAGENTA}{msg}{RESET}")
def ghost(msg): print(f"{GHOST}👻 {msg}{RESET}")
def ghost_active(msg): print(f"{GHOST_ACTIVE}👻 {msg}{RESET}")
def ghost_meta(msg): print(f"{GHOST_META}{msg}{RESET}")

# =============================
# HELP SYSTEM
# =============================

HELP_CONTENT = {
    "init": {
        "desc": "Initialize a new Bit repository",
        "examples": [
            "bit init"
        ],
        "tips": [
            "Creates .gitignore and .bit/config.json",
            "Enables AI features if GEMINI_API_KEY is set"
        ]
    },
    "commit": {
        "desc": "Create commits with AI-generated messages",
        "examples": [
            "bit commit"
        ],
        "tips": [
            "Auto-stages modified files",
            "AI generates conventional commit messages",
            "Shows ghost warning if in ghost mode"
        ]
    },
    "push": {
        "desc": "Push commits to remote repository",
        "examples": [
            "bit push"
        ],
        "tips": [
            "Blocked if on a ghost branch",
            "Use 'bit ghost apply' to materialize ghost first"
        ]
    },
    "clone": {
        "desc": "Clone a repository",
        "examples": [
            "bit clone https://github.com/user/repo.git",
            "bit clone https://github.com/user/repo.git my-folder"
        ],
        "tips": [
            "Auto-detects target folder from URL",
            "Skips if folder already exists"
        ]
    },
    "branch": {
        "desc": "List branches and ghost branches",
        "examples": [
            "bit branch"
        ],
        "tips": [
            "Shows both git branches and ghost branches",
            "Ghost branches marked with 👻",
            "Active ghost branch highlighted in purple"
        ]
    },
    "ghost": {
        "desc": "Ghost branch management",
        "subcommands": {
            "create": {
                "desc": "Create a ghost branch (detached HEAD state)",
                "examples": [
                    "bit ghost create feature-x",
                    "bit ghost create experiment"
                ],
                "tips": [
                    "Detaches HEAD from any branch",
                    "Isolates commits in ghost mode",
                    "Cannot push ghost branches directly"
                ]
            },
            "apply": {
                "desc": "Materialize ghost branch into real branch",
                "examples": [
                    "bit ghost apply feature-x"
                ],
                "tips": [
                    "Creates a real branch from ghost state",
                    "Removes ghost from tracking",
                    "Attaches HEAD to new branch"
                ]
            },
            "discard": {
                "desc": "Discard ghost branch and its commits",
                "examples": [
                    "bit ghost discard feature-x"
                ],
                "tips": [
                    "Removes ghost from tracking",
                    "Commits are lost (not materialized)",
                    "Working files remain unchanged"
                ]
            }
        }
    },
    "merge": {
        "desc": "Merge operations",
        "subcommands": {
            "--preview": {
                "desc": "Preview merge conflicts without modifying working directory",
                "examples": [
                    "bit merge --preview feature-x",
                    "bit merge --preview develop"
                ],
                "tips": [
                    "Uses git merge-tree for virtual merge",
                    "AI provides conflict resolution advice",
                    "No files are changed during preview"
                ]
            }
        },
        "examples": [
            "bit merge --preview <branch-name>",
            "bit merge <branch-name>  # passes through to git"
        ],
        "tips": [
            "Preview mode checks for conflicts safely",
            "Without --preview, passes to git merge"
        ]
    },
    "help": {
        "desc": "Show this help system",
        "examples": [
            "bit help"
        ],
        "tips": [
            "Static help always available",
            "Interactive AI chat if GEMINI_API_KEY is set"
        ]
    }
}

def bit_help():
    """Display comprehensive help system with static help and optional AI chat"""
    
    # Header
    print()
    print(f"{CYAN}╔═══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}║{RESET}                      {CYAN}Bit CLI — Complete Command Reference{RESET}                {CYAN}║{RESET}")
    print(f"{CYAN}╚═══════════════════════════════════════════════════════════════╝{RESET}")
    print()
    print(f"{DIM}Version: {BIT_VERSION} | AI Powered: {'✅' if client else '❌'}{RESET}")
    print()
    
    # Print commands
    for cmd_name, cmd_info in HELP_CONTENT.items():
        if cmd_name == "ghost":
            # Special handling for ghost command
            print(f"{CYAN}📋 {cmd_name}{RESET} — {cmd_info['desc']}")
            print()
            
            # Print ghost subcommands
            for sub_name, sub_info in cmd_info.get("subcommands", {}).items():
                print(f"  {MAGENTA}  {sub_name}{RESET} — {sub_info['desc']}")
                print()
                
                # Print examples
                if "examples" in sub_info:
                    print(f"  {YELLOW}  💡 Examples:{RESET}")
                    for ex in sub_info["examples"]:
                        print(f"  {YELLOW}    {ex}{RESET}")
                    print()
                
                # Print tips
                if "tips" in sub_info:
                    for tip in sub_info["tips"]:
                        print(f"  {DIM}    💡 {tip}{RESET}")
                    print()
            
        elif cmd_name == "merge":
            # Special handling for merge command
            print(f"{CYAN}📋 {cmd_name}{RESET} — {cmd_info['desc']}")
            print()
            
            # Print merge subcommands
            for sub_name, sub_info in cmd_info.get("subcommands", {}).items():
                print(f"  {MAGENTA}  {sub_name}{RESET} — {sub_info['desc']}")
                print()
                
                # Print examples
                if "examples" in sub_info:
                    print(f"  {YELLOW}  💡 Examples:{RESET}")
                    for ex in sub_info["examples"]:
                        print(f"  {YELLOW}    {ex}{RESET}")
                    print()
                
                # Print tips
                if "tips" in sub_info:
                    for tip in sub_info["tips"]:
                        print(f"  {DIM}    💡 {tip}{RESET}")
                    print()
            
            # Print general examples for merge
            if "examples" in cmd_info:
                print(f"  {YELLOW}  💡 General Examples:{RESET}")
                for ex in cmd_info["examples"]:
                    print(f"  {YELLOW}    {ex}{RESET}")
                print()
            
            # Print general tips for merge
            if "tips" in cmd_info:
                for tip in cmd_info["tips"]:
                    print(f"  {DIM}    💡 {tip}{RESET}")
                print()
                
        else:
            # Regular commands
            print(f"{CYAN}📋 {cmd_name}{RESET} — {cmd_info['desc']}")
            print()
            
            # Print examples
            if "examples" in cmd_info:
                print(f"{YELLOW}  💡 Examples:{RESET}")
                for ex in cmd_info["examples"]:
                    print(f"{YELLOW}    {ex}{RESET}")
                print()
            
            # Print tips
            if "tips" in cmd_info:
                for tip in cmd_info["tips"]:
                    print(f"{DIM}  💡 {tip}{RESET}")
                print()
        
        print(f"{DIM}{'─' * 60}{RESET}")
        print()
    
    # Git passthrough info
    print(f"{CYAN}📋 git-cmd{RESET} — Pass through any git command")
    print()
    print(f"{YELLOW}  💡 Examples:{RESET}")
    print(f"{YELLOW}    bit status{RESET}")
    print(f"{YELLOW}    bit log --oneline{RESET}")
    print(f"{YELLOW}    bit diff{RESET}")
    print()
    print(f"{DIM}{'─' * 60}{RESET}")
    print()
    
    # Interactive AI Chat
    if client:
        print(f"{MAGENTA}╔═══════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{MAGENTA}║{RESET}                     {MAGENTA}Interactive AI Help Available{RESET}                   {MAGENTA}║{RESET}")
        print(f"{MAGENTA}╚═══════════════════════════════════════════════════════════════╝{RESET}")
        print()
        print(f"{CYAN}Type your questions about Bit commands to chat with AI.{RESET}")
        print(f"{CYAN}Type {YELLOW}'exit'{CYAN} or press Ctrl+C to leave the chat.{RESET}")
        print()
        
        # Interactive loop - only if running in a terminal
        if sys.stdin.isatty():
            try:
                while True:
                    try:
                        user_input = input(f"{MAGENTA}Ask Bit > {RESET}")
                    except EOFError:
                        # stdin closed - exit gracefully
                        break
                    
                    if user_input.strip().lower() in ['exit', 'quit', 'q']:
                        print(f"{CYAN}👋 Goodbye!{RESET}")
                        break
                    
                    if not user_input.strip():
                        continue
                    
                    # Get AI response
                    spinner = Spinner([
                        "Thinking",
                        "Reading your question",
                        "Formulating answer"
                    ])
                    spinner.start()
                    
                    try:
                        prompt = f"""
You are a helpful assistant for the CLI tool version {BIT_VERSION}.

Commands available: {', '.join(HELP_CONTENT.keys())}

Special features:
- Ghost branches: create isolated, detach HEAD state for experimentation
- Merge preview: preview conflicts without modifying files
- AI-powered commit messages and advice

User question: {user_input}

Provide a clear, concise answer. Include examples when relevant. Be specific about command syntax.
"""
                        r = client.models.generate_content(
                            model="gemini-3-flash-preview",
                            contents=prompt,
                        )
                        spinner.stop()
                        
                        if r.text:
                            print(f"{GREEN}✅{RESET}")
                            print()
                            print(r.text.strip())
                            print()
                        else:
                            spinner.stop()
                            warn("No response from AI")
                            
                    except Exception as e:
                        spinner.stop()
                        err(f"Error: {str(e)}")
                        warn("Falling back to static help system above")
                        print()
                        
            except KeyboardInterrupt:
                print(f"\n{CYAN}👋 Goodbye!{RESET}")
                print()
        else:
            # Non-interactive mode (no TTY)
            print(f"{DIM}Interactive chat available in terminal mode.{RESET}")
            print(f"{DIM}Run 'bit help' from a terminal to chat with AI.{RESET}")
            print()
    else:
        print(f"{CYAN}🤖 AI Help Not Available{RESET}")
        print(f"{DIM}Set GEMINI_API_KEY in .env to enable interactive help.{RESET}")
        print()
    
    print(f"{CYAN}╔═══════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}║{RESET}                    {CYAN}For more info, visit the project repo{RESET}                 {CYAN}║{RESET}")
    print(f"{CYAN}╚═══════════════════════════════════════════════════════════════╝{RESET}")
    print()

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

def ai_merge_advice(merge_output):
    """Get AI advice about merge conflicts from Gemini"""
    if not client:
        return None
    
    try:
        prompt = f"""
Git merge output showing conflicts:
{merge_output}

Explain in 2-3 sentences:
1. Why this conflict is happening
2. What the developer should do (rebase, manual resolve, etc.)
Be concise and actionable.
"""
        r = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
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

def show_ghost_warning():
    """Display a warning banner when user is in ghost mode"""
    active = get_active_ghost()
    if active:
        ghost_active(f"Active Ghost: {active} (commits are isolated)")

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
    
    # Show ghost warning if in ghost mode
    show_ghost_warning()

    staged = run(["git", "diff", "--cached", "--name-only"]).stdout.strip()

    if not staged:
        meta("Auto-staging modified files")
        for f in run(["git", "diff", "--name-only"]).stdout.splitlines():
            if not f.startswith("bit-/"):
                run(["git", "add", f])

    track_symbol_changes()

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
        msg = "chore: update code and new feature enabled"

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
    
    ghost_active(f"Ghost branch '{name}' created")
    ghost("You are now in Ghost Mode (detached HEAD)")
    ghost_meta(f"Base commit → {base_commit[:8]}")

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
    
    ok(f"Ghost '{name}' materialized as real branch")
    ghost_meta("Ghost state cleared • HEAD attached")

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
    
    ghost(f"Ghost '{name}' discarded")
    ghost_meta("Commits removed • Working files untouched")

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
            marker = f"{GHOST_ACTIVE}👻 *{RESET}" if name == active else f"{GHOST}👻{RESET}"
            base = ghosts[name].get("base_commit", "")[:8]
            created = ghosts[name].get("created_at", "")
            print(f"  {marker} {GHOST}{name}{RESET} (base: {DIM}{base}{RESET})")
            if created:
                ghost_meta(f"     created: {created}")

# =============================
# MERGE PREVIEW
# =============================
def bit_merge_preview(branch_name):
    """Preview merge conflicts without modifying working directory"""
    if not branch_name:
        err("Usage: bit merge --preview <branch-name>")
        return
    
    # Check if we're on a ghost branch
    active_ghost = get_active_ghost()
    if active_ghost:
        warn(f"⚠ Previewing merge from Ghost Branch ({active_ghost})")
        ghost_meta("This is a detached HEAD state - preview may be unusual")
        print()
    
    # Validate branch exists
    branch_check = run(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"])
    if branch_check.returncode != 0:
        err(f"Branch '{branch_name}' not found")
        info("Available branches:")
        r = run(["git", "branch"])
        print(r.stdout)
        return
    
    # Get current commit
    current_commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    if not current_commit:
        err("Cannot get current commit. Are you in a git repository?")
        return
    
    # Get the target branch's commit
    target_commit = run(["git", "rev-parse", branch_name]).stdout.strip()
    if not target_commit:
        err(f"Cannot get commit for branch '{branch_name}'")
        return
    
    meta(f"Analyzing merge preview: {branch_name} → current")
    meta(f"Your commit: {current_commit[:8]}")
    meta(f"Target commit: {target_commit[:8]}")
    print()
    
    # Find merge base
    merge_base = run(["git", "merge-base", current_commit, target_commit]).stdout.strip()
    if not merge_base:
        err("Cannot find merge base")
        return
    
    # Perform virtual merge using git merge-tree
    # This creates the merge in memory without touching working directory
    result = run(["git", "merge-tree", "--write-tree", current_commit, target_commit])
    
    if result.returncode == 0:
        # Clean merge
        ok("✓ Clean merge! No conflicts expected.")
        meta(f"Merge base: {merge_base[:8]}")
        info("You can safely merge: ")
        print(f"   git merge {branch_name}")
    else:
        # Conflicts detected
        err("⚠ Merge conflicts detected!")
        print()
        
        # Parse conflict markers from merge-tree output
        output = result.stdout + result.stderr
        conflicts = []
        
        for line in output.split('\n'):
            if '<<<<<<<' in line:
                conflicts.append("  " + line.strip())
        
        if conflicts:
            warn("Conflicting files:")
            for conflict in conflicts:
                print(conflict)
            print()
        
        # Get AI advice if available
        spinner = Spinner([
            "Analyzing conflicts",
            "Generating advice"
        ])
        spinner.start()
        advice = ai_merge_advice(output)
        spinner.stop()
        
        if advice:
            ai_msg("AI Merge Advice:")
            print(f"  {advice}")
            print()
        else:
            meta("AI unavailable - try: git merge {branch_name} --no-commit to see full conflicts")
            print()
        
        info("To preview with real conflicts (temp files):")
        print(f"   git merge {branch_name} --no-commit --no-ff")
        print()
        info("Then resolve conflicts or abort with: git merge --abort")

# =============================
# SYMBOL TRACKING
# =============================
DB_DIR = os.path.join(BIT_DIR, "db")
ACTIVITY_FILE = os.path.join(DB_DIR, "activity.json")

def ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    if not os.path.exists(ACTIVITY_FILE):
        with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)

def load_activity():
    ensure_db()
    try:
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_activity(data):
    ensure_db()
    with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def parse_symbols_from_code(code):
    """Return list of function and class names in a Python code string."""
    symbols = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(node.name)
            elif isinstance(node, ast.ClassDef):
                symbols.append(node.name)
    except Exception:
        pass
    return symbols

def get_staged_file_content(file_path):
    """Return the staged version of a file from git index."""
    r = run(["git", "show", f":{file_path}"])
    if r.returncode == 0:
        return r.stdout
    return ""

def track_symbol_changes():
    """
    Track symbols (functions/classes) modified in staged Python files.
    Save activity to .bit/db/activity.json
    """
    staged_files = run(["git", "diff", "--cached", "--name-only"]).stdout.splitlines()
    activity = load_activity()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    for f in staged_files:
        if not f.endswith(".py"):  # Only Python for now
            continue

        new_code = get_staged_file_content(f)
        old_code_result = run(["git", "show", f"HEAD:{f}"])
        old_code = old_code_result.stdout if old_code_result.returncode == 0 else ""

        old_symbols = set(parse_symbols_from_code(old_code))
        new_symbols = set(parse_symbols_from_code(new_code))
        changed_symbols = list(new_symbols - old_symbols)  # New/modified functions

        if changed_symbols:
            activity[timestamp] = {
                "file": f,
                "symbols_changed": changed_symbols
            }
            ghost_meta(f"Tracked symbols in {f}: {', '.join(changed_symbols)}")

    save_activity(activity)

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
        print("Usage: bit <init|commit|push|clone|branch|ghost|merge|help|git-cmd>")
        print()
        info("Merge preview: bit merge --preview <branch-name>")
        info("Help system: bit help")
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
    elif cmd == "merge":
        # Check for --preview flag
        if args and args[0] == "--preview":
            branch_name = args[1] if len(args) > 1 else None
            bit_merge_preview(branch_name)
        else:
            # Pass through to git merge
            bit_passthrough([cmd] + args)
    elif cmd == "help":
        bit_help()
    else:
        bit_passthrough([cmd] + args)
    
    # Log this command to history
    try:
        log_history(cmd, args)
    except Exception:
        pass  # Don't break functionality if logging fails

if __name__ == "__main__":
    main()
