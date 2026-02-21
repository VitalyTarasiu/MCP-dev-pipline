"""Multi-agent development pipeline with independent agent contexts.

Each agent (PM, Developer, Architect) runs in its own single-agent team.
They communicate only through Jira and GitHub — never through shared
conversation history.  Fresh agent instances are created per phase for
true context independence.

The review loop repeats until the architect approves or max rounds
are reached.  PRs are NEVER merged automatically.
"""

from __future__ import annotations

import re

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

from config import get_config
from tools.jira_tools import create_jira_issue, get_jira_issue, add_jira_comment
from tools.github_tools import (
    get_repo_tree,
    get_file_content,
    create_branch,
    create_or_update_file,
    create_pull_request,
    get_pr_diff,
    get_pr_files,
    get_pr_reviews,
    get_pr_review_comments,
    add_pr_review,
    approve_pull_request,
)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

PM_SYSTEM_MESSAGE = """\
You are a Product Manager. Your ONLY job is to create a well-structured Jira task.

When given a requirement:
1. Write a clear one-line summary.
2. Write a detailed description explaining what needs to be done.
3. Write acceptance criteria as a numbered list.
4. Call create_jira_issue to create the task (it will be auto-assigned).

After creating the issue, report the issue key and end your message with PHASE_COMPLETE.
"""

DEV_SYSTEM_MESSAGE = """\
You are a Software Developer working on a Java/Gradle project.

IMPORTANT: Complete ALL steps below. Do NOT stop until you have created the PR.

Your workflow:
1. Call get_jira_issue to read the task requirements.
2. Call get_repo_tree to explore the repository and find relevant files.
3. Call get_file_content to read the FULL content of every file you plan to change.
4. Call create_branch to create a feature branch named feature/<JIRA_KEY>-<short-desc>.
5. Call create_or_update_file for EACH file you need to change.
   CRITICAL: You MUST provide the COMPLETE file content — every line of the original
   file plus your additions. NEVER submit a partial snippet or skeleton.
6. Call create_pull_request to open a PR referencing the Jira key.
7. Call add_jira_comment to post the PR link on the Jira ticket.

After completing ALL steps, end your final message with PHASE_COMPLETE.

Rules:
- Always read the full file before modifying it.
- Provide COMPLETE file content when updating — preserve ALL existing code.
- Keep changes minimal and focused on the task.
- Follow existing code patterns and conventions.
- NEVER merge any PR.
"""

DEV_FIX_SYSTEM_MESSAGE = """\
You are a Software Developer fixing review feedback on a Pull Request.

IMPORTANT: Complete ALL steps below.

Your workflow:
1. Call get_pr_reviews to read all review feedback.
2. Call get_pr_review_comments to read any inline comments.
3. Call get_file_content to read the current file content from the feature branch.
4. Call create_or_update_file to push fixes.
   CRITICAL: Provide the COMPLETE file content — every original line plus your fix.
   NEVER submit a partial snippet.

After pushing all fixes, end your final message with PHASE_COMPLETE.

Rules:
- Fix ALL issues mentioned by the reviewer.
- Preserve all existing code that was not flagged.
- NEVER merge any PR.
"""

