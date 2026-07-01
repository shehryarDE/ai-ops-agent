from typing import TypedDict, Annotated, Sequence, List, Optional, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class DiagnosisResult(TypedDict):
    issue_type: str           # bug | security | scalability | ai_ops | data_ops
    severity: str             # critical | high | medium | low
    issue_summary: str        # one line — what is wrong
    root_cause: str           # why it fails in production
    affected_snippet: str     # the exact broken code
    affected_components: List[str]
    production_impact: str    # what happens when this hits production
    confidence_score: float   # 0.0 - 1.0


class ProposedFix(TypedDict):
    fix_description: str
    code_before: str
    code_after: str
    files_to_change: List[str]
    test_command: str
    rollback_plan: str


class AgentState(TypedDict):
    # ── INPUT ────────────────────────────────────────────────────
    messages:        Annotated[Sequence[BaseMessage], add_messages]
    raw_code:        str    # the actual code file content — sent to LLM once only
    error_log:       str    # stack trace or error message if any
    project_context: str    # what does this project do
    file_path:       str    # which file this code came from

    # ── ROUTING & SPECIALISTS ────────────────────────────────────
    domain:              Literal["ai_ops", "data_ops", "undetermined"]  # Strict type router targeting
    all_issues:          List[DiagnosisResult]  # items generated from specialized diagnostic loops
    current_issue_index: int                    # tracking for map/reduce style evaluation index

    # ── RISK ASSESSMENT ──────────────────────────────────────────
    risk_level:     str   # low | high | done
    risk_reasoning: str   # why this risk level was assigned

    # ── CODE FIX ENGINE ──────────────────────────────────────────
    proposed_fix:   Optional[ProposedFix]
    human_approved: bool
    human_feedback: str

    # ── IN-MEMORY SANDBOX TESTING ────────────────────────────────
    test_passed: bool
    test_output: str
    retry_count: int

    # ── SUMMARY PIPELINE OUTPUT ──────────────────────────────────
    final_report: str