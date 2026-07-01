from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import (
    router_node,               # NEW
    ai_ops_diagnose_node,      # NEW
    data_ops_diagnose_node,    # NEW
    specialist_node,
    risk_node,
    human_approval_node,
    fix_node,
    test_node,
    next_issue_node,
    report_node,
)

# ─────────────────────────────────────────────────────────────────
# ROUTING FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def route_initial_domain(state: AgentState) -> str:
    """Routes the execution to the appropriate domain-specific agent."""
    domain = state.get("domain", "data_ops")
    if domain == "ai_ops":
        return "ai_ops_diagnose"
    return "data_ops_diagnose"


def route_after_risk(state: AgentState) -> str:
    """After risk assessment: auto-fix, ask human, or go to report."""
    risk = state.get("risk_level", "high")
    if risk == "done":
        return "report"
    if risk == "low":
        return "fix"
    return "human_approval"


def route_after_human(state: AgentState) -> str:
    """After human decision: fix if approved, skip if not."""
    return "fix" if state.get("human_approved") else "next_issue"


def route_after_test(state: AgentState) -> str:
    """After sandbox compiler check: retry fix or move to next issue."""
    if state.get("test_passed"):
        return "next_issue"
    if state.get("retry_count", 0) < 2:
        return "fix"
    return "next_issue"


def route_after_next(state: AgentState) -> str:
    """After advancing index: more issues to process, or done."""
    idx = state.get("current_issue_index", 0)
    total = len(state.get("all_issues", []))
    return "report" if idx >= total else "risk"


# ─────────────────────────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AgentState)

    # ── Register all nodes
    g.add_node("router", router_node)                             # New Routing Module
    g.add_node("ai_ops_diagnose", ai_ops_diagnose_node)           # Isolated AI Specialist
    g.add_node("data_ops_diagnose", data_ops_diagnose_node)       # Isolated Data Specialist
    g.add_node("specialist", specialist_node)
    g.add_node("risk", risk_node)
    g.add_node("human_approval", human_approval_node)
    g.add_node("fix", fix_node)
    g.add_node("test", test_node)
    g.add_node("next_issue", next_issue_node)
    g.add_node("report", report_node)

    # ── Entry path configuration
    g.set_entry_point("router")

    # ── Domain Conditional Routing Link
    g.add_conditional_edges(
        "router",
        route_initial_domain,
        {
            "ai_ops_diagnose": "ai_ops_diagnose",
            "data_ops_diagnose": "data_ops_diagnose"
        }
    )

    # ── Converge streams back into prioritization pipeline
    g.add_edge("ai_ops_diagnose", "specialist")
    g.add_edge("data_ops_diagnose", "specialist")
    
    # ── Linear edges
    g.add_edge("specialist", "risk")
    g.add_edge("fix", "test")
    g.add_edge("report", END)

    # ── Downstream conditional loops
    g.add_conditional_edges(
        "risk",
        route_after_risk,
        {"fix": "fix", "human_approval": "human_approval", "report": "report"},
    )

    g.add_conditional_edges(
        "human_approval", 
        route_after_human, 
        {"fix": "fix", "next_issue": "next_issue"}
    )

    g.add_conditional_edges(
        "test", 
        route_after_test, 
        {"fix": "fix", "next_issue": "next_issue"}
    )

    g.add_conditional_edges(
        "next_issue", 
        route_after_next, 
        {"risk": "risk", "report": "report"}
    )

    # ── Compile with isolated memory tracking
    return g.compile(checkpointer=MemorySaver())


# Thread-safe graph initialization singleton
agent_graph = build_graph()