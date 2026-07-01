import io
import sys
import json
import subprocess
from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AgentState
from .prompts import (
    SYSTEM_PROMPT,
    ROUTER_PROMPT,             
    AI_OPS_DIAGNOSE_PROMPT,    
    DATA_OPS_DIAGNOSE_PROMPT,  
    SPECIALIST_PROMPT,
    RISK_PROMPT,
    FIX_PROMPT,
    TEST_PROMPT,
    REPORT_PROMPT,
    build_issues_summary,
    build_fix_summary,
)
from ..config import load_config, sort_issues_by_severity, filter_low_confidence

# Import bound specialized tools and routers
from .tools import (
    llm, 
    llm_router, 
    llm_ai_specialist, 
    llm_data_specialist, 
    llm_risk, 
    llm_fix, 
    llm_test
)

_cfg = load_config()


# ─────────────────────────────────────────────────────────────────
# HELPER — extract tool call results from LLM response
# ─────────────────────────────────────────────────────────────────
def _extract(response) -> list[dict]:
    """Pull all tool call args from an LLM response."""
    results = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            try:
                args = tc["args"]
                if isinstance(args, str):
                    args = json.loads(args)
                results.append(args)
            except Exception:
                pass
    return results


# ─────────────────────────────────────────────────────────────────
# NODE 0 — SYSTEM DOMAIN ROUTER (NEW)
# ─────────────────────────────────────────────────────────────────
def router_node(state: AgentState) -> dict:
    """Evaluates project context metadata to route execution paths."""
    print("\n🔀 [ROUTER] Inspecting system architecture and context...")
    
    router_prompt = """You are the Lead Systems Architect. Inspect the codebase characteristics and assign the correct operational specialist group.
    
    FILE: {file_path}
    CONTEXT: {project_context}
    ERROR: {error_log}
    
    CRITERIA:
    - Target 'ai_ops' for agentic loops, prompt tracking, LangGraph states, LLM parameters, or vector lookups.
    - Target 'data_ops' for ETL pipelines, batch engines, unclosed resource handlers, memory constraints, or Spark jobs."""
    
    formatted = router_prompt.format(
        file_path=state.get("file_path", "unknown"),
        project_context=state.get("project_context", "No context provided"),
        error_log=state.get("error_log", "No error — pre-production review")
    )
    
    response = llm_router.invoke([
        SystemMessage(content="You are a system metadata orchestrator routing incoming tasks to optimized code developers."),
        HumanMessage(content=formatted)
    ])
    
    extracted = _extract(response)
    domain_assignment = extracted[0].get("domain", "data_ops") if extracted else "data_ops"
    
    print(f"    Selected Specialist Domain ➔ [{domain_assignment.upper()}]")
    return {
        "domain": domain_assignment,
        "messages": [response]
    }


# ─────────────────────────────────────────────────────────────────
# NODE 1a — AI OPS TARGETED DIAGNOSE (NEW)
# ─────────────────────────────────────────────────────────────────
def ai_ops_diagnose_node(state: AgentState) -> dict:
    print("\n🔍 [AI-OPS DIAGNOSE] Scanning for infinite loops, rate limits, and context overflows...")

    # FIX: Swapped to domain-specific prompt configuration
    prompt = AI_OPS_DIAGNOSE_PROMPT.format(
        file_path=state.get("file_path", "unknown"),
        project_context=state.get("project_context", "No context provided"),
        error_log=state.get("error_log", "No error — pre-production review"),
        raw_code=state.get("raw_code", ""),
    )

    response = llm_ai_specialist.invoke([
        SystemMessage(content=SYSTEM_PROMPT), 
        HumanMessage(content=prompt)
    ])

    issues = sort_issues_by_severity(_extract(response))
    print(f"    AI-Ops Audit Completed | Identified Issues: {len(issues)}")
    for iss in issues:
        print(f"    ├─ [{iss.get('severity', '?').upper()}] {iss.get('issue_summary', '?')[:70]}")

    return {
        "all_issues": issues,
        "current_issue_index": 0,
        "messages": [response],
    }
