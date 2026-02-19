import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # OpenAI
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Models  (developer = cheap, architect = premium)
    DEVELOPER_MODEL: str = field(default_factory=lambda: os.getenv("DEVELOPER_MODEL", "gpt-4o-mini"))
    ARCHITECT_MODEL: str = field(default_factory=lambda: os.getenv("ARCHITECT_MODEL", "gpt-4o"))
    PM_MODEL: str = field(default_factory=lambda: os.getenv("PM_MODEL", "gpt-4o-mini"))
    SELECTOR_MODEL: str = field(default_factory=lambda: os.getenv("SELECTOR_MODEL", "gpt-4o-mini"))

    # Jira
    JIRA_URL: str = field(default_factory=lambda: os.getenv("JIRA_URL", "https://think-up.atlassian.net"))
    JIRA_USER: str = field(default_factory=lambda: os.getenv("JIRA_USER", "vitaly.tarasiuk@thinkup.global"))
    JIRA_API_TOKEN: str = field(default_factory=lambda: os.getenv("JIRA_API_TOKEN", ""))
    JIRA_PROJECT_KEY: str = field(default_factory=lambda: os.getenv("JIRA_PROJECT_KEY", "TUP"))

    # GitHub
    GITHUB_TOKEN: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    GITHUB_REPO: str = field(default_factory=lambda: os.getenv("GITHUB_REPO", "thinkup-global/api-controller"))
    BASE_BRANCH: str = field(default_factory=lambda: os.getenv("BASE_BRANCH", "dev"))


config = Config()