ARCH_SYSTEM_MESSAGE = """\
You are a Senior Software Architect reviewing a Pull Request.

Review process:
1. Call get_pr_diff to read the full diff.
2. Call get_pr_files to list changed files.
3. If needed, call get_file_content for additional context.
4. Evaluate the changes for:
   - Correctness: Does it fulfill the Jira task?
   - Completeness: Are ALL existing methods/classes preserved? No accidental deletions?
   - Quality: Clean, readable, follows project conventions?
   - Security: No sensitive data in logs?
   - Best practices: Proper error handling, appropriate log levels?

CRITICAL: The diff should show ONLY targeted additions/modifications.
If you see massive deletions of existing code, REQUEST CHANGES immediately.

If the code is acceptable:
- Call add_pr_review with event="APPROVE" and a summary of what looks good.
  If self-approval is blocked by GitHub, use event="COMMENT" with APPROVED in body.
- End your message with: APPROVED

If changes are needed:
- Call add_pr_review with event="REQUEST_CHANGES" and specific, actionable feedback.
- End your message with: CHANGES_REQUESTED

NEVER merge any PR.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _search_messages(messages: list, pattern: str) -> str | None:
    """Search all messages for a regex match, returning the first capture group."""
    for msg in messages:
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            for item in content:
                text = str(getattr(item, "content", ""))
                m = re.search(pattern, text)
                if m:
                    return m.group(1)
        elif isinstance(content, str):
            m = re.search(pattern, content)
            if m:
                return m.group(1)
    return None


def _last_text(messages: list) -> str:
    """Get the text of the last message in the list."""
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content.strip():
            return content
    return ""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


async def run_pipeline(requirement: str) -> None:
    """Run the full development pipeline with independent agent contexts."""

    cfg = get_config()

    def _dev_client():
        return OpenAIChatCompletionClient(model=cfg.DEVELOPER_MODEL, api_key=cfg.OPENAI_API_KEY)

    def _arch_client():
        return OpenAIChatCompletionClient(model=cfg.ARCHITECT_MODEL, api_key=cfg.OPENAI_API_KEY)

    def _pm_client():
        return OpenAIChatCompletionClient(model=cfg.PM_MODEL, api_key=cfg.OPENAI_API_KEY)

    # ========== Phase 1: PM creates Jira task ==========
    print(f"\n{'=' * 58}")
    print(f"  Phase 1 -- Product Manager creating Jira task")
    print(f"  Model: {cfg.PM_MODEL}")
    print(f"{'=' * 58}\n")

    pm = AssistantAgent(
        name="product_manager",
        model_client=_pm_client(),
        system_message=PM_SYSTEM_MESSAGE,
        tools=[create_jira_issue],
    )
    pm_team = RoundRobinGroupChat(
        participants=[pm],
        termination_condition=TextMentionTermination("PHASE_COMPLETE") | MaxMessageTermination(20),
    )
    pm_result = await Console(pm_team.run_stream(task=requirement))

    jira_key = _search_messages(pm_result.messages, r"([A-Z]+-\d+)")
    if not jira_key:
        print("\n  ERROR: Could not extract Jira issue key. Aborting.")
        return
    print(f"\n  >>> Jira issue: {jira_key}")

    # ========== Phase 2: Developer implements & creates PR ==========
    print(f"\n{'=' * 58}")
    print(f"  Phase 2 -- Developer implementing changes")
    print(f"  Model: {cfg.DEVELOPER_MODEL} (independent context)")
    print(f"{'=' * 58}\n")

    dev_task = (
        f"Read Jira ticket {jira_key} and implement the required changes.\n"
        f"Create a feature branch, make the code changes, and create a Pull Request.\n"
        f"Add a comment to {jira_key} with the PR link.\n"
        f"You must complete ALL steps described in your system instructions."
    )

    dev = AssistantAgent(
        name="developer",
        model_client=_dev_client(),
        system_message=DEV_SYSTEM_MESSAGE,
        tools=[
            get_jira_issue,
            get_repo_tree,
            get_file_content,
            create_branch,
            create_or_update_file,
            create_pull_request,
            add_jira_comment,
        ],
    )
    dev_team = RoundRobinGroupChat(
        participants=[dev],
        termination_condition=TextMentionTermination("PHASE_COMPLETE") | MaxMessageTermination(60),
    )
    dev_result = await Console(dev_team.run_stream(task=dev_task))

    pr_number_str = (
        _search_messages(dev_result.messages, r"PR #(\d+)")
        or _search_messages(dev_result.messages, r"pull/(\d+)")
    )
    if not pr_number_str:
        print("\n  ERROR: Could not extract PR number. Aborting.")
        return
    pr_number = int(pr_number_str)
    print(f"\n  >>> PR: #{pr_number}")

    # ========== Phase 3: Review loop ==========
    max_rounds = 3
    for round_num in range(1, max_rounds + 1):
        # --- Architect reviews (fresh agent = independent context) ---
        print(f"\n{'=' * 58}")
        print(f"  Phase 3.{round_num}a -- Architect reviewing PR #{pr_number}")
        print(f"  Model: {cfg.ARCHITECT_MODEL} (independent context)")
        print(f"{'=' * 58}\n")

        arch_task = (
            f"Review Pull Request #{pr_number} on the repository.\n"
            f"Get the diff, examine the changes, and submit your review.\n"
            f"APPROVE if the code is correct and complete, or REQUEST_CHANGES with feedback."
        )
        arch = AssistantAgent(
            name="architect",
            model_client=_arch_client(),
            system_message=ARCH_SYSTEM_MESSAGE,
            tools=[
                get_pr_diff,
                get_pr_files,
                get_file_content,
                add_pr_review,
                approve_pull_request,
            ],
        )
        arch_team = RoundRobinGroupChat(
            participants=[arch],
            termination_condition=(
                TextMentionTermination("APPROVED")
                | TextMentionTermination("CHANGES_REQUESTED")
                | MaxMessageTermination(30)
            ),
        )
        arch_result = await Console(arch_team.run_stream(task=arch_task))

        # Print the architect's review comment
        arch_comment = _last_text(arch_result.messages)
        print(f"\n  {'─' * 54}")
        print(f"  Architect Review (round {round_num}):")
        print(f"  {'─' * 54}")
        for line in arch_comment.strip().split("\n"):
            print(f"  {line}")
        print(f"  {'─' * 54}")

        if "APPROVED" in arch_comment.upper():
            print(f"\n  >>> PR #{pr_number} APPROVED by architect")
            break

        if round_num == max_rounds:
            print(f"\n  WARNING: Max review rounds ({max_rounds}) reached.")
            break

        # --- Developer fixes (fresh agent = independent context) ---
        print(f"\n{'=' * 58}")
        print(f"  Phase 3.{round_num}b -- Developer fixing review comments")
        print(f"  Model: {cfg.DEVELOPER_MODEL} (independent context)")
        print(f"{'=' * 58}\n")

        fix_task = (
            f"Read the review comments on PR #{pr_number}.\n"
            f"Fix ALL issues raised by the architect.\n"
            f"Push the fixes to the same feature branch.\n"
            f"You must complete ALL steps described in your system instructions."
        )
        dev_fix = AssistantAgent(
            name="developer",
            model_client=_dev_client(),
            system_message=DEV_FIX_SYSTEM_MESSAGE,
            tools=[
                get_pr_reviews,
                get_pr_review_comments,
                get_repo_tree,
                get_file_content,
                create_or_update_file,
                add_jira_comment,
            ],
        )
        dev_fix_team = RoundRobinGroupChat(
            participants=[dev_fix],
            termination_condition=TextMentionTermination("PHASE_COMPLETE") | MaxMessageTermination(60),
        )
        await Console(dev_fix_team.run_stream(task=fix_task))

    # ========== Summary ==========
    print(f"\n{'=' * 58}")
    print(f"  Pipeline Complete")
    print(f"  Jira : {cfg.JIRA_URL}/browse/{jira_key}")
    print(f"  PR   : https://github.com/{cfg.GITHUB_REPO}/pull/{pr_number}")
    print(f"  Status: PR is open -- NOT merged (manual merge required)")
    print(f"{'=' * 58}\n")