# ─────────────────────────────────────────────────────────────────
# NODE 1b — DATA OPS TARGETED DIAGNOSE (NEW)
def data_ops_diagnose_node(state: AgentState) -> dict:
    print("\n🔍 [DATA-OPS DIAGNOSE] Scanning for resource leakage, pipeline idling, and OOM profiles...")

    # FIX: Swapped to domain-specific prompt configuration
    prompt = DATA_OPS_DIAGNOSE_PROMPT.format(
        file_path=state.get("file_path", "unknown"),
        project_context=state.get("project_context", "No context provided"),
        error_log=state.get("error_log", "No error — pre-production review"),
        raw_code=state.get("raw_code", ""), # Defensive extraction fallback
    )

    response = llm_data_specialist.invoke([
        SystemMessage(content=SYSTEM_PROMPT), 
        HumanMessage(content=prompt)
    ])

    issues = sort_issues_by_severity(_extract(response))
    print(f"    Data-Ops Audit Completed | Identified Issues: {len(issues)}")
    for iss in issues:
        print(f"    ├─ [{iss.get('severity', '?').upper()}] {iss.get('issue_summary', '?')[:70]}")

    return {
        "all_issues": issues,
        "current_issue_index": 0,
        "messages": [response],
    }
# ─────────────────────────────────────────────────────────────────
# NODE 2 — SPECIALIST CRITERIA RE-RANKER
# ─────────────────────────────────────────────────────────────────
def specialist_node(state: AgentState) -> dict:
    print(f"\n🧠 [SPECIALIST] Applying {state.get('domain', '?').upper()} deep filters...")

    prompt = SPECIALIST_PROMPT.format(
        domain=state.get("domain", "general"),
        issues_summary=build_issues_summary(state.get("all_issues", [])),
    )

    response = llm_data_specialist.invoke([
        SystemMessage(content=SYSTEM_PROMPT), 
        HumanMessage(content=prompt)
    ])

    new_issues = _extract(response)
    all_issues = sort_issues_by_severity(state.get("all_issues", []) + new_issues)
    confident, flagged = filter_low_confidence(all_issues, _cfg.min_confidence)

    MAX_ISSUES_PER_RUN = 3
    if len(confident) > MAX_ISSUES_PER_RUN:
        print(f"    ⚠️  Capping processing queue to top {MAX_ISSUES_PER_RUN} issues to optimize rate budgets.")
        confident = confident[:MAX_ISSUES_PER_RUN]

    print(f"    Queue Processing Sequence: {len(confident)} High-Confidence Targets.")
    return {
        "all_issues": confident,
        "messages": [response],
    }


# ─────────────────────────────────────────────────────────────────
# NODE 3 — RISK EVALUATION
# ─────────────────────────────────────────────────────────────────
def risk_node(state: AgentState) -> dict:
    issues = state.get("all_issues", [])
    idx = state.get("current_issue_index", 0)

    if idx >= len(issues):
        return {"risk_level": "done"}

    current = issues[idx]
    print(f"\n⚖️  [RISK] Assessing Vulnerability Profile {idx+1}/{len(issues)}: {current.get('issue_summary', '?')[:60]}...")

    if current.get("issue_type") in ("security", "prompt_injection"):
        print("    Security exception detected ➔ Enforcement Level Set to HIGH")
        return {
            "risk_level": "high",
            "risk_reasoning": "Security profiles are blocked from execution and always require engineer override.",
        }

    if not _cfg.auto_fix_enabled:
        return {
            "risk_level": "high",
            "risk_reasoning": "Global config override: auto_fix_enabled=False.",
        }

    prompt = RISK_PROMPT.format(
        issue_summary=current.get("issue_summary", ""),
        root_cause=current.get("root_cause", ""),
        fix_summary=f"Patch {current.get('issue_type', '?')} block inside components.",
    )

    response = llm_risk.invoke([
        SystemMessage(content=SYSTEM_PROMPT), 
        HumanMessage(content=prompt)
    ])

    results = _extract(response)
    risk_data = results[0] if results else {"risk_level": "high", "risk_reasoning": "Assessment error fallback."}

    print(f"    Risk Metric: {risk_data.get('risk_level', '?').upper()} ➔ {risk_data.get('risk_reasoning', '?')[:80]}")
    return {
        "risk_level": risk_data.get("risk_level", "high"),
        "risk_reasoning": risk_data.get("risk_reasoning", ""),
        "messages": [response],
    }


