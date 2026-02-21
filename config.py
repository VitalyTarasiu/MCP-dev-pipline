import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    DEVELOPER_MODEL: str = field(default_factory=lambda: os.getenv("DEVELOPER_MODEL", "gpt-4o-mini"))
    ARCHITECT_MODEL: str = field(default_factory=lambda: os.getenv("ARCHITECT_MODEL", "gpt-4o"))
    PM_MODEL: str = field(default_factory=lambda: os.getenv("PM_MODEL", "gpt-4o-mini"))

    JIRA_URL: str = field(default_factory=lambda: os.getenv("JIRA_URL", ""))
    JIRA_USER: str = field(default_factory=lambda: os.getenv("JIRA_USER", ""))
    JIRA_API_TOKEN: str = field(default_factory=lambda: os.getenv("JIRA_API_TOKEN", ""))
    JIRA_PROJECT_KEY: str = field(default_factory=lambda: os.getenv("JIRA_PROJECT_KEY", ""))

    GITHUB_TOKEN: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    GITHUB_REPO: str = field(default_factory=lambda: os.getenv("GITHUB_REPO", ""))
    BASE_BRANCH: str = field(default_factory=lambda: os.getenv("BASE_BRANCH", "dev"))


def get_config() -> Config:
    """Create a fresh Config reading current environment variables."""
    return Config()


config = Config()
