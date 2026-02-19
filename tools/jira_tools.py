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


def create_jira_issue(summary: str, description: str, issue_type: str = "Task") -> str:
    """Create a new Jira issue in the configured project.

    Args:
        summary: Brief title for the issue (e.g. 'Add logging to authentication module')
        description: Detailed description with acceptance criteria
        issue_type: Issue type name - Task, Story, or Bug. Defaults to Task.

    Returns:
        The created issue key and URL, or an error message.
    """
    try:
        jira = _get_jira()
        result = jira.issue_create(
            fields={
                "project": {"key": config.JIRA_PROJECT_KEY},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            }
        )
        issue_key = result["key"]
        return f"Created Jira issue: {issue_key}\nURL: {config.JIRA_URL}/browse/{issue_key}"
    except Exception as e:
        return f"Error creating Jira issue: {e}"


def get_jira_issue(issue_key: str) -> str:
    """Get the full details of a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g. 'TUP-123')

    Returns:
        JSON string with issue details including summary, description, status, and assignee.
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


def update_jira_issue_status(issue_key: str, status_name: str) -> str:
    """Transition a Jira issue to a new status.

    Args:
        issue_key: The Jira issue key (e.g. 'TUP-123')
        status_name: Target status name (e.g. 'In Progress', 'In Review', 'Done')

    Returns:
        Confirmation message or error.
    """
    try:
        jira = _get_jira()
        jira.issue_transition(issue_key, status_name)
        return f"Updated {issue_key} status to: {status_name}"
    except Exception as e:
        return f"Error updating issue status: {e}"


def add_jira_comment(issue_key: str, comment: str) -> str:
    """Add a comment to a Jira issue.

    Args:
        issue_key: The Jira issue key (e.g. 'TUP-123')
        comment: The comment text to add

    Returns:
        Confirmation message or error.
    """
    try:
        jira = _get_jira()
        jira.issue_add_comment(issue_key, comment)
        return f"Added comment to {issue_key}"
    except Exception as e:
        return f"Error adding comment: {e}"
