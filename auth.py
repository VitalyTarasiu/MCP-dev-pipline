"""Interactive credential setup with browser-based SSO for Jira and GitHub."""

from __future__ import annotations

import subprocess
import webbrowser
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"

REQUIRED_KEYS = ("OPENAI_API_KEY", "JIRA_API_TOKEN", "GITHUB_TOKEN")


def read_env() -> dict[str, str]:
    """Read key=value pairs from the .env file."""
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def write_env(values: dict[str, str]) -> None:
    """Write key=value pairs to the .env file."""
    lines = [f"{k}={v}" for k, v in values.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")


def ensure_credentials() -> bool:
    """Check for missing credentials and run interactive setup if needed.

    Returns True when all required credentials are present.
    """
    env = read_env()
    missing = [k for k in REQUIRED_KEYS if not env.get(k)]

    if not missing:
        return True

    print("\n  Missing credentials detected — starting setup...\n")

    if "OPENAI_API_KEY" in missing:
        _setup_openai(env)

    if "JIRA_API_TOKEN" in missing:
        _setup_jira(env)

    if "GITHUB_TOKEN" in missing:
        _setup_github(env)

    write_env(env)
    print(f"\n  Credentials saved to {ENV_FILE}\n")
    return True


# ---- Individual setup helpers ------------------------------------------------


def _setup_openai(env: dict[str, str]) -> None:
    print("=" * 55)
    print("  OPENAI API KEY")
    print("=" * 55)
    print("  Get your key at: https://platform.openai.com/api-keys")
    print()
    key = input("  Paste your OpenAI API key: ").strip()
    env["OPENAI_API_KEY"] = key


def _setup_jira(env: dict[str, str]) -> None:
    print()
    print("=" * 55)
    print("  JIRA API TOKEN  (SSO — browser will open)")
    print("=" * 55)
    print()
    print("  1. Your browser will open the Atlassian token page")
    print("  2. Sign in with SSO if prompted")
    print("  3. Click  'Create API token'")
    print("  4. Name it (e.g. 'MCP Pipeline') and click Create")
    print("  5. Copy the token")
    print()
    input("  Press Enter to open the browser...")
    webbrowser.open("https://id.atlassian.com/manage-profile/security/api-tokens")
    print()
    token = input("  Paste your Jira API token: ").strip()
    env["JIRA_API_TOKEN"] = token


def _setup_github(env: dict[str, str]) -> None:
    print()
    print("=" * 55)
    print("  GITHUB TOKEN  (SSO — browser will open)")
    print("=" * 55)

    # Try the gh CLI first — it already handles SSO via the browser
    token = _try_gh_cli()
    if token:
        print(f"  Found token from GitHub CLI (gh).")
        env["GITHUB_TOKEN"] = token
        return

    print()
    print("  1. Your browser will open the GitHub token page")
    print("  2. Sign in with SSO if prompted")
    print("  3. Set a name and expiration")
    print("  4. Under scopes, check  'repo'  (full control)")
    print("  5. Click 'Generate token' and copy it")
    print()
    input("  Press Enter to open the browser...")
    webbrowser.open(
        "https://github.com/settings/tokens/new?scopes=repo&description=MCP+Dev+Pipeline"
    )
    print()
    token = input("  Paste your GitHub PAT: ").strip()
    env["GITHUB_TOKEN"] = token


def _try_gh_cli() -> str | None:
    """Return a token from the gh CLI if it is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
