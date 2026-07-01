import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure the root backend directory is in the python path for absolute imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent.graph import agent_graph


# ─────────────────────────────────────────────────────────────────
# RUNNER — accepts any code file
# ─────────────────────────────────────────────────────────────────


def run(file_path: str, project_context: str = "", error_log: str = ""):
    """Run the AI-Ops agent on any code file.

    file_path:       path to the file you want analyzed
    project_context: what does this project do (optional but helps)
    error_log:       paste a stack trace here if you have one (optional)
    """

    if not os.path.exists(file_path):
        print(f"❌  File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        raw_code = f.read()

    print("\n" + "=" * 60)
    print("  AI-OPS AGENT — Production Readiness Review")
    print(f"  File  : {file_path}")
    print(f"  Lines : {len(raw_code.splitlines())}")
    print("=" * 60)

    # State parameters aligned across config, nodes, and git clients
    initial_state = {
        "messages": [],
        "raw_code": raw_code,
        "error_log": error_log or "No error — pre-production review",
        "project_context": project_context or "No context provided",
        "file_path": file_path,
        "domain": "",
        "issues": [],  # Unified storage for raw issues found
        "confident_issues": [],  # Handled by confidence threshold splitting
        "flagged_issues": [],  # Tracked for reporting safety
        "current_issue_index": 0,
        "risk_level": "",
        "risk_reasoning": "",
        "proposed_fix": None,  # Dict payload containing the solution snippet
        "human_approved": False,
        "human_feedback": "",
        "test_passed": False,
        "test_output": "",
        "retry_count": 0,
        "pr_url": "",  # Automatically captured from your GitClient flow
        "final_report": "",
    }

    config = {"configurable": {"thread_id": f"review-{os.path.basename(file_path)}"}}

    print("🤖 Invoking graph engine workflow stream...\n")

    try:
        # Loop over the update events emitted by LangGraph as each node completes
        for event in agent_graph.stream(
            initial_state, config=config, stream_mode="updates"
        ):
            for node_name, state_update in event.items():
                print(f"🔷 [Node: {node_name}] has finished execution.")

                # Output visual progression anchors if relevant data updates are passed
                if "issues" in state_update and state_update["issues"]:
                    print(
                        f"   ⚠️  Discovered {len(state_update['issues'])} potential issues."
                    )

                if "pr_url" in state_update and state_update["pr_url"]:
                    print(f"   🚀 Pull Request Created: {state_update['pr_url']}")

    except Exception as e:
        print(f"❌  Graph pipeline execution crashed: {e}")
        sys.exit(1)

    print("\n✅  Analysis complete.")


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# Change file_path to point to any file you want reviewed
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run(
        file_path="your_file.py",  # ← change this to point to your target code file
        project_context=(
            "Describe what your project does here. "
            "Example: LangGraph agent for automated camera configuration (CamConfig-AI)."
        ),
        error_log="",  # ← paste stack trace here if you have one
    )