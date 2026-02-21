#!/usr/bin/env python3
"""Interactive CLI for the multi-agent development pipeline.

Usage:
    python main.py
"""

import getpass
import os
import subprocess
import sys
import webbrowser


def prompt(label: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    text = f"  {label}{suffix}: "
    if secret:
        value = getpass.getpass(text).strip()
    else:
        value = input(text).strip()
    return value or default


def _obtain_github_token() -> str:
    """Get GitHub token: try gh CLI first, then open browser for PAT creation."""
    # Try gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            print("  Found token from GitHub CLI (gh).")
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    print()
    print("  GitHub token not found. Opening browser for PAT creation...")
    print("  1. Sign in with SSO if prompted")
    print("  2. Set a name and expiration")
    print("  3. Under scopes, check 'repo' (full control)")
    print("  4. Click 'Generate token' and copy it")
    print()
    input("  Press Enter to open the browser...")
    webbrowser.open(
        "https://github.com/settings/tokens/new?scopes=repo&description=MCP+Dev+Pipeline"
    )
    print()
    return getpass.getpass("  Paste your GitHub PAT: ").strip()


def _obtain_jira_token() -> str:
    """Open browser for Jira API token creation via SSO."""
    print()
    print("  Jira API token not found. Opening browser for token creation...")
    print("  1. Sign in with SSO if prompted")
    print("  2. Click 'Create API token'")
    print("  3. Name it (e.g. 'MCP Pipeline') and click Create")
    print("  4. Copy the token")
    print()
    input("  Press Enter to open the browser...")
    webbrowser.open("https://id.atlassian.com/manage-profile/security/api-tokens")
    print()
    return getpass.getpass("  Paste your Jira API token: ").strip()


def _obtain_openai_key() -> str:
    """Get OpenAI API key."""
    print()
    print("  OpenAI API key not found. Opening browser...")
    print()
    input("  Press Enter to open the browser...")
    webbrowser.open("https://platform.openai.com/api-keys")
    print()
    return getpass.getpass("  Paste your OpenAI API key: ").strip()


def main() -> None:
    print()
    print("=" * 58)
    print("    Multi-Agent Development Pipeline")
    print("=" * 58)
    print()

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        open(env_path, "w").close()

    from dotenv import load_dotenv, set_key

    load_dotenv(env_path)

    # --- Jira ---
    print("  Jira Configuration")
    print("  " + "-" * 40)
    jira_url = prompt("URL", os.getenv("JIRA_URL", ""))
    jira_user = prompt("User email", os.getenv("JIRA_USER", ""))
    jira_project = prompt("Project key", os.getenv("JIRA_PROJECT_KEY", ""))

    jira_token = os.getenv("JIRA_API_TOKEN", "")
    if not jira_token:
        jira_token = _obtain_jira_token()
    print()

    # --- GitHub ---
    print("  GitHub Configuration")
    print("  " + "-" * 40)
    github_repo = prompt("Repo (owner/repo)", os.getenv("GITHUB_REPO", ""))
    base_branch = prompt("Base branch", os.getenv("BASE_BRANCH", "dev"))

    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        github_token = _obtain_github_token()
    print()

    # --- OpenAI ---
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        openai_key = _obtain_openai_key()
        print()

    # Persist to .env and set for current process
    for key, val in [
        ("JIRA_URL", jira_url),
        ("JIRA_USER", jira_user),
        ("JIRA_PROJECT_KEY", jira_project),
        ("JIRA_API_TOKEN", jira_token),
        ("GITHUB_REPO", github_repo),
        ("BASE_BRANCH", base_branch),
        ("GITHUB_TOKEN", github_token),
        ("OPENAI_API_KEY", openai_key),
    ]:
        if val:
            os.environ[key] = val
            set_key(env_path, key, val)

    # --- Requirement ---
    print("=" * 58)
    print()
    requirement = input("  Enter your requirement:\n  > ").strip()
    if not requirement:
        print("  No requirement provided. Exiting.")
        sys.exit(1)

    print()
    print("=" * 58)
    print(f"  Jira     : {jira_url} ({jira_project})")
    print(f"  GitHub   : {github_repo} (branch: {base_branch})")
    print(f"  Assignee : {jira_user}")
    print("=" * 58)

    import asyncio

    from pipeline.dev_pipeline import run_pipeline

    asyncio.run(run_pipeline(requirement))


if __name__ == "__main__":
    main()
