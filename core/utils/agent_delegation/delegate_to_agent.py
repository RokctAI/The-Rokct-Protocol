# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD

import os

_trace_id_propagation = {"X-Trace-Id": "compliance"}
import requests
import json
import argparse
import sys


def parse_env_content(content):
    """
    Parses shell-style exports (export KEY=<value>) and returns True
    if GROQ_API_KEY was found and set.
    """
    for line in content.splitlines():
        if "GROQ_API_KEY=" in line:
            val = line.replace("export ", "").strip().split("=", 1)[1].strip("'\" ")
            os.environ["GROQ_API_KEY"] = val
            return True
    return False


def load_monorepo_env(custom_path=None):
    """
    Recovers the GROQ_API_KEY from the central Monorepo.
    Priority 1: Remote Vault (GitHub API via MONOREPO_PAT)
    Priority 2: Local Hunting (Monorepo sibling folder)
    Returns True only if parse_env_content() successfully found and set a key.
    """
    # --- 1. REMOTE CI MODE (GitHub API) ---
    pat = os.environ.get("MONOREPO_PAT")
    if pat:
        url = (
            "https://api.github.com/repos/RokctAI/monorepo/contents/.env/production.env"
        )
        headers = {
            "Authorization": f"token {pat}",
            "Accept": "application/vnd.github.v3.raw",
        }
        # Callers capture stdout (and often stderr) as the response payload
        # and can commit it into job cards, so never print URLs, tokens,
        # headers, or payload content here — non-sensitive metadata only,
        # and only to stderr.
        if os.environ.get("GITHUB_ACTIONS"):
            print(
                "[CI Debug] MONOREPO_PAT detected; resolving env via remote vault.",
                file=sys.stderr,
            )

        try:
            # We fetch as RAW plain text
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                if parse_env_content(resp.text):
                    if os.environ.get("GITHUB_ACTIONS"):
                        print(
                            "[CI Debug] Env resolution via remote vault: ok",
                            file=sys.stderr,
                        )
                    return True
        except Exception as e:
            # Exception text can embed the request URL — log the class only.
            if os.environ.get("GITHUB_ACTIONS"):
                print(
                    f"[CI Debug] Remote vault resolution failed: {type(e).__name__}",
                    file=sys.stderr,
                )

    # --- 2. LOCAL FALLBACK MODE ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    )

    env_paths = []
    if custom_path:
        env_paths.append(custom_path)
    env_paths.append(os.path.join(workspace_root, "Monorepo", ".env", "production.env"))
    env_paths.append(os.path.join(workspace_root, ".env", "production.env"))

    if os.environ.get("GITHUB_ACTIONS"):
        print(
            "[CI Debug] Falling back to local env resolution.",
            file=sys.stderr,
        )
    for path in env_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if parse_env_content(f.read()):
                        return True
            except OSError as e:
                if os.environ.get("GITHUB_ACTIONS"):
                    print(
                        f"[CI Debug] Local env resolution failed: {type(e).__name__}",
                        file=sys.stderr,
                    )
    return False


USAGE_LOG = os.path.join(".rokct", "agent", "log", "api_usage.jsonl")


def log_api_usage(record):
    """Append one JSON line of API usage to a committed, queryable log.
    Best-effort and silent on stdout — callers capture stdout as the
    response payload, so this must never print."""
    try:
        record["ts"] = (
            __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        os.makedirs(os.path.dirname(USAGE_LOG), exist_ok=True)
        with open(USAGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + chr(10))
    except Exception:
        pass


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class AgentCLI:
    """CLI client for the Groq chat completions API."""

    # === Groq Methods ===
    def call_groq(self, prompt, system_prompt=None, model="llama-3.3-70b-versatile"):
        """Call Groq API directly for chat completions."""
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model, "messages": messages, "temperature": 0.2}

        response = requests.post(GROQ_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage", {})
        log_api_usage(
            {
                "api": "groq",
                "kind": "chat",
                "model": model,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        )
        return data.get("choices", [{}])[0].get("message", {}).get("content")


def main():
    """Entry point: resolves the Groq key and dispatches the requested command."""
    parser = argparse.ArgumentParser(
        description="Delegate tasks to Groq (Remote Vault priority)."
    )
    parser.add_argument("--env-file", help="Local env file (final fallback)")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # --- Groq Chat ---
    groq_parser = subparsers.add_parser("groq", help="Call Groq chat completion")
    groq_parser.add_argument("--prompt", required=True, help="User prompt")
    groq_parser.add_argument("--system", help="System prompt")
    groq_parser.add_argument(
        "--model", default="llama-3.3-70b-versatile", help="Groq model"
    )

    args = parser.parse_args()

    # Priority: environment, then remote vault (MONOREPO_PAT), then local file.
    if not os.environ.get("GROQ_API_KEY"):
        load_monorepo_env(args.env_file)

    cli = AgentCLI()

    try:
        if args.command == "groq":
            result = cli.call_groq(args.prompt, args.system, args.model)
            if result:
                print(result)
            else:
                return 1
        else:
            parser.print_help()
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                print(f"Details: {json.dumps(e.response.json(), indent=2)}")
            except Exception:
                print(f"Details: {e.response.text}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
