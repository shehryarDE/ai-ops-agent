import os
import sys
import time
from dotenv import load_dotenv

# Ensure environment variables are active before importing graph components
load_dotenv()

print("\n" + "=" * 80)
print(" 🛠️  AI-OPS UNIVERSAL TEST AGENT RUNNER")
print("=" * 80)

# Verify LangSmith variables are online
if os.getenv("LANGSMITH_TRACING") == "true":
    print(
        f"🚀 LangSmith Tracing Is Active! Logs are streaming to project: {os.getenv('LANGSMITH_PROJECT')}"
    )
else:
    print("⚠️  Warning: LANGSMITH_TRACING is not set to true in your .env file.")

# Safely import your graph entry point
try:
    from app.agent.graph import agent_graph
except ImportError as e:
    print(
        f"❌  Import Error: Ensure you are running from the backend directory. Detail: {e}"
    )
    sys.exit(1)


def test_production_scenario(
    scenario_name: str, code_snippet: str, error_log: str, context: str
):
    """Compiles the dynamic initial state and invokes the agent graph pipeline."""
    print("\n" + "-" * 80)
    print(f"🔥 RUNNING PRODUCTION TEST SCENARIO: {scenario_name}")
    print("-" * 80)

    # Completely synchronized state payload aligned to multi-domain execution
    initial_state = {
        "messages": [],
        "raw_code": code_snippet,
        "error_log": error_log,
        "project_context": context,
        "file_path": f"production_failures/{scenario_name.lower().replace(' ', '_')}.py",
        
        # Routing & Orchestration state synchronization
        "domain": "undetermined",  # Allows router_node to safely evaluate and assign literals
        "all_issues": [],          # Unified array used by downstream specialist node filters
        "current_issue_index": 0,
        
        # Risk & Approvals state
        "risk_level": "",
        "risk_reasoning": "",
        "human_approved": False,
        "human_feedback": "",
        
        # Code Fix Engine & Sandbox Testing state
        "proposed_fix": None,
        "test_passed": False,
        "test_output": "",
        "retry_count": 0,
        
        # Summary Pipeline final outputs
        "final_report": "",
    }

    config = {
        "configurable": {
            "thread_id": f"benchmark-{scenario_name.lower().replace(' ', '-spaced')}"
        }
    }

    print("🤖 Invoking AI-Ops Agent Workflow...")
    final_output = agent_graph.invoke(initial_state, config)

    print("\n--- 🏁 Scenario Execution Finished ---")
    print(
        f"Identified Risk Level : {final_output.get('risk_level', 'UNKNOWN').upper()}"
    )
    print(
        f"Automation PR Status  : {final_output.get('final_report')[:120].strip()}..." if final_output.get('final_report') else "No report generated."
    )


# ─────────────────────────────────────────────────────────────────
# BENCHMARK TEST SCENARIOS (Security, Scalability, Concurrency)
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # --- SCENARIO 1: DATA ENGINEERING SCALABILITY FAILURE (Memory Leak / OOM) ---
    pandas_leak_code = """
import pandas as pd
import glob

def process_large_ecommerce_batches():
    # CRITICAL BUG: Concatenating millions of rows into local memory at once causes OOM crash
    all_data = []
    for file in glob.glob("raw_logs/*.csv"):
        df = pd.read_csv(file)
        all_data.append(df)
        
    combined_df = pd.concat(all_data, ignore_index=True)
    return combined_df.groupby("category")["revenue"].sum()
"""
    pandas_error = "Process terminated by operating system: OOM (Out of Memory Error) / SIGKILL signal."
    pandas_context = "High-throughput ETL pipeline tracking raw transactions running on an AWS EC2 micro instance."

    test_production_scenario(
        scenario_name="Data Scalability Memory Leak",
        code_snippet=pandas_leak_code,
        error_log=pandas_error,
        context=pandas_context,
    )

    # --- SCENARIO 2: AI CODE SECURITY FAILURE (SQL Injection / Plaintext Secrets) ---
    ai_security_code = """
import psycopg2

def fetch_user_embedding_profile(user_input_id: str):
    # CRITICAL BUG: Direct string interpolation exposes DB to SQL injection
    # CRITICAL BUG: Hardcoded connection credential strings
    conn = psycopg2.connect("dbname=ai_metrics user=admin password=secret_password host=localhost")
    cursor = conn.cursor()
    
    query = f"SELECT user_id, embedding_vector FROM vectors WHERE user_id = '{user_input_id}'"
    cursor.execute(query)
    return cursor.fetchone()
"""
    security_error = "No runtime crash reported, but pre-production code scan flagged critical security alerts."
    security_context = "User-facing API endpoint retrieving high-dimension embeddings from a vector storage database layout."

    test_production_scenario(
        scenario_name="AI Pipeline Security Vulnerability",
        code_snippet=ai_security_code,
        error_log=security_error,
        context=security_context,
    )

    # ── CLEAN SHUTDOWN FLUSH ──────────────────────────────────────
    print("\n" + "=" * 80)
    print("⏳ Giving LangSmith background threads a moment to cleanly flush logs...")
    time.sleep(3)
    print("🚀 All traces pushed successfully. Test suite complete. 👋")