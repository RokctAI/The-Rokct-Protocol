# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
_trace_id_propagation = {"X-Trace-Id": "compliance"}
import requests
import json
import argparse
import sys


def parse_env_content(content):
    """
    Parses shell-style exports (export KEY=<value>) and returns True
    only if a key was successfully found and set.
    Priority: JULES_API_KEY then AGENT_API_KEY.
    """
    found = False

    # --- Pass 1: JULES_API_KEY ---
    for line in content.splitlines():
        if "JULES_API_KEY=" in line:
            val = line.replace("export ", "").strip().split("=", 1)[1].strip("'\" ")
            os.environ["JULES_API_KEY"] = val
            found = True
            break

    # --- Pass 2: AGENT_API_KEY (only if JULES_API_KEY not found) ---
    if not found:
        for line in content.splitlines():
            if "AGENT_API_KEY=" in line:
                val = line.replace("export ", "").strip().split("=", 1)[1].strip("'\" ")
                os.environ["AGENT_API_KEY"] = val
                found = True
                break

    return found


def load_monorepo_env(custom_path=None):
    """
    Recovers the JULES_API_KEY from the central Monorepo.
    Priority 1: Remote Vault (GitHub API via MONOREPO_PAT)
    Priority 2: Local Hunting (Monorepo sibling folder)
    Returns True only if parse_env_content() successfully found and set a key.
    """
    # --- 1. REMOTE CI MODE (GitHub API) ---
    pat = os.environ.get("MONOREPO_PAT")
    if pat:
        url = "https://api.github.com/repos/RokctAI/monorepo/contents/.env/production.env"
        headers = {
            "Authorization": f"token {pat}",
            "Accept": "application/vnd.github.v3.raw"
        }
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"[CI Debug] MONOREPO_PAT detected. Dialing home to: {url}")

        try:
            # We fetch as RAW plain text
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                if parse_env_content(resp.text):
                    return True
        except Exception as e:
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"[CI Debug] Remote Vault resolution failed: {e}")

    # --- 2. LOCAL FALLBACK MODE ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_dir))))

    env_paths = []
    if custom_path:
        env_paths.append(custom_path)
    env_paths.append(os.path.join(workspace_root, "Monorepo", ".env", "production.env"))
    env_paths.append(os.path.join(workspace_root, ".env", "production.env"))

    for path in env_paths:
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"[CI Debug] Checking local env path: {path}")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if parse_env_content(f.read()):
                        return True
            except OSError as e:
                if os.environ.get("GITHUB_ACTIONS"):
                    print(f"[CI Debug] Local env resolution failed ({path}): {e}")
    return False


BASE_URL = "https://jules.googleapis.com/v1alpha"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class AgentCLI:
    """CLI client for the Jules Agent API."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key
        }

    def create_session(self, prompt, source_repo,
                       automation_mode="AUTO_CREATE_PR",
                       title=None, branch="main", require_approval=False):
        """Create a new agent session on the given source repo and branch."""
        url = f"{BASE_URL}/sessions"
        payload = {
            "prompt": prompt,
            "sourceContext": {
                "source": source_repo,
                "githubRepoContext": {
                    "startingBranch": branch
                }
            },
            "automationMode": automation_mode,
            "requirePlanApproval": require_approval
        }
        if title:
            payload["title"] = title

        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_session(self, session_id):
        """Fetch the current state of an existing session."""
        url = f"{BASE_URL}/sessions/{session_id}"
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def send_message(self, session_id, message):
        """Send an additional message to an existing session."""
        url = f"{BASE_URL}/sessions/{session_id}:sendMessage"
        payload = {"prompt": message}
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def approve_plan(self, session_id):
        """Approve the plan generated by the agent for a session."""
        url = f"{BASE_URL}/sessions/{session_id}:approvePlan"
        response = requests.post(url, headers=self.headers, json={}, timeout=30)
        response.raise_for_status()
        return {"status": "success", "message": "Plan approved."}

    def delete_session(self, session_id):
        """Delete / cancel a running session."""
        url = f"{BASE_URL}/sessions/{session_id}"
        response = requests.delete(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return {"status": "success", "message": f"Session {session_id} deleted."}

    def list_sessions(self):
        """List all sessions accessible with the current API key."""
        url = f"{BASE_URL}/sessions"
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json().get("sessions", [])

    # === Groq Methods ===
    def call_groq(self, prompt, system_prompt=None, model="llama-3.3-70b-versatile"):
        """Call Groq API directly for chat completions."""
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2
        }

        response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content")


def main():
    """Entry point — resolves the API key and dispatches the requested command."""
    # --- Priority: Remote Vault > Local Env > Local File ---
    parser = argparse.ArgumentParser(
        description="Delegate tasks to an AI Agent (Remote Vault priority)."
    )
    parser.add_argument("--api-key", help="Explicit API key (overrides AGENT_API_KEY / JULES_API_KEY)")
    parser.add_argument("--env-file", help="Local env file (final fallback)")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # --- Create Session ---
    create_parser = subparsers.add_parser("create", help="Create a new Agent session")
    create_parser.add_argument("--prompt", required=True, help="User prompt/task for the Agent")
    create_parser.add_argument("--repo", required=True, help="Full source name (e.g., 'sources/github/RokctAI/factory')")
    create_parser.add_argument("--branch", default="main", help="Starting branch (default: main)")
    create_parser.add_argument("--title", help="Session title")
    create_parser.add_argument("--require-approval", action="store_true", help="Require plan approval before execution (default: False)")
    create_parser.add_argument("--automation-mode", default="AUTO_CREATE_PR", help="Automation mode (default: AUTO_CREATE_PR)")

    # --- Get Session ---
    status_parser = subparsers.add_parser("status", help="Get session status")
    status_parser.add_argument("--id", required=True, help="Session ID")

    # --- Send Message ---
    msg_parser = subparsers.add_parser("query", help="Send a message to an active session")
    msg_parser.add_argument("--id", required=True, help="Session ID")
    msg_parser.add_argument("--message", required=True, help="Message content")

    # --- Approve Plan ---
    approve_parser = subparsers.add_parser("approve", help="Approve the proposed plan")
    approve_parser.add_argument("--id", required=True, help="Session ID")

    # --- Delete Session ---
    delete_parser = subparsers.add_parser("delete", help="Delete an Agent session")
    delete_parser.add_argument("--id", required=True, help="Session ID")

    # --- List Sessions ---
    subparsers.add_parser("list", help="List all Agent sessions")

    # --- Groq Chat ---
    groq_parser = subparsers.add_parser("groq", help="Call Groq chat completion")
    groq_parser.add_argument("--prompt", required=True, help="User prompt")
    groq_parser.add_argument("--system", help="System prompt")
    groq_parser.add_argument("--model", default="llama-3.3-70b-versatile", help="Groq model")

    args = parser.parse_args()

    # Priority 1: Remote Vault (via MONOREPO_PAT)
    if os.environ.get("MONOREPO_PAT"):
        load_monorepo_env(args.env_file)

    # Priority 2: local fallback (no MONOREPO_PAT or vault returned nothing)
    if not os.environ.get("JULES_API_KEY") and not os.environ.get("AGENT_API_KEY"):
        load_monorepo_env(args.env_file)

    # Resolve key
    api_key = args.api_key or os.environ.get("JULES_API_KEY") or os.environ.get("AGENT_API_KEY")

    if not api_key:
        print("Error: Agent API Key is missing. Provide via --api-key, AGENT_API_KEY, or JULES_API_KEY env var.")
        return 1

    cli = AgentCLI(api_key)

    try:
        if args.command == "create":
            repo = args.repo
            if not repo.startswith("sources/"):
                repo = f"sources/github/{repo}"
            result = cli.create_session(
                args.prompt, repo,
                title=args.title, branch=args.branch,
                require_approval=args.require_approval,
                automation_mode=args.automation_mode
            )
            print(json.dumps(result, indent=2))
        elif args.command == "status":
            result = cli.get_session(args.id)
            print(json.dumps(result, indent=2))
        elif args.command == "query":
            result = cli.send_message(args.id, args.message)
            print(json.dumps(result, indent=2))
        elif args.command == "approve":
            result = cli.approve_plan(args.id)
            print(json.dumps(result, indent=2))
        elif args.command == "delete":
            result = cli.delete_session(args.id)
            print(json.dumps(result, indent=2))
        elif args.command == "list":
            result = cli.list_sessions()
            print(json.dumps(result, indent=2))
        elif args.command == "groq":
            result = cli.call_groq(args.prompt, args.system, args.model)
            if result:
                print(result)
            else:
                return 1
        else:
            parser.print_help()
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f"Details: {json.dumps(e.response.json(), indent=2)}")
            except:
                print(f"Details: {e.response.text}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
