import os
import json
from typing import List, Literal
from langchain_groq import ChatGroq
from langchain_core.tools import StructuredTool

# ── LLM Core Instance ───────────────────────────────────────────
api_key = "gsk_YOUR_ACTUAL_LONG_KEY_HERE"

llm = ChatGroq(
    model="llama-3.3-70b-versatile", 
    api_key=api_key
)

# ── Function Blueprints ─────────────────────────────────────────

def route_domain_fn(domain: Literal["ai_ops", "data_ops"], reasoning: str) -> str:
    """Assigns the target operational specialist domain based on code properties."""
    return json.dumps({"domain": domain, "reasoning": reasoning})


def diagnose_issue_fn(
    issue_type: str,
    severity: Literal["critical", "high", "medium", "low"],
    issue_summary: str,
    root_cause: str,
    affected_snippet: str,
    affected_components: List[str],
    production_impact: str,
    confidence_score: float,
) -> str:
    """Records a diagnosed production issue found in the code."""
    return json.dumps({
        "issue_type": issue_type,
        "severity": severity,
        "issue_summary": issue_summary,
        "root_cause": root_cause,
        "affected_snippet": affected_snippet,
        "affected_components": affected_components,
        "production_impact": production_impact,
        "confidence_score": confidence_score,
    })


def risk_assessor_fn(risk_level: Literal["low", "high"], risk_reasoning: str, reversible: str, side_effects: str) -> str:
    """Classifies fix risk as low (auto-apply) or high (human approval)."""
    is_reversible = str(reversible).lower() in ("true", "1", "yes")
    return json.dumps({
        "risk_level": risk_level,
        "risk_reasoning": risk_reasoning,
        "reversible": is_reversible,
        "side_effects": side_effects,
    })


def generate_fix_fn(
    fix_description: str,
    updated_full_code: str,
    files_to_change: List[str],
    test_command: str,
    rollback_plan: str,
) -> str:
    """Generates the repaired version of the target code file."""
    return json.dumps({
        "fix_description": fix_description,
        "updated_full_code": updated_full_code,
        "files_to_change": files_to_change,
        "test_command": test_command,
        "rollback_plan": rollback_plan,
    })


def test_fix_fn(passed: bool, reason: str, should_retry: bool, retry_suggestion: str) -> str:
    """Records the result of testing the applied fix."""
    return json.dumps({
        "passed": passed,
        "reason": reason,
        "should_retry": should_retry,
        "retry_suggestion": retry_suggestion,
    })


# ── Explicit Structural Tool Construction ───────────────────────
# This completely bypasses decorator framework initialization bugs
route_domain = StructuredTool.from_function(func=route_domain_fn, name="route_domain")
diagnose_issue = StructuredTool.from_function(func=diagnose_issue_fn, name="diagnose_issue")
risk_assessor = StructuredTool.from_function(func=risk_assessor_fn, name="risk_assessor")
generate_fix = StructuredTool.from_function(func=generate_fix_fn, name="generate_fix")
test_fix = StructuredTool.from_function(func=test_fix_fn, name="test_fix")


# ── Specialized Agent Model Bindings (Synchronized) ─────────────
llm_router = llm.bind_tools([route_domain], tool_choice="route_domain")
llm_ai_specialist = llm.bind_tools([diagnose_issue])
llm_data_specialist = llm.bind_tools([diagnose_issue])
llm_risk = llm.bind_tools([risk_assessor])
llm_fix = llm.bind_tools([generate_fix])
llm_test = llm.bind_tools([test_fix])