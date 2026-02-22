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


def _obtain_github_token(try_cli: bool = True) -> str:
    """Get GitHub token: try gh CLI first (unless try_cli=False), then open browser for PAT creation."""
    if try_cli:
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
    print("  Opening browser for GitHub PAT creation...")
    print("  1. Sign in with SSO if prompted")
    print("  2. Set a name and expiration")
    print("  3. Under scopes, check 'repo' (full control)")
    print("  4. Click 'Generate token', copy it, then come back here and paste it below")
    print()
    webbrowser.open(
        "https://github.com/settings/tokens/new?scopes=repo&description=MCP+Dev+Pipeline"
    )
    print()
    return input("  Paste your GitHub PAT: ").strip()


def _obtain_jira_token() -> str:
    """Open browser for Jira API token creation via SSO."""
    print()
    print("  Opening browser for Jira API token creation...")
    print("  1. Sign in with SSO if prompted")
    print("  2. Click 'Create API token'")
    print("  3. Name it (e.g. 'MCP Pipeline') and click Create")
    print("  4. Copy the token, then come back here and paste it below")
    print()
    webbrowser.open("https://id.atlassian.com/manage-profile/security/api-tokens")
    print()
    return input("  Paste your Jira API token: ").strip()


def _obtain_openai_key() -> str:
    """Get OpenAI API key."""
    print()
    print("  Opening browser for OpenAI API key creation...")
    print("  Copy the key, then come back here and paste it below")
    print()
    webbrowser.open("https://platform.openai.com/api-keys")
    print()
    return getpass.getpass("  Paste your OpenAI API key: ").strip()


def _validate_jira(url: str, user: str, token: str) -> bool:
    """Return True if the Jira credentials work."""
    try:
        import requests
        r = requests.get(f"{url}/rest/api/2/myself", auth=(user, token), timeout=10)
        if r.status_code == 200:
            return True
        seraph = r.headers.get("X-Seraph-Loginreason", "")
        if seraph == "AUTHENTICATED_FAILED":
            print(
                f"  Jira API token authentication is blocked (HTTP {r.status_code}).\n"
                f"  Your organization's Atlassian admin has likely disabled 'Personal API tokens'.\n"
                f"  Ask your Jira admin to go to admin.atlassian.com → Security →\n"
                f"  Authentication policies → and enable 'Personal API tokens'."
            )
        else:
            print(f"  Jira authentication failed: HTTP {r.status_code} — {r.text[:120]}")
        return False
    except Exception as e:
        print(f"  Jira connection error: {e}")
        return False


def _validate_github(token: str, repo: str) -> bool:
    """Return True if the GitHub token and repo are accessible."""
    try:
        from github import Github
        g = Github(token)
        g.get_repo(repo)
        return True
    except Exception as e:
        print(f"  GitHub authentication failed: {e}")
        return False


def _ensure_jira_token(url: str, user: str, token: str, env_path: str) -> str:
    """Validate the Jira token; re-prompt on simple auth failure, warn and continue on org-policy block."""
    from dotenv import set_key

    print(f"  Checking Jira connection...")
    if _validate_jira(url, user, token):
        print("  Jira connection OK.")
        return token

    # If the header shows AUTHENTICATED_FAILED it's an org policy issue — no point retrying with new tokens.
    import requests
    try:
        r = requests.get(f"{url}/rest/api/2/myself", auth=(user, token), timeout=10)
        org_policy_block = r.headers.get("X-Seraph-Loginreason") == "AUTHENTICATED_FAILED"
    except Exception:
        org_policy_block = False

    if org_policy_block:
        print()
        print("  WARNING: Jira auth is blocked by your org's authentication policy.")
        print("  The pipeline will start but Jira operations will fail until your")
        print("  Jira admin enables API tokens at admin.atlassian.com.")
        print()
        answer = input("  Continue anyway? [y/N]: ").strip().lower()
        if answer != "y":
            sys.exit(0)
        return token

    # Simple bad token — let user retry once with browser popup
    print()
    print("  Jira credentials are invalid. Opening browser to create a new token...")
    set_key(env_path, "JIRA_API_TOKEN", "")
    os.environ.pop("JIRA_API_TOKEN", None)
    token = _obtain_jira_token()

    print(f"  Re-checking Jira connection...")
    if _validate_jira(url, user, token):
        print("  Jira connection OK.")
        return token

    print()
    print("  WARNING: Jira authentication still failing. The pipeline will start")
    print("  but Jira operations may fail. Check your token and try again.")
    answer = input("  Continue anyway? [y/N]: ").strip().lower()
    if answer != "y":
        sys.exit(0)
    return token


def _ensure_github_token(token: str, repo: str, env_path: str) -> str:
    """Validate the GitHub token, re-prompting with browser popup if invalid."""
    from dotenv import set_key
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        print(f"  Checking GitHub connection... (attempt {attempt}/{max_attempts})")
        if _validate_github(token, repo):
            print("  GitHub connection OK.")
            return token
        print()
        print("  GitHub credentials are invalid. Opening browser to create a new token...")
        set_key(env_path, "GITHUB_TOKEN", "")
        os.environ.pop("GITHUB_TOKEN", None)
        # Skip gh CLI on retries — it would return the same bad token
        token = _obtain_github_token(try_cli=False)
    print("  ERROR: Could not authenticate with GitHub after multiple attempts. Exiting.")
    sys.exit(1)


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

    # --- Validate credentials ---
    print()
    print("  Validating credentials...")
    print("  " + "-" * 40)
    jira_token = _ensure_jira_token(jira_url, jira_user, jira_token, env_path)
    github_token = _ensure_github_token(github_token, github_repo, env_path)
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
