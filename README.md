# MCP Development Pipeline

An AI-powered software development pipeline built with [Microsoft AutoGen](https://github.com/microsoft/autogen). Three autonomous agents collaborate to turn a plain-English product requirement into a merged pull request:

| Agent | Role | Model |
|-------|------|-------|
| **Product Manager** | Turns requirements into structured Jira tasks | Claude 3.5 Haiku (cheap) |
| **Developer** | Reads the task, explores the repo, implements changes, creates a PR | Claude 3.5 Haiku (cheap) |
| **Architect** | Reviews the PR for quality, security and architecture; approves or requests changes | Claude Opus 4 (premium) |

## Pipeline Flow

```
User Requirement
       │
       ▼
┌──────────────┐
│   Product    │  Creates a Jira issue with description
│   Manager    │  and acceptance criteria
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Developer   │  Reads task → explores repo → creates branch
│              │  → implements code → creates PR
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Architect   │  Reviews PR diff → approves or requests changes
└──────┬───────┘
       │
  ┌────┴────┐
  │Approved?│
  └────┬────┘
   yes │  no ──► Developer revises ──► Architect re-reviews
       │
       ▼
┌──────────────┐
│  Developer   │  Merges PR → updates Jira to Done
└──────────────┘
```

## Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)
- A [Jira API token](https://id.atlassian.com/manage-profile/security/api-tokens)
- A [GitHub Personal Access Token](https://github.com/settings/tokens) with `repo` scope

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/VitalyTarasiu/MCP-dev-pipline.git
cd MCP-dev-pipline

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and fill in your API keys (see below)
```

### Environment Variables

Edit the `.env` file with your credentials:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `JIRA_URL` | Jira instance URL (default: `https://think-up.atlassian.net`) |
| `JIRA_USER` | Jira username / email |
| `JIRA_API_TOKEN` | Jira API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens)) |
| `JIRA_PROJECT_KEY` | Jira project key (default: `TUP`) |
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope |
| `GITHUB_REPO` | Target repository as `owner/repo` (default: `thinkup-global/api-controller`) |
| `BASE_BRANCH` | Branch PRs target (default: `dev`) |
| `DEVELOPER_MODEL` | Model for the developer agent (default: `claude-3-5-haiku-latest`) |
| `ARCHITECT_MODEL` | Model for the architect agent (default: `claude-opus-4-20250514`) |

## Usage

### Interactive mode

```bash
python main.py
```

You will be prompted to type your requirement. Example:

```
Requirement > I want you to add structured logging to the authentication module
```

### Command-line mode

```bash
python main.py "Add a health-check endpoint that returns service status and version"
```

### What happens

1. The **Product Manager** creates a Jira issue in your project with a clear description and acceptance criteria.
2. The **Developer** reads the Jira task, explores the repository, creates a feature branch, implements the changes, and opens a Pull Request.
3. The **Architect** reviews the PR diff. If the code is good, it approves and hands back to the developer to merge. If changes are needed, it sends feedback and the developer revises.
4. Once approved, the **Developer** merges the PR and marks the Jira issue as Done.

All progress is streamed to the terminal in real time.

## Project Structure

```
MCP-dev-pipline/
├── main.py                    # CLI entry point
├── config.py                  # Loads .env configuration
├── requirements.txt           # Python dependencies
├── .env.example               # Template for environment variables
├── tools/
│   ├── jira_tools.py          # Jira API: create issues, update status, comment
│   └── github_tools.py        # GitHub API: branches, files, PRs, reviews, merge
└── pipeline/
    └── dev_pipeline.py        # AutoGen multi-agent orchestration
```

## Customisation

- **Change models**: Edit `DEVELOPER_MODEL` / `ARCHITECT_MODEL` / `PM_MODEL` in `.env`.
- **Change target repo**: Edit `GITHUB_REPO` and `BASE_BRANCH` in `.env`.
- **Change Jira project**: Edit `JIRA_PROJECT_KEY` in `.env`.
- **Adjust review rounds**: The pipeline allows up to 50 messages (configurable via `MaxMessageTermination` in `dev_pipeline.py`).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Error creating Jira issue` | Verify `JIRA_API_TOKEN` is valid. SSO users must create an API token, not use their password. |
| `Error creating branch` | Ensure `GITHUB_TOKEN` has `repo` scope and the `BASE_BRANCH` exists. |
| `401 Unauthorized` on GitHub | Regenerate your PAT and update `.env`. |
| Model errors | Verify `ANTHROPIC_API_KEY` is set and the model names are correct for your Anthropic account. |
