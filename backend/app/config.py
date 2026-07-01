import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────
# CONFIG SCHEMA
# ─────────────────────────────────────────────────────────────────

@dataclass
class Config:
    # LLM
    groq_api_key: str
    model_name:   str
    temperature:  float
    max_tokens:   int

    # Git — optional, only needed for auto-PR
    github_token:    str
    github_repo:     str    # "owner/repo"
    git_base_branch: str

    # Agent behaviour
    max_retries:      int
    auto_fix_enabled: bool   # if False, ALL fixes require human approval
    min_confidence:   float  # issues below this are flagged only, not auto-fixed


def load_config() -> Config:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set.\n"
            "Add it to your .env file:\n"
            "  GROQ_API_KEY=your_key_here"
        )

    return Config(
        groq_api_key     = key,
        model_name       = os.getenv("MODEL_NAME",       "llama-3.3-70b-versatile"),
        temperature      = float(os.getenv("TEMPERATURE",  "0.1")),
        max_tokens       = int(os.getenv("MAX_TOKENS",     "2048")),
        github_token     = os.getenv("GITHUB_TOKEN",      ""),
        github_repo      = os.getenv("GITHUB_REPO",       ""),
        git_base_branch  = os.getenv("GIT_BASE_BRANCH",   "main"),
        max_retries      = int(os.getenv("MAX_RETRIES",    "3")),
        auto_fix_enabled = os.getenv("AUTO_FIX_ENABLED",  "true").lower() == "true",
        min_confidence   = float(os.getenv("MIN_CONFIDENCE", "0.75")),
    )


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def sort_issues_by_severity(issues: list) -> list:
    """Sort issues so CRITICAL is always fixed first."""
    # Defensive lower() matching handles string variation anomalies safely
    return sorted(
        issues,
        key=lambda x: SEVERITY_ORDER.get(str(x.get("severity", "low")).lower(), 3)
    )


def filter_low_confidence(issues: list, min_confidence: float = 0.75) -> tuple:
    """
    Split issues into:
    - confident: agent will attempt to fix these
    - flagged:   below confidence threshold, reported only
    """
    confident = []
    flagged = []
    
    for i in issues:
        try:
            # Coerce value into valid float comparison metrics securely
            score = float(i.get("confidence_score", 0))
        except (ValueError, TypeError):
            score = 0.0
            
        if score >= min_confidence:
            confident.append(i)
        else:
            flagged.append(i)
            
    return confident, flagged