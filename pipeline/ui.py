"""Rich terminal UI for the Multi-Agent Development Pipeline.

Provides a colored architecture diagram, progress tracking, clean
tool-call logs, and a custom AutoGen console handler — designed for
executive demos where readability and visual flow matter.
"""

from __future__ import annotations

import json
from typing import Any


# ── ANSI escape codes ──────────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BLUE   = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN   = "\033[36m"
    WHITE  = "\033[37m"
    GRAY   = "\033[90m"
    BR_RED = "\033[91m"
    BR_GREEN = "\033[92m"
    BR_YELLOW = "\033[93m"
    BR_BLUE = "\033[94m"
    BR_MAGENTA = "\033[95m"
    BR_CYAN = "\033[96m"
    BR_WHITE = "\033[97m"


# ── Phase constants ────────────────────────────────────────────────

PM   = "pm"
DEV  = "dev"
ARCH = "arch"
FIX  = "fix"
DONE = "done"

PHASE_META = {
    PM:   {"label": "Product Manager",  "short": "PM",   "color": C.BR_CYAN},
    DEV:  {"label": "Developer",        "short": "DEV",  "color": C.BR_BLUE},
    ARCH: {"label": "Architect Review", "short": "ARCH", "color": C.BR_YELLOW},
    FIX:  {"label": "Developer Fix",    "short": "FIX",  "color": C.BR_MAGENTA},
    DONE: {"label": "Complete",         "short": "DONE", "color": C.BR_GREEN},
}

AGENT_COLORS = {
    "product_manager": C.BR_CYAN,
    "developer":       C.BR_BLUE,
    "architect":       C.BR_YELLOW,
}


# ── Tool output summarization ─────────────────────────────────────

