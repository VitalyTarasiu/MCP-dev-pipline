import json
from atlassian import Jira
from config import config

_jira_client: Jira | None = None


def _get_jira() -> Jira:
    global _jira_client
    if _jira_client is None:
        _jira_client = Jira(
            url=config.JIRA_URL,
            username=config.JIRA_USER,
            password=config.JIRA_API_TOKEN,
        )
    return _jira_client


def _find_assignee_account_id(jira: Jira) -> str | None:
    """Look up the Jira account ID for the configured user."""
    try:
        me = jira.myself()
        return me.get("accountId")
    except Exception:
        pass
    return None


def create_jira_issue(
    summary: str,
    description: str,
    acceptance_criteria: str = "",
    issue_type: str = "Task",
) -> str:
    """Create a new Jira issue, assign it to the configured user.

    Args:
        summary: Brief title for the issue.
        description: Detailed description of the work.
        acceptance_criteria: Definition-of-done checklist (appended to description).
        issue_type: Issue type name - Task, Story, or Bug. Defaults to Task.

    Returns:
        The created issue key and URL, or an error message.
    """
    try:
        jira = _get_jira()
        full_description = description
        if acceptance_criteria:
            full_description += f"\n\n*Acceptance Criteria:*\n{acceptance_criteria}"

        fields: dict = {
            "project": {"key": config.JIRA_PROJECT_KEY},
            "summary": summary,
            "description": full_description,
            "issuetype": {"name": issue_type},
        }

        account_id = _find_assignee_account_id(jira)
        if account_id:
            fields["assignee"] = {"accountId": account_id}

        result = jira.issue_create(fields=fields)
        issue_key = result["key"]
        assigned = config.JIRA_USER if account_id else "could not assign"
        return (
            f"Created Jira issue: {issue_key}\n"
            f"URL: {config.JIRA_URL}/browse/{issue_key}\n"
            f"Assigned to: {assigned}"
        )
    except Exception as e:
        return f"Error creating Jira issue: {e}"


def get_jira_issue(issue_key: str) -> str:
    """Get the full details of a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g. 'TUP-123')

    Returns:
        JSON string with issue details.
    """
    try:
        jira = _get_jira()
        issue = jira.issue(issue_key)
        fields = issue.get("fields", {})
        assignee = fields.get("assignee")
        return json.dumps(
            {
                "key": issue.get("key"),
                "summary": fields.get("summary", ""),
                "description": fields.get("description", ""),
                "status": fields.get("status", {}).get("name", ""),
                "issue_type": fields.get("issuetype", {}).get("name", ""),
                "assignee": assignee.get("displayName", "Unassigned") if assignee else "Unassigned",
            },
            indent=2,
        )
    except Exception as e:
        return f"Error getting Jira issue: {e}"


def add_jira_comment(issue_key: str, comment: str) -> str:
    """Add a comment to a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g. 'TUP-123')
        comment: The comment text to add.

    Returns:
        Confirmation message or error.
    """
    try:
        jira = _get_jira()
        jira.issue_add_comment(issue_key, comment)
        return f"Added comment to {issue_key}"
    except Exception as e:
        return f"Error adding comment: {e}"
