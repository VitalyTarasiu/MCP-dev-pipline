#!/usr/bin/env python3
"""MCP Development Pipeline — AI-powered software development workflow.

Run interactively:
    python main.py

Run with a requirement directly:
    python main.py "Add structured logging to the authentication module"
"""

import asyncio
import sys

from auth import ensure_credentials


def main() -> None:
    # 1. Make sure .env has all required API keys / tokens.
    #    Opens the browser for Jira + GitHub SSO when tokens are missing.
    ensure_credentials()

    # 2. Import the pipeline *after* credentials are on disk so
    #    config.py picks them up via load_dotenv().
    from pipeline.dev_pipeline import run_pipeline  # noqa: E402

    # 3. Get the product requirement.
    if len(sys.argv) > 1:
        requirement = " ".join(sys.argv[1:])
    else:
        print("MCP Development Pipeline")
        print("=" * 40)
        print()
        print("Describe the feature or change you want.")
        print("The PM agent will create a Jira task, the developer will")
        print("implement it, and the architect will review the PR.")
        print()
        requirement = input("Requirement > ").strip()

    if not requirement:
        print("Error: no requirement provided.")
        sys.exit(1)

    asyncio.run(run_pipeline(requirement))


if __name__ == "__main__":
    main()
