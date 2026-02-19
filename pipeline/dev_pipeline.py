from __future__ import annotations

from typing import Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

from config import config
from tools.jira_tools import (
    create_jira_issue,
    get_jira_issue,
    update_jira_issue_status,
    add_jira_comment,
)
from tools.github_tools import (
    get_repo_tree,
    get_file_content,
    create_branch,
    create_or_update_file,
    create_pull_request,
    get_pr_diff,
    get_pr_files,
    add_pr_review,
    approve_pull_request,
    merge_pull_request,
)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

PM_SYSTEM_MESSAGE = """\
You are a Product Manager agent in an automated software development pipeline.

Your job:
1. Analyze the user's requirement and turn it into a clear, actionable Jira task.
2. The Jira issue must contain:
   - A concise summary/title
   - A detailed description explaining what needs to be done
   - Acceptance criteria as a numbered checklist
   - Any relevant technical notes

After creating the issue, you MUST end your FINAL text response with exactly:
HANDOFF_TO_DEVELOPER
Issue: <ISSUE_KEY>
"""

DEV_SYSTEM_MESSAGE = f"""\
You are a Software Developer agent in an automated development pipeline.
Target repository: {config.GITHUB_REPO} (base branch: {config.BASE_BRANCH}).

IMPORTANT: Complete ALL steps below in a SINGLE turn using multiple tool calls.
Do NOT stop between steps — call all required tools one after another.

Workflow when receiving a NEW task:
1. Call get_jira_issue to read the task requirements.
2. Call get_repo_tree to explore the repository root and relevant subdirectories.
3. Call get_file_content on key files to understand code conventions.
4. Call create_branch to create a feature branch named feature/<ISSUE_KEY>-<short-description>.
5. Call create_or_update_file for EACH file you need to change/create (one call per file).
6. Call create_pull_request to open a PR with a clear description.
7. Call add_jira_comment to post the PR link on the Jira issue.
8. ONLY after completing ALL steps above, end your final text message with:
   HANDOFF_TO_ARCHITECT

Workflow when the architect APPROVES your PR:
1. The PR is approved and ready to merge. Do NOT merge it yourself.
2. End your final text message with:
   PIPELINE_COMPLETE

Workflow when the architect REQUESTS CHANGES:
1. Read their feedback from the conversation history.
2. Call create_or_update_file on the same branch to make the fixes.
3. End your final text message with:
   HANDOFF_TO_ARCHITECT

Rules:
- Keep changes minimal and focused on the task.
- Follow existing code patterns and conventions you observe in the repo.
- Write meaningful commit messages that reference the issue key.
- Do NOT end your turn until you have completed all steps in the current workflow.
"""

ARCH_SYSTEM_MESSAGE = """\
You are a Software Architect and Senior Code Reviewer.

IMPORTANT: You are ONLY called after the developer has created a Pull Request.
Do NOT ask for a PR number — extract it from the conversation history.

Review criteria (check every one):
1. **Correctness** — Does the code fulfill the Jira task requirements?
2. **Code quality** — Clean, readable, follows project conventions?
3. **Architecture** — Fits the existing design, no unnecessary complexity?
4. **Security** — No vulnerabilities, proper input validation?
5. **Performance** — No obvious bottlenecks?
6. **Error handling** — Proper handling of edge cases?

Review process:
1. Find the PR number in the conversation (look for "Created PR #<number>").
2. Call get_pr_diff to read the full diff.
3. Call get_pr_files to list changed files.
4. If needed, call get_file_content for additional context.
5. Write a thorough, constructive review.

If the code is acceptable:
- Call approve_pull_request.
- End your message with:  APPROVED - HANDOFF_TO_DEVELOPER

If changes are needed:
- Call add_pr_review with event="REQUEST_CHANGES" and detailed feedback.
- End your message with:  CHANGES_REQUESTED - HANDOFF_TO_DEVELOPER
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_model_client(model: str) -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model,
        api_key=config.OPENAI_API_KEY,
    )


def workflow_selector(
    messages: Sequence[AgentEvent | ChatMessage],
) -> str | None:
    """Route based on explicit handoff keywords.

    Each agent keeps control until it emits a HANDOFF_ signal in its
    final text response.  This prevents premature agent switching.
    """
    agent_names = {"product_manager", "developer", "architect"}

    for msg in reversed(messages):
        source = getattr(msg, "source", None)
        if source not in agent_names:
            continue

        content = str(getattr(msg, "content", ""))

        if "HANDOFF_TO_DEVELOPER" in content:
            return "developer"
        if "HANDOFF_TO_ARCHITECT" in content:
            return "architect"
        if "PIPELINE_COMPLETE" in content:
            return None

        # No handoff keyword yet — let the same agent continue its work.
        return source

    return "product_manager"


# ---------------------------------------------------------------------------
# Pipeline entry-point
# ---------------------------------------------------------------------------


async def run_pipeline(requirement: str) -> None:
    """Run the full development pipeline for a product requirement."""

    pm_client = _create_model_client(config.PM_MODEL)
    dev_client = _create_model_client(config.DEVELOPER_MODEL)
    arch_client = _create_model_client(config.ARCHITECT_MODEL)
    selector_client = _create_model_client(config.SELECTOR_MODEL)

    pm_agent = AssistantAgent(
        name="product_manager",
        description="Product Manager — creates Jira tasks from requirements",
        model_client=pm_client,
        system_message=PM_SYSTEM_MESSAGE,
        tools=[create_jira_issue],
    )

    dev_agent = AssistantAgent(
        name="developer",
        description="Software Developer — implements code changes and creates PRs",
        model_client=dev_client,
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

    arch_agent = AssistantAgent(
        name="architect",
        description="Software Architect — reviews PRs for quality and approves or rejects",
        model_client=arch_client,
        system_message=ARCH_SYSTEM_MESSAGE,
        tools=[
            get_pr_diff,
            get_pr_files,
            get_file_content,
            add_pr_review,
            approve_pull_request,
        ],
    )

    termination = TextMentionTermination("PIPELINE_COMPLETE") | MaxMessageTermination(
        50
    )

    team = SelectorGroupChat(
        participants=[pm_agent, dev_agent, arch_agent],
        model_client=selector_client,
        selector_func=workflow_selector,
        termination_condition=termination,
        allow_repeated_speaker=True,
    )

    header = (
        f"\n{'=' * 60}\n"
        f"  Development Pipeline Started\n"
        f"  Requirement : {requirement}\n"
        f"  Target Repo : {config.GITHUB_REPO}\n"
        f"  Jira Project: {config.JIRA_PROJECT_KEY}\n"
        f"  Models      : PM={config.PM_MODEL}  Dev={config.DEVELOPER_MODEL}  Arch={config.ARCHITECT_MODEL}\n"
        f"{'=' * 60}\n"
    )
    print(header)

    try:
        result = await Console(team.run_stream(task=requirement))
        print(f"\n{'=' * 60}")
        print("  Pipeline finished.")
        print(f"{'=' * 60}")
    finally:
        await pm_client.close()
        await dev_client.close()
        await arch_client.close()
        await selector_client.close()
