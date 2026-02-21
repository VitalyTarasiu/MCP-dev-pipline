#!/usr/bin/env python3
"""Interactive CLI for the multi-agent development pipeline.

Usage:
    python main.py
"""

import getpass
import os
import sys


def prompt(label: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    text = f"  {label}{suffix}: "
    if secret:
        value = getpass.getpass(text).strip()
    else:
        value = input(text).strip()
    return value or default


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
        jira_token = prompt("API token", secret=True)
    print()

    # --- GitHub ---
    print("  GitHub Configuration")
    print("  " + "-" * 40)
    github_repo = prompt("Repo (owner/repo)", os.getenv("GITHUB_REPO", ""))
    base_branch = prompt("Base branch", os.getenv("BASE_BRANCH", "dev"))
    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        github_token = prompt("Personal access token", secret=True)
    print()

    # --- OpenAI ---
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        openai_key = prompt("OpenAI API key", secret=True)
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