def _summarize_args(name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except Exception:
        return ""

    if name == "get_file_content":
        return args.get("file_path", "")
    if name == "get_repo_tree":
        return args.get("path", "") or "/"
    if name == "create_branch":
        return args.get("branch_name", "")
    if name == "create_or_update_file":
        path = args.get("file_path", "")
        lines = args.get("content", "").count("\n") + 1
        return f"{path} ({lines} lines)"
    if name == "create_pull_request":
        return args.get("title", "")[:60]
    if name == "create_jira_issue":
        return args.get("summary", "")[:60]
    if name == "get_jira_issue":
        return args.get("issue_key", "")
    if name == "add_jira_comment":
        return args.get("issue_key", "")
    if name == "add_pr_review":
        return args.get("event", "COMMENT")
    if name in (
        "get_pr_diff", "get_pr_files", "get_pr_reviews",
        "get_pr_review_comments", "approve_pull_request",
    ):
        return f"PR #{args.get('pr_number', '?')}"
    return ""


def _summarize_result(name: str, result: str) -> str:
    if not result:
        return "(empty)"
    if name == "get_repo_tree":
        lines = [l for l in result.split("\n") if l.strip()]
        dirs  = sum(1 for l in lines if "[DIR]" in l)
        files = sum(1 for l in lines if "[FILE]" in l)
        return f"Found {files} files, {dirs} directories"
    if name == "get_file_content":
        if result.startswith("Error"):
            return result[:80]
        return f"Read {result.count(chr(10)) + 1} lines"
    if name == "get_pr_diff":
        return f"Diff retrieved ({result.count(chr(10)) + 1} lines)"
    if name == "get_pr_reviews":
        return f"{result.count('Reviewer:')} review(s) found"
    if name == "get_pr_review_comments":
        c = result.count("File:")
        return f"{c} inline comment(s)" if c else result.split("\n")[0][:80]
    if name == "get_pr_files":
        c = len([l for l in result.split("\n") if l.strip()])
        return f"{c} file(s) changed"

    one_line = result.replace("\n", " ").strip()
    return (one_line[:120] + "...") if len(one_line) > 120 else one_line


# ── PipelineUI ─────────────────────────────────────────────────────

class PipelineUI:

    def __init__(self) -> None:
        self.completed: set[str] = set()
        self.current: str | None = None
        self._call_names: dict[str, str] = {}

    # ── Header ──────────────────────────────────────────

    def show_header(
        self, jira_url: str, github_repo: str, base_branch: str, jira_user: str,
    ) -> None:
        w = 60
        bar = "═" * w
        r = C.RESET
        print()
        print(f"  {C.BR_CYAN}{C.BOLD}{bar}{r}")
        print(f"  {C.BR_CYAN}{C.BOLD}{'MULTI-AGENT DEVELOPMENT PIPELINE':^{w}}{r}")
        print(f"  {C.BR_CYAN}{C.BOLD}{bar}{r}")
        print(f"  {C.GRAY}  Jira     : {jira_url}{r}")
        print(f"  {C.GRAY}  GitHub   : {github_repo}  (base: {base_branch}){r}")
        print(f"  {C.GRAY}  Assignee : {jira_user}{r}")
        print()

    # ── Architecture diagram ────────────────────────────

    def show_architecture(self, highlight: str | None = None) -> None:
        def _c(phase: str) -> str:
            if phase == highlight:
                return PHASE_META[phase]["color"] + C.BOLD
            if phase in self.completed:
                return C.GREEN
            return C.GRAY

        r  = C.RESET
        g  = C.GRAY
        p1 = _c(PM)
        p2 = _c(DEV)
        p3 = _c(ARCH)
        pf = _c(FIX)
        pd = _c(DONE)

        print(
            f"    {p1}┌──────────────────────────────────┐{r}\n"
            f"    {p1}│  Phase 1 ─ Product Manager       │{r}  {g}Creates Jira task{r}\n"
            f"    {p1}└────────────────┬─────────────────┘{r}\n"
            f"    {g}                 │ Jira ticket{r}\n"
            f"    {p2}┌────────────────▼─────────────────┐{r}\n"
            f"    {p2}│  Phase 2 ─ Developer             │{r}  {g}Implements code, creates PR{r}\n"
            f"    {p2}└────────────────┬─────────────────┘{r}\n"
            f"    {g}                 │ Pull Request{r}\n"
            f"    {p3}┌────────────────▼─────────────────┐{r}\n"
            f"    {p3}│  Phase 3a ─ Architect Review     │{r}  {g}Reviews code quality{r}\n"
            f"    {p3}└───────┬─────────────────┬────────┘{r}\n"
            f"    {C.GREEN}    APPROVED{r}          {C.BR_YELLOW}CHANGES_REQUESTED{r}\n"
            f"    {C.GREEN}        │{r}                   {C.BR_YELLOW}│{r}\n"
            f"    {C.GREEN}        │{r}          {pf}┌────────▼─────────┐{r}\n"
            f"    {C.GREEN}        │{r}          {pf}│ Phase 3b ─ Fix   │{r}  {g}Fixes review issues{r}\n"
            f"    {C.GREEN}        │{r}          {pf}└────────┬─────────┘{r}\n"
            f"    {C.GREEN}        │{r}          {g}         └──▶ loop (max 3){r}\n"
            f"    {pd}┌───────▼──────────────────────────┐{r}\n"
            f"    {pd}│  Pipeline Complete               │{r}  {g}PR open — manual merge{r}\n"
            f"    {pd}└──────────────────────────────────┘{r}"
        )
        print()

    # ── Progress bar ────────────────────────────────────

    def _progress_bar(self, current: str, show_fix: bool = False) -> None:
        phases = [PM, DEV, ARCH]
        if show_fix:
            phases.append(FIX)
        phases.append(DONE)

        parts = []
        for p in phases:
            meta = PHASE_META[p]
            if p == current:
                parts.append(f"{meta['color']}{C.BOLD}◉ {meta['short']}{C.RESET}")
            elif p in self.completed:
                parts.append(f"{C.GREEN}● {meta['short']}{C.RESET}")
            else:
                parts.append(f"{C.GRAY}○ {meta['short']}{C.RESET}")

        print(f"    {f' {C.GRAY}────{C.RESET} '.join(parts)}")
        print()

    # ── Phase transitions ───────────────────────────────

    def phase_start(
        self, phase: str, model: str, round_num: int = 0,
    ) -> None:
        self.current = phase
        meta  = PHASE_META[phase]
        color = meta["color"]
        label = meta["label"]
        if round_num > 0:
            label += f"  (round {round_num}/3)"

        show_fix = phase == FIX or FIX in self.completed

        print()
        print(f"  {color}{C.BOLD}{'━' * 60}{C.RESET}")
        print(f"  {color}{C.BOLD}  ▶ {label}{C.RESET}")
        print(f"  {color}    Model: {model}  │  Context: independent{C.RESET}")
        print(f"  {color}{C.BOLD}{'━' * 60}{C.RESET}")
        print()
        self._progress_bar(phase, show_fix)
        self.show_architecture(phase)

    def phase_end(self, phase: str) -> None:
        self.completed.add(phase)
        meta = PHASE_META[phase]
        print(f"\n  {C.GREEN}  ✓ {meta['label']} completed{C.RESET}\n")

    # ── Context passing between agents ──────────────────

    def context_arrow(self, label: str, value: str) -> None:
        print(f"  {C.BR_WHITE}{C.BOLD}  ──▶ {label}: {value}{C.RESET}\n")

    # ── Tool call activity ──────────────────────────────

    def tool_call(self, agent: str, call_id: str, name: str, brief_args: str) -> None:
        self._call_names[call_id] = name
        print(f"    {C.GRAY}⚡ {name}({brief_args}){C.RESET}", flush=True)

    def tool_result(self, call_id: str, result: str) -> None:
        name = self._call_names.pop(call_id, "")
        summary = _summarize_result(name, result)
        if "error" in summary.lower():
            print(f"    {C.RED}✗ {summary}{C.RESET}")
        else:
            print(f"    {C.GREEN}✓ {summary}{C.RESET}")

    # ── Agent text messages ─────────────────────────────

    def agent_message(self, agent: str, text: str) -> None:
        clean = (
            text.replace("PHASE_COMPLETE", "")
                .replace("CHANGES_REQUESTED", "")
                .strip()
        )
        if not clean:
            return

        color = AGENT_COLORS.get(agent, C.WHITE)
        lines = clean.split("\n")
        max_show = 10

        print()
        print(f"    {color}{C.BOLD}{agent}:{C.RESET}")
        for line in lines[:max_show]:
            print(f"    {color}{line}{C.RESET}")
        if len(lines) > max_show:
            print(f"    {C.GRAY}... ({len(lines) - max_show} more lines){C.RESET}")
        print()

    # ── Architect review verdict ────────────────────────

    def review_verdict(self, text: str, approved: bool) -> None:
        print()
        if approved:
            c = C.BR_GREEN
            label = "P R   A P P R O V E D"
            icon  = "✓"
        else:
            c = C.BR_YELLOW
            label = "C H A N G E S   R E Q U E S T E D"
            icon  = "↻"

        w = 50
        print(f"  {c}{C.BOLD}  ╔{'═' * w}╗{C.RESET}")
        print(f"  {c}{C.BOLD}  ║{f'{icon}  {label}':^{w}}║{C.RESET}")
        print(f"  {c}{C.BOLD}  ╚{'═' * w}╝{C.RESET}")

        lines = text.strip().split("\n")
        for line in lines[:12]:
            clean = line.replace("APPROVED", "").replace("CHANGES_REQUESTED", "").strip()
            if clean:
                print(f"    {C.DIM}{clean}{C.RESET}")
        if len(lines) > 12:
            print(f"    {C.GRAY}... ({len(lines) - 12} more lines){C.RESET}")
        print()

    # ── Final summary ───────────────────────────────────

    def show_summary(
        self, jira_url: str, jira_key: str, github_repo: str, pr_number: int,
    ) -> None:
        self.current = DONE
        self.completed.add(DONE)

        r = C.RESET
        w = 60
        print()
        print(f"  {C.BR_GREEN}{C.BOLD}{'═' * w}{r}")
        print(f"  {C.BR_GREEN}{C.BOLD}{'PIPELINE COMPLETE':^{w}}{r}")
        print(f"  {C.BR_GREEN}{C.BOLD}{'═' * w}{r}")
        print()
        print(f"    {C.BR_WHITE}Jira : {jira_url}/browse/{jira_key}{r}")
        print(f"    {C.BR_WHITE}PR   : https://github.com/{github_repo}/pull/{pr_number}{r}")
        print(f"    {C.BR_YELLOW}Status: PR is open — NOT merged (manual merge required){r}")
        print()
        self._progress_bar(DONE, FIX in self.completed)
        self.show_architecture(DONE)


# ── Custom console (replaces AutoGen's Console) ───────────────────

async def pretty_console(stream: Any, ui: PipelineUI) -> Any:
    """Consume an AutoGen run_stream(), printing clean activity logs.

    Returns the TaskResult (same contract as autogen_agentchat.ui.Console).
    """
    from autogen_agentchat.base import TaskResult

    result = None
    async for msg in stream:
        if isinstance(msg, TaskResult):
            result = msg
            continue

        source  = getattr(msg, "source", "")
        content = getattr(msg, "content", "")

        if isinstance(content, str) and content.strip():
            ui.agent_message(source, content)
        elif isinstance(content, list):
            for item in content:
                if hasattr(item, "name") and hasattr(item, "arguments"):
                    call_id = getattr(item, "id", "")
                    brief   = _summarize_args(item.name, item.arguments)
                    ui.tool_call(source, call_id, item.name, brief)
                elif hasattr(item, "call_id") and hasattr(item, "content"):
                    ui.tool_result(item.call_id, item.content)

    return result