# ─────────────────────────────────────────────────────────────────
# NODE 4a — ENGINEER INTERACTIVE INTERACTION
# ─────────────────────────────────────────────────────────────────
def human_approval_node(state: AgentState) -> dict:
    issues = state.get("all_issues", [])
    idx = state.get("current_issue_index", 0)
    current = issues[idx]

    print("\n" + "=" * 60)
    print("🚨  HUMAN APPROVAL REQUIRED (GRAPH IDLE)")
    print("=" * 60)
    print(f"  Issue Summary : {current.get('issue_summary', '?')}")
    print(f"  Severity Rank : {current.get('severity', '?').upper()}")
    print(f"  Vulnerability : {current.get('issue_type', '?')}")
    print(f"  Risk Profile  : {state.get('risk_reasoning', '?')}")
    print("=" * 60)

    try:
        decision = input("  Authorize automation fix generation? (yes / no / skip) ➔ ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        decision = "skip"

    if decision == "yes":
        return {"human_approved": True, "human_feedback": ""}
    elif decision == "skip":
        return {"human_approved": False, "human_feedback": "Skipped by deployment engineer"}
    else:
        try:
            feedback = input("  Provide alternative steering guidance ➔ ").strip()
        except (EOFError, KeyboardInterrupt):
            feedback = "Rejected"
        return {"human_approved": False, "human_feedback": feedback}


# ─────────────────────────────────────────────────────────────────
# NODE 4b — CODE PATCH REPAIR ENGINE
# ───────────
def fix_node(state: AgentState) -> dict:
    current_idx = state.get("current_issue_index", 0)
    issues = state.get("all_issues", [])
    
    if current_idx >= len(issues):
        print("✅ No more issues left in the processing queue.")
        return state
        
    current_issue = issues[current_idx]
    print(f"\n🔧 [FIX ENGINE] Repairing target block: {current_issue.get('issue_summary', '')[:70]}...")

    # Format the updated instruction layout
    prompt = FIX_PROMPT.format(
        issue_summary=current_issue.get("issue_summary", ""),
        root_cause=current_issue.get("root_cause", ""),
        raw_code=state.get("raw_code", ""),
        file_path=state.get("file_path", "unknown")
    )

    response = llm_fix.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    tool_calls = _extract(response)
    if not tool_calls:
        print("❌ No valid fix payload structure generated by the LLM.")
        return {**state, "test_passed": False, "test_output": "Failed tool payload parsing extraction."}

    fix_data = tool_calls[0]
    print(f"    Fix Manifest: {fix_data.get('fix_description', 'Applying patched files layout')}")

    # Extract the unified code string or fall back gracefully to old properties
    updated_code = fix_data.get("updated_full_code") or fix_data.get("code_after")

    if not updated_code:
        print("❌ Repaired source target block returned empty.")
        return {**state, "test_passed": False, "test_output": "Empty patch data schema mapping payload."}

    # Safely modify the source file in place inside your workspace environment
    try:
        # 🛠️ AUTO-CREATE FILE PARENT DIRECTORIES IF THEY ARE MISSING
        dir_name = os.path.dirname(state["file_path"])
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(state["file_path"], "w", encoding="utf-8") as f:
            f.write(updated_code)
            
    except Exception as e:
        print(f"❌ Core disk file writer subsystem error: {e}")
        # Increment retry_count on disk failure to let LangGraph break loops gracefully
        return {
            **state, 
            "test_passed": False, 
            "test_output": f"Disk Write Failure: {str(e)}",
            "retry_count": state.get("retry_count", 0) + 1
        }

    return {
        **state,
        "proposed_fix": fix_data,
        "messages": state.get("messages", []) + [response],
        "test_command": fix_data.get("test_command", f"python -m py_compile {state['file_path']}")
    }

# ─────────────────────────────────────────────────────────────────
# NODE 5 — IN-MEMORY COMPILER SANDBOX (SWE-BENCH UPGRADE)
# ─────────────────────────────────────────────────────────────────
def test_node(state: AgentState) -> dict:
    fix = state.get("proposed_fix")
    if not fix or not fix.get("code_after"):
        return {"test_passed": False, "test_output": "Aborted: Patch code vector string empty."}

    print(f"\n🧪 [SANDBOX TEST] Executing abstract AST compilation verification...")
    
    # Extract raw generation block to test directly in memory
    patch_target_string = fix["code_after"]

    # In-Memory Isolation compilation to eliminate file-not-found system dependencies
    try:
        compile(patch_target_string, filename="<sandbox_patch_validation>", mode="exec")
        test_passed = True
        test_output = "Compilation Success: Abstract structural integrity verified. Code contains no syntax anomalies."
    except SyntaxError as e:
        test_passed = False
        test_output = f"AST Compiler Failure: SyntaxError on line {e.lineno} -> {e.msg}\nFaulty line: {e.text}"
    except Exception as e:
        test_passed = False
        test_output = f"Sandbox Exception: Engine failure during execution parse -> {str(e)}"

    print(f"    {'✅ COMPILATION PASSED' if test_passed else '❌ COMPILATION FAILED'}")

    issues = state.get("all_issues", [])
    idx = state.get("current_issue_index", 0)
    current = issues[idx] if idx < len(issues) else {}

    # Trigger optional repository syncs if valid
    if test_passed and _cfg.github_token and _cfg.github_repo:
        try:
            from ..utils.git_client import apply_and_commit
            pr_url = apply_and_commit(
                proposed_fix=fix,
                diagnosis=current,
                test_passed=test_passed,
                github_token=_cfg.github_token,
                github_repo=_cfg.github_repo,
                base_branch=_cfg.git_base_branch,
            )
            if pr_url:
                print(f"    🔗 Automation PR Created successfully: {pr_url}")
        except Exception as git_err:
            print(f"    ⚠️  Git lifecycle automated push skipped: {str(git_err)}")

    return {
        "test_passed": test_passed,
        "test_output": test_output,
        "retry_count": state.get("retry_count", 0) + (0 if test_passed else 1),
    }


# ─────────────────────────────────────────────────────────────────
# NODE 6 — ITERATION TRACKER
# ─────────────────────────────────────────────────────────────────
def next_issue_node(state: AgentState) -> dict:
    next_idx = state.get("current_issue_index", 0) + 1
    total = len(state.get("all_issues", []))

    if next_idx < total:
        print(f"\n➡️  [ITERATION NEXT] Index updated. Transitioning to processing queue {next_idx + 1}/{total}")
    else:
        print("\n✅ [ITERATION COMPLETE] Target backlog completely evaluated.")

    return {
        "current_issue_index": next_idx,
        "proposed_fix": None,
        "risk_level": "",
        "risk_reasoning": "",
        "test_passed": False,
        "test_output": "",
        "retry_count": 0,
        "human_approved": False,
        "human_feedback": "",
    }


# ─────────────────────────────────────────────────────────────────
# NODE 7 — POST-MORTEM SUMMARY GENERATOR
# ─────────────────────────────────────────────────────────────────
def report_node(state: AgentState) -> dict:
    print("\n📋 [REPORT ENGINE] Processing diagnostic summaries...")

    prompt = REPORT_PROMPT.format(
        issues_summary=build_issues_summary(state.get("all_issues", [])),
        fix_summary=build_fix_summary(state.get("proposed_fix") or {}),
        test_result="VERIFIED PASSED" if state.get("test_passed") else "EVALUATION FAILED / SKIPPED",
        human_feedback=state.get("human_feedback") or "System Pipeline Automation (No Intervention Required)",
    )

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT), 
        HumanMessage(content=prompt)
    ])

    print("\n" + "=" * 60)
    print(response.content)
    print("=" * 60)

    return {
        "final_report": response.content,
        "messages": [response],
    }