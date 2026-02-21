from github import Github, GithubException, Repository
from config import config

_github_client: Github | None = None
_repo: Repository.Repository | None = None
_last_branch: str | None = None


def _get_repo() -> Repository.Repository:
    global _github_client, _repo
    if _repo is None:
        _github_client = Github(config.GITHUB_TOKEN)
        _repo = _github_client.get_repo(config.GITHUB_REPO)
    return _repo


def get_repo_tree(path: str = "") -> str:
    """Get the file and directory listing of the repository.

    Args:
        path: Subdirectory path to list. Empty string for root directory.

    Returns:
        Formatted list of files and directories.
    """
    try:
        repo = _get_repo()
        ref = _last_branch or config.BASE_BRANCH
        contents = repo.get_contents(path, ref=ref)
        if not isinstance(contents, list):
            contents = [contents]
        result = []
        for item in sorted(contents, key=lambda x: (x.type != "dir", x.path)):
            marker = "[DIR] " if item.type == "dir" else "[FILE]"
            result.append(f"{marker} {item.path}")
        return "\n".join(result) if result else "Empty directory"
    except Exception as e:
        return f"Error listing repository: {e}"


def get_file_content(file_path: str, branch: str = "") -> str:
    """Read the content of a file from the repository.

    Args:
        file_path: Path to the file in the repository.
        branch: Branch to read from. Defaults to feature branch or base branch.

    Returns:
        The file content as a string.
    """
    try:
        repo = _get_repo()
        ref = branch or _last_branch or config.BASE_BRANCH
        content = repo.get_contents(file_path, ref=ref)
        if isinstance(content, list):
            return f"Error: {file_path} is a directory, not a file"
        return content.decoded_content.decode("utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def create_branch(branch_name: str) -> str:
    """Create a new branch from the configured base branch.

    Args:
        branch_name: Name for the new branch (e.g. 'feature/TUP-123-add-logging')

    Returns:
        Confirmation with branch name or error message.
    """
    global _last_branch
    try:
        repo = _get_repo()
        base = repo.get_branch(config.BASE_BRANCH)
        repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=base.commit.sha,
        )
        _last_branch = branch_name
        return f"Created branch: {branch_name} (from {config.BASE_BRANCH})"
    except GithubException as e:
        if e.status == 422:
            _last_branch = branch_name
            return f"Branch '{branch_name}' already exists — will use it"
        return f"Error creating branch: {e}"
    except Exception as e:
        return f"Error creating branch: {e}"


def create_or_update_file(
    file_path: str, content: str, commit_message: str = "", branch: str = ""
) -> str:
    """Create a new file or update an existing file in the repository.

    Args:
        file_path: Path where the file should be created or updated.
        content: The COMPLETE file content to write.
        commit_message: Git commit message. Defaults to 'Update <file_path>'.
        branch: Branch to commit to. Defaults to the last created branch.

    Returns:
        Confirmation message with commit details.
    """
    if not branch:
        branch = _last_branch or config.BASE_BRANCH
    if not commit_message:
        commit_message = f"Update {file_path}"
    try:
        repo = _get_repo()
        try:
            existing = repo.get_contents(file_path, ref=branch)
            if isinstance(existing, list):
                return f"Error: {file_path} is a directory"
            result = repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
            return f"Updated {file_path} on {branch} (commit: {result['commit'].sha[:8]})"
        except GithubException:
            result = repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch,
            )
            return f"Created {file_path} on {branch} (commit: {result['commit'].sha[:8]})"
    except Exception as e:
        return f"Error writing file: {e}"


def create_pull_request(title: str, body: str, head_branch: str = "") -> str:
    """Create a pull request from a feature branch to the base branch.

    Args:
        title: PR title (should include the Jira issue key).
        body: PR description in markdown.
        head_branch: Source branch name. Defaults to the last created branch.

    Returns:
        The PR number and URL.
    """
    if not head_branch:
        head_branch = _last_branch or config.BASE_BRANCH
    try:
        repo = _get_repo()
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=config.BASE_BRANCH,
        )
        return f"Created PR #{pr.number}: {pr.title}\nURL: {pr.html_url}"
    except Exception as e:
        return f"Error creating pull request: {e}"


def get_pr_diff(pr_number: int) -> str:
    """Get the full diff of a pull request for code review.

    Args:
        pr_number: The pull request number.

    Returns:
        Formatted diff showing all file changes.
    """
    try:
        repo = _get_repo()
        pr = repo.get_pull(pr_number)
        files = pr.get_files()
        diff_parts = []
        for f in files:
            diff_parts.append(f"{'=' * 60}")
            diff_parts.append(
                f"File: {f.filename} | Status: {f.status} | +{f.additions} -{f.deletions}"
            )
            diff_parts.append(f"{'=' * 60}")
            if f.patch:
                diff_parts.append(f.patch)
            else:
                diff_parts.append("(binary file or no patch available)")
            diff_parts.append("")
        return "\n".join(diff_parts) if diff_parts else "No file changes in this PR"
    except Exception as e:
        return f"Error getting PR diff: {e}"


def get_pr_files(pr_number: int) -> str:
    """Get the list of files changed in a pull request.

    Args:
        pr_number: The pull request number.

    Returns:
        List of changed files with their status and change counts.
    """
    try:
        repo = _get_repo()
        pr = repo.get_pull(pr_number)
        files = pr.get_files()
        result = []
        for f in files:
            result.append(f"{f.status}: {f.filename} (+{f.additions} -{f.deletions})")
        return "\n".join(result) if result else "No files changed"
    except Exception as e:
        return f"Error getting PR files: {e}"


def get_pr_reviews(pr_number: int) -> str:
    """Get all reviews submitted on a pull request.

    Args:
        pr_number: The pull request number.

    Returns:
        Formatted list of reviews with reviewer, state, and body.
    """
    try:
        repo = _get_repo()
        pr = repo.get_pull(pr_number)
        reviews = list(pr.get_reviews())
        if not reviews:
            return "No reviews on this PR yet."
        result = []
        for r in reviews:
            result.append(f"Reviewer: {r.user.login}")
            result.append(f"State: {r.state}")
            result.append(f"Body: {r.body}")
            result.append("---")
        return "\n".join(result)
    except Exception as e:
        return f"Error getting PR reviews: {e}"


def get_pr_review_comments(pr_number: int) -> str:
    """Get inline review comments on a pull request.

    Args:
        pr_number: The pull request number.

    Returns:
        Formatted list of inline comments with file, line, and body.
    """
    try:
        repo = _get_repo()
        pr = repo.get_pull(pr_number)
        comments = list(pr.get_review_comments())
        if not comments:
            return "No inline review comments on this PR."
        result = []
        for c in comments:
            result.append(f"File: {c.path}")
            result.append(f"Line: {c.position}")
            result.append(f"Author: {c.user.login}")
            result.append(f"Body: {c.body}")
            result.append("---")
        return "\n".join(result)
    except Exception as e:
        return f"Error getting review comments: {e}"


def add_pr_review(pr_number: int, body: str, event: str = "COMMENT") -> str:
    """Add a review to a pull request.

    Args:
        pr_number: The pull request number.
        body: Review comment body with detailed feedback.
        event: Review event type - COMMENT, REQUEST_CHANGES, or APPROVE.

    Returns:
        Confirmation message.
    """
    try:
        repo = _get_repo()
        pr = repo.get_pull(pr_number)
        pr.create_review(body=body, event=event)
        return f"Added {event} review to PR #{pr_number}"
    except Exception as e:
        return f"Error adding review: {e}"


def approve_pull_request(
    pr_number: int, body: str = "Approved by Architecture Review"
) -> str:
    """Approve a pull request after successful review.

    Args:
        pr_number: The pull request number.
        body: Approval comment.

    Returns:
        Confirmation message.
    """
    try:
        repo = _get_repo()
        pr = repo.get_pull(pr_number)
        pr.create_review(body=body, event="APPROVE")
        return f"Approved PR #{pr_number}"
    except Exception as e:
        return f"Error approving PR (may be self-approval restriction): {e}"
