# Multi-Agent Development Pipeline

An AI-powered software development workflow using [Microsoft AutoGen](https://github.com/microsoft/autogen).

Three agents collaborate with **independent contexts and models**:

| Agent | Model | Role |
|-------|-------|------|
| **Product Manager** | gpt-4o-mini | Creates Jira tasks from requirements |
| **Developer** | gpt-4o-mini | Reads Jira, implements code, creates PRs |
| **Architect** | gpt-4o | Reviews PRs, approves or requests changes |

## Flow

```
User requirement
    |
    v
[PM] Creates Jira task (assigned to configured user)
    |
    v
[Developer] Reads Jira -> explores repo -> implements -> creates PR
    |
    v
[Architect] Reviews PR diff
    |           |
    |       CHANGES_REQUESTED
    |           |
    |           v
    |       [Developer] Reads review comments -> pushes fixes
    |           |
    |           v
    |       [Architect] Re-reviews...  (loop up to 5 rounds)
    |
    APPROVED
    |
    v
Pipeline complete — PR left open for manual merge
```

**Key design decisions:**
- Each agent runs in its **own context** — they communicate only through Jira and GitHub, never through shared conversation history.
- PRs are **never merged automatically**. The pipeline ends when the architect approves.
- The architect and developer use **different models** (gpt-4o vs gpt-4o-mini).

## Setup

```bash
# 1. Clone
git clone https://github.com/VitalyTarasiu/MCP-dev-pipline.git
cd MCP-dev-pipline

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Pre-fill credentials
cp .env.example .env
# Edit .env with your API keys
```

## Usage

```bash
python main.py
```

The CLI will interactively ask for:
1. **Jira URL** and project key
2. **GitHub repo** and base branch
3. **API tokens** (if not already in `.env`)
4. **Your requirement** (what the PM should create as a task)

Values are saved to `.env` for future runs.

## Project Structure

```
├── main.py                  # Interactive CLI entry point
├── config.py                # Environment configuration
├── pipeline/
│   └── dev_pipeline.py      # Agent orchestration with review loop
├── tools/
│   ├── jira_tools.py        # Jira API: create issues, comments
│   └── github_tools.py      # GitHub API: branches, files, PRs, reviews
├── requirements.txt
├── .env.example
└── README.md
```

## Requirements

- Python 3.11+
- OpenAI API key
- Jira API token ([generate here](https://id.atlassian.com/manage-profile/security/api-tokens))
- GitHub personal access token with `repo` scope
