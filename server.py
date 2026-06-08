"""
HTTP Agent Server for Heroku deployment.

Simple Flask server that receives task execution requests from the Node.js backend
and processes them using the lane-specific executors.

Architecture:
  Node.js Backend (web dyno) --HTTP POST /execute--> Python Agent Server (worker web dyno)

The backend calls this server when AGENT_MODE=http is set.
If this server is down or unreachable, the backend falls back to direct LLM execution.

Usage:
  heroku ps:scale web=1 -a orca-dojo-agents
"""
import asyncio
import json
import os
import sys
import traceback

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from config_loader import load_agent_secrets
from lanes.research import ActiveResearchLane
from lanes.code import CodeLane
from lanes.data import DataLane
from lanes.outreach import OutreachLane

LANE_MAP = {
    "RESEARCH": ActiveResearchLane,
    "CODE": CodeLane,
    "DATA": DataLane,
    "OUTREACH": OutreachLane,
}

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Heroku."""
    return jsonify({"status": "ok", "service": "dojo-agents"})


@app.route('/execute', methods=['POST'])
def execute_task():
    """
    Execute a task using the appropriate lane executor.
    
    Request body:
    {
        "agentId": "code-5jm4u7",
        "taskId": "abc123",
        "payload": { "instructions": "..." }
    }
    
    Response:
    {
        "type": "TASK_COMPLETE",
        "taskId": "abc123",
        "result": { ... },
        "provenanceHash": "..."
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"type": "TASK_FAILED", "message": "No JSON body"}), 400

    agent_id = data.get("agentId")
    task_id = data.get("taskId")
    payload = data.get("payload", {})

    if not agent_id or not task_id:
        return jsonify({"type": "TASK_FAILED", "message": "Missing agentId or taskId"}), 400

    print(f"[Server] Received task {task_id} for agent {agent_id}")

    try:
        result = asyncio.run(_process_task(agent_id, task_id, payload))
        return jsonify(result)
    except FileNotFoundError as e:
        print(f"[Server] Vault not found for agent {agent_id}: {e}")
        return jsonify({
            "type": "TASK_FAILED",
            "taskId": task_id,
            "message": f"Agent vault not found: {agent_id}"
        }), 404
    except Exception as e:
        print(f"[Server] Task {task_id} failed: {e}")
        traceback.print_exc()
        return jsonify({
            "type": "TASK_FAILED",
            "taskId": task_id,
            "message": str(e)
        }), 500


async def _process_task(agent_id: str, task_id: str, payload: dict) -> dict:
    """Process a task using the lane executor."""
    # Load agent config from vault
    secrets = load_agent_secrets(agent_id)
    config_data = secrets.get("config", secrets)
    lane = config_data.get("lane", "RESEARCH").upper()

    if lane not in LANE_MAP:
        raise ValueError(f"Unknown lane: {lane}")

    # Set up wallet
    from orca_dojo_sdk.wallet import DojoWallet
    pk = secrets.get("private_key")
    wallet = DojoWallet(private_key=pk) if pk else DojoWallet.create_random()

    # Create executor and process
    executor_class = LANE_MAP[lane]
    executor = executor_class(agent_id, secrets, wallet)

    from orca_dojo_sdk.types import Task as TaskObj
    task_obj = TaskObj(
        task_id=task_id,
        lane=lane,
        payload=payload,
        reward_micro_usdc=0
    )

    result = await executor.process_task(task_obj)

    return {
        "type": "TASK_COMPLETE",
        "taskId": task_id,
        "result": result.model_dump() if hasattr(result, 'model_dump') else str(result),
        "provenanceHash": result.provenance_hash if hasattr(result, 'provenance_hash') else None,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print("  0RCA DOJO — Agent HTTP Server")
    print(f"  Listening on port {port}")
    print(f"  VAULT_KEY: {'SET' if os.environ.get('VAULT_KEY') else 'MISSING'}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port)
