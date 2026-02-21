# Multi-Agent Development Pipeline

An AI-powered software development workflow using [Microsoft AutoGen](https://github.com/microsoft/autogen).

Three agents collaborate with **independent contexts and models**:

| Agent | Model | Role |
|-------|-------|------|
| **Product Manager** | gpt-4o-mini | Creates Jira tasks from requirements |
| **Developer** | gpt-4o-mini | Reads Jira, implements code, creates PRs |
| **Architect** | gpt-4o | Reviews PRs, approves or requests changes |

## How It Works

```
User types a requirement in plain English
        |
        v
[PM Agent] Creates Jira task (assigned to you)
        |
        v
[Developer Agent] Reads Jira ticket
        |→ Explores repository structure
        |→ Reads relevant source files
        |→ Creates feature branch
        |→ Makes code changes (complete file content)
        |→ Creates Pull Request
        |→ Comments PR link on Jira ticket
        |
        v
[Architect Agent] Reviews PR diff     ← independent context & model (gpt-4o)
        |
     ┌──┴──┐
     |     |
  APPROVE  REQUEST_CHANGES
     |     |
     |     v
     |  [Developer Agent] Reads review comments  ← fresh independent context
     |     |→ Fixes all issues
     |     |→ Pushes to same branch
     |     |
     |     v
     |  [Architect Agent] Re-reviews...  (up to 5 rounds)
     |
     v
Pipeline Complete — PR left open for manual merge
```

**Key design:**
- Each agent runs in its **own isolated context** — they never see each other's reasoning
- They communicate **only through Jira and GitHub** (tickets, PRs, review comments)
- PRs are **never merged automatically** — always left open for manual merge
- Architect uses **gpt-4o** (smart), Developer uses **gpt-4o-mini** (fast/cheap)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/VitalyTarasiu/MCP-dev-pipline.git
cd MCP-dev-pipline

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

That's it. No manual `.env` editing needed — the CLI handles everything on first run.

---

## Usage

```bash
python main.py
```

### First Run — Interactive Setup

On first run, the CLI prompts you for everything and **opens your browser** for SSO authentication:

```
==========================================================
    Multi-Agent Development Pipeline
==========================================================

  Jira Configuration
  ----------------------------------------
  URL: https://your-company.atlassian.net
  User email: you@company.com
  Project key: PROJ

  Jira API token not found. Opening browser for token creation...
  1. Sign in with SSO if prompted
  2. Click 'Create API token'
  3. Name it (e.g. 'MCP Pipeline') and click Create
  4. Copy the token

  Press Enter to open the browser...
  Paste your Jira API token: ****

  GitHub Configuration
  ----------------------------------------
  Repo (owner/repo): myorg/my-repo
  Base branch [dev]: dev

  Found token from GitHub CLI (gh).       ← auto-detected if gh is installed

==========================================================

  Enter your requirement:
  > I want to add structured logging to the payment module

==========================================================
  Jira     : https://your-company.atlassian.net (PROJ)
  GitHub   : myorg/my-repo (branch: dev)
  Assignee : you@company.com
==========================================================

  Phase 1 -- Product Manager creating Jira task
  ...
```

### Subsequent Runs

All credentials are saved to `.env`. On next run, only the Jira/GitHub project details and your requirement are asked:

```bash
python main.py
```

### Authentication Flow

| Service | How it authenticates |
|---------|---------------------|
| **Jira** | Opens browser → Atlassian SSO → you create an API token → paste it |
| **GitHub** | Auto-detects `gh` CLI token. If not found: opens browser → GitHub SSO → you create a PAT with `repo` scope → paste it |
| **OpenAI** | Opens browser → OpenAI dashboard → you copy your API key → paste it |

All tokens are stored in `.env` (git-ignored) and reused on future runs.

---

## Project Structure

```
MCP-dev-pipline/
├── main.py                  # Interactive CLI entry point
├── config.py                # Environment configuration
├── auth.py                  # Browser-based SSO helpers (legacy)
├── pipeline/
│   └── dev_pipeline.py      # Agent orchestration with review loop
├── tools/
│   ├── jira_tools.py        # Jira API: create issues, comments, assign
│   └── github_tools.py      # GitHub API: branches, files, PRs, reviews
├── requirements.txt         # Python dependencies
├── .env.example             # Template for environment variables
├── .env                     # Your credentials (git-ignored)
└── README.md
```

## Requirements

- **Python 3.11+**
- **OpenAI API key** — for LLM models ([get one here](https://platform.openai.com/api-keys))
- **Jira API token** — for task management ([generate here](https://id.atlassian.com/manage-profile/security/api-tokens))
- **GitHub PAT** with `repo` scope — for code changes ([create here](https://github.com/settings/tokens/new?scopes=repo))

## Customizing Models

Edit `.env` to change which models each agent uses:

```env
DEVELOPER_MODEL=gpt-4o-mini    # cheap & fast for code generation
ARCHITECT_MODEL=gpt-4o          # smart for code review
PM_MODEL=gpt-4o-mini            # cheap for task creation
```
