# Multi-Agent Development Pipeline

An AI-powered software development workflow built with [Microsoft AutoGen v0.4](https://github.com/microsoft/autogen). Three autonomous agents simulate a real dev team: a **Product Manager** creates Jira tasks, a **Developer** writes code and opens PRs, and an **Architect** reviews the code — all driven by a single natural-language requirement.

---

## Agents

| Agent | LLM Model | Role | Tools |
|-------|-----------|------|-------|
| **Product Manager** | `gpt-4o-mini` | Turns a user requirement into a structured Jira task | `create_jira_issue` |
| **Developer** | `gpt-4o-mini` | Reads the Jira ticket, explores the repo, implements code, creates a PR | `get_jira_issue`, `get_repo_tree`, `get_file_content`, `create_branch`, `create_or_update_file`, `create_pull_request`, `add_jira_comment` |
| **Architect** | `gpt-4o` | Reviews the PR diff, approves or requests changes | `get_pr_diff`, `get_pr_files`, `get_file_content`, `add_pr_review`, `approve_pull_request` |
| **Developer (fix mode)** | `gpt-4o-mini` | Reads architect's review comments, pushes fixes to the same branch | `get_pr_reviews`, `get_pr_review_comments`, `get_file_content`, `create_or_update_file` |

---

## Pipeline Flow

```
                        ┌─────────────────────────┐
                        │   User types requirement │
                        │   in plain English       │
                        └────────────┬────────────┘
                                     │
                     ┌───────────────▼───────────────┐
                     │  Phase 1: Product Manager     │
                     │  ─────────────────────────    │
                     │  • Parses the requirement     │
                     │  • Creates Jira task           │
                     │  • Auto-assigns to user        │
                     │  Model: gpt-4o-mini            │
                     └───────────────┬───────────────┘
                                     │ Jira key (e.g. TUP-4609)
                     ┌───────────────▼───────────────┐
                     │  Phase 2: Developer            │
                     │  ─────────────────────────     │
                     │  • Reads Jira ticket           │
                     │  • Explores repository tree    │
                     │  • Reads source files           │
                     │  • Creates feature branch      │
                     │  • Commits code changes        │
                     │  • Creates Pull Request        │
                     │  • Comments PR link on Jira    │
                     │  Model: gpt-4o-mini             │
                     │  Context: independent          │
                     └───────────────┬───────────────┘
                                     │ PR number (e.g. #234)
                     ┌───────────────▼───────────────┐
              ┌─────►│  Phase 3a: Architect Review   │
              │      │  ─────────────────────────     │
              │      │  • Gets PR diff                │
              │      │  • Examines changed files      │
              │      │  • Checks correctness,         │
              │      │    completeness, quality,       │
              │      │    security, best practices     │
              │      │  • Submits review              │
              │      │  Model: gpt-4o                  │
              │      │  Context: independent          │
              │      └───────────┬────────┬──────────┘
              │                  │        │
              │            APPROVED   CHANGES_REQUESTED
              │                  │        │
              │                  │   ┌────▼────────────────────┐
              │                  │   │  Phase 3b: Developer Fix│
              │                  │   │  ───────────────────    │
              │                  │   │  • Reads review comments│
              │                  │   │  • Reads current code   │
              │                  │   │  • Pushes fixes         │
              │                  │   │  Model: gpt-4o-mini     │
              │                  │   │  Context: independent   │
              │                  │   └────────────┬───────────┘
              │                  │                │
              └──────────────────┘◄───────────────┘
              (max 3 review rounds)
                                     │
                     ┌───────────────▼───────────────┐
                     │  Pipeline Complete             │
                     │  PR is open — NOT merged       │
                     │  Manual merge required         │
                     └───────────────────────────────┘
```

---

## How AutoGen Is Used — Detailed Design

### Architecture: Independent Single-Agent Teams

This pipeline uses **AutoGen v0.4** (`autogen-agentchat`) with a deliberate design choice: **each agent runs in its own isolated team** rather than sharing a single group chat. This gives each agent a completely independent context — they never see each other's internal reasoning.

```python
# Each phase creates a FRESH agent + single-agent team
agent = AssistantAgent(
    name="developer",
    model_client=OpenAIChatCompletionClient(model="gpt-4o-mini", api_key=...),
    system_message=DEV_SYSTEM_MESSAGE,
    tools=[get_jira_issue, get_repo_tree, ...],
)
team = RoundRobinGroupChat(
    participants=[agent],
    termination_condition=TextMentionTermination("PHASE_COMPLETE") | MaxMessageTermination(60),
)
result = await Console(team.run_stream(task="Read Jira ticket TUP-123 and..."))
```

#### Why Single-Agent Teams Instead of a Shared Group Chat?

| Approach | Shared `SelectorGroupChat` | Independent single-agent teams (what we use) |
|----------|---------------------------|----------------------------------------------|
| **Context** | All agents see all messages | Each agent only sees its own task |
| **Independence** | Agents can be influenced by each other's reasoning | True isolation — communicate only via Jira/GitHub |
| **Model per agent** | Each agent can have a different model ✓ | Each agent can have a different model ✓ |
| **Multi-step tool calls** | Handled by the team re-prompting | Handled by `RoundRobinGroupChat` re-prompting |
| **Review loop** | Complex selector logic needed | Simple Python `for` loop |
| **Fresh context per round** | Requires manual `on_reset()` | Create a new agent instance per round |

### Key AutoGen Components Used

**1. `AssistantAgent`** — Each agent is an `AssistantAgent` configured with:
- A **system message** (role instructions, workflow steps, rules)
- A **model client** (`OpenAIChatCompletionClient` wrapping an OpenAI model)
- A **tools list** (Python functions that the LLM can call)

The `AssistantAgent` handles the tool-calling loop internally: it calls the LLM, if the LLM requests tool calls it executes them, feeds results back, and repeats until the LLM produces a final text response.

**2. `RoundRobinGroupChat`** — Wraps a single agent into a "team" that:
- Sends the task to the agent
- If the agent responds but hasn't said `PHASE_COMPLETE`, re-prompts it to continue
- This is critical for `gpt-4o-mini` which sometimes stops after a few tool calls instead of completing all steps

**3. `TextMentionTermination`** — Stops the team when the agent's response contains a specific string:
- PM, Developer: `"PHASE_COMPLETE"`
- Architect: `"APPROVED"` or `"CHANGES_REQUESTED"`

**4. `MaxMessageTermination`** — Safety net to prevent infinite loops (60 messages max per phase).

**5. `Console`** — Streams all agent events (tool calls, results, text responses) to stdout in real time so you can watch the pipeline work.

### How Agents Communicate

Agents **never** see each other's messages. They communicate exclusively through external systems:

```
PM ──creates──► Jira Issue ◄──reads── Developer
                                          │
                                     creates PR
                                          │
Developer ──comments──► Jira      GitHub PR ◄──reviews── Architect
                                          │
                                    review comments
                                          │
Developer (fix) ──reads──► PR reviews ◄──writes── Architect
```

### The Review Loop (Python Orchestration)

The review loop is a simple Python `for` loop — not AutoGen orchestration:

```python
for round_num in range(1, 4):  # max 3 rounds
    # Create FRESH architect (independent context)
    arch = AssistantAgent(name="architect", model_client=gpt4o, ...)
    arch_team = RoundRobinGroupChat([arch], ...)
    arch_result = await Console(arch_team.run_stream(task=f"Review PR #{pr}"))

    if "APPROVED" in arch_result:
        break  # Done!

    # Create FRESH developer (independent context)
    dev = AssistantAgent(name="developer", model_client=gpt4o_mini, ...)
    dev_team = RoundRobinGroupChat([dev], ...)
    await Console(dev_team.run_stream(task=f"Fix review comments on PR #{pr}"))
```

Each iteration creates **new agent instances** — this guarantees the architect reviews the PR fresh each round without memory of previous reviews, and the developer reads the latest review comments without prior context.

### Self-Approval Workaround

GitHub blocks approving your own PR (both agents use the same token). The tools automatically fall back:

```
APPROVE attempt → GitHub 422 error → fallback to COMMENT with "APPROVED" in body
```

The pipeline checks for `"APPROVED"` in the text, so this works seamlessly.

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

### Dependencies

| Package | Purpose |
|---------|---------|
| `autogen-agentchat` | AutoGen v0.4 agent framework |
| `autogen-ext[openai]` | OpenAI model client for AutoGen |
| `tiktoken` | Token counting for OpenAI models |
| `atlassian-python-api` | Jira REST API client |
| `PyGithub` | GitHub REST API client |
| `python-dotenv` | Load `.env` configuration |

---

## Usage

```bash
python main.py
```

### First Run — Interactive Setup

On first run, the CLI prompts for Jira/GitHub configuration and **opens your browser** for SSO authentication when tokens are missing:

```
==========================================================
    Multi-Agent Development Pipeline
==========================================================

  Jira Configuration
  ----------------------------------------
  URL [https://think-up.atlassian.net]:
  User email [vitaly.tarasiuk@thinkup.global]:
  Project key [TUP]:

  Jira API token not found. Opening browser for token creation...
  1. Sign in with SSO if prompted
  2. Click 'Create API token'
  3. Name it (e.g. 'MCP Pipeline') and click Create
  4. Copy the token

  Press Enter to open the browser...
  Paste your Jira API token: ****

  GitHub Configuration
  ----------------------------------------
  Repo (owner/repo) [thinkup-global/api-controller]:
  Base branch [dev]:

  Found token from GitHub CLI (gh).       ← auto-detected

==========================================================

  Enter your requirement:
  > Add logging to the applyCoupon method for inactive promotion codes

==========================================================
  Jira     : https://think-up.atlassian.net (TUP)
  GitHub   : thinkup-global/api-controller (branch: dev)
  Assignee : vitaly.tarasiuk@thinkup.global
==========================================================

  Phase 1 -- Product Manager creating Jira task
  ...
  Phase 2 -- Developer implementing changes
  ...
  Phase 3.1a -- Architect reviewing PR #234
  ...
  ──────────────────────────────────────────────────────
  Architect Review (round 1):
  ──────────────────────────────────────────────────────
  The changes introduce proper logging for inactive promotion codes...
  - Correctness: Aligned with Jira task requirements ✓
  - Completeness: All existing code preserved ✓
  ...
  APPROVED
  ──────────────────────────────────────────────────────

  >>> PR #234 APPROVED by architect

==========================================================
  Pipeline Complete
  Jira : https://think-up.atlassian.net/browse/TUP-4609
  PR   : https://github.com/thinkup-global/api-controller/pull/234
  Status: PR is open -- NOT merged (manual merge required)
==========================================================
```

### Subsequent Runs

All credentials are saved to `.env` (git-ignored). On next run you only confirm the Jira project, GitHub repo, and type your requirement:

```bash
python main.py
```

### Authentication Flow

| Service | How it authenticates |
|---------|---------------------|
| **Jira** | Opens browser → Atlassian SSO → you create an API token → paste it back |
| **GitHub** | Auto-detects `gh` CLI token. If not found: opens browser → GitHub SSO → you create a PAT with `repo` scope → paste it |
| **OpenAI** | Opens browser → OpenAI dashboard → you copy your API key → paste it |

All tokens are stored in `.env` and reused on future runs. You can switch Jira projects or GitHub repos freely — the tokens work across all your projects.

---

## Project Structure

```
MCP-dev-pipline/
├── main.py                  # Interactive CLI — prompts, browser auth, runs pipeline
├── config.py                # Reads .env into a Config dataclass
├── auth.py                  # Browser-based SSO helpers (legacy)
├── pipeline/
│   ├── __init__.py
│   └── dev_pipeline.py      # AutoGen agent orchestration + review loop
├── tools/
│   ├── __init__.py
│   ├── jira_tools.py        # create_jira_issue, get_jira_issue, add_jira_comment
│   └── github_tools.py      # branches, files, PRs, reviews, approve
├── requirements.txt
├── .env.example             # Template for environment variables
├── .env                     # Your credentials (git-ignored, auto-created)
├── .gitignore
└── README.md
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | *(required)* |
| `DEVELOPER_MODEL` | Model for Developer & PM agents | `gpt-4o-mini` |
| `ARCHITECT_MODEL` | Model for Architect agent | `gpt-4o` |
| `PM_MODEL` | Model for PM agent | `gpt-4o-mini` |
| `JIRA_URL` | Your Jira instance URL | *(prompted)* |
| `JIRA_USER` | Your Jira email | *(prompted)* |
| `JIRA_API_TOKEN` | Jira API token | *(browser SSO)* |
| `JIRA_PROJECT_KEY` | Jira project key (e.g. `TUP`) | *(prompted)* |
| `GITHUB_TOKEN` | GitHub personal access token | *(auto/browser)* |
| `GITHUB_REPO` | Target repo as `owner/repo` | *(prompted)* |
| `BASE_BRANCH` | Branch PRs target | `dev` |

### Customizing Models

Edit `.env` to swap models:

```env
DEVELOPER_MODEL=gpt-4o-mini    # cheap & fast for code generation
ARCHITECT_MODEL=gpt-4o          # smart for code review
PM_MODEL=gpt-4o-mini            # cheap for task creation
```

---

## Requirements

- **Python 3.11+**
- **OpenAI API key** — [get one here](https://platform.openai.com/api-keys)
- **Jira API token** — [generate here](https://id.atlassian.com/manage-profile/security/api-tokens)
- **GitHub PAT** with `repo` scope — [create here](https://github.com/settings/tokens/new?scopes=repo), or install [GitHub CLI](https://cli.github.com/) for automatic token detection
