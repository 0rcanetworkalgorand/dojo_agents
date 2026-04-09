import os
import time
import json
import requests
import socketio
import threading
from decimal import Decimal
from dotenv import load_dotenv

# Load workspace env
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3006")
AGENT_LANE = os.getenv("AGENT_LANE", "RESEARCH")

sio = socketio.Client()

def get_my_agents():
    """Fetch agents belonging to the current user/lane to decide who bids."""
    try:
        # For demo, we just get all idle agents in this lane
        resp = requests.get(f"{BACKEND_URL}/agents?lane={AGENT_LANE}")
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[Watcher] Error fetching agents: {e}")
    return []

@sio.event
def connect():
    print(f"[Watcher] Connected to Phoenix Swarm Backend at {BACKEND_URL}")

@sio.on("NEW_TASK")
def on_new_task(data):
    task_id = data.get("id")
    lane = data.get("lane")
    bounty_micro = int(data.get("bountyUsdc", 0))
    
    print(f"[Watcher] 📡 New Task Detected: {task_id} (Lane: {lane}, Bounty: {bounty_micro/1_000_000} USDC)")
    
    if lane != AGENT_LANE:
        print(f"[Watcher] Skipping task (mismatched lane: {lane})")
        return

    # Find an agent to bid
    my_agents = get_my_agents()
    if not my_agents:
        print("[Watcher] No active agents available to bid.")
        return

    # Simple Strategy: Bid 90% of maximum bounty to win!
    bid_amount = int(bounty_micro * 0.9)
    agent = my_agents[0]
    agent_address = agent.get("address")

    print(f"[Watcher] 💡 Bidding {bid_amount/1_000_000} USDC for Agent {agent_address}...")

    try:
        bid_resp = requests.post(
            f"{BACKEND_URL}/tasks/{task_id}/bid",
            json={
                "agentAddress": agent_address,
                "bidAmountUsdc": str(bid_amount)
            }
        )
        if bid_resp.status_code == 200:
            print(f"[Watcher] ✅ Bid accepted for task {task_id}")
        else:
            print(f"[Watcher] ❌ Bid rejected: {bid_resp.text}")
    except Exception as e:
        print(f"[Watcher] Error submitting bid: {e}")

@sio.event
def disconnect():
    print("[Watcher] Disconnected from backend.")

def main():
    print(f"--- 0rca Swarm Dojo Watcher ---")
    print(f"Monitoring Lane: {AGENT_LANE}")
    
    # Try connecting with exponential backoff
    retry = 0
    while retry < 5:
        try:
            sio.connect(BACKEND_URL)
            break
        except Exception as e:
            print(f"Connection failed, retrying... ({e})")
            time.sleep(5)
            retry += 1

    if sio.connected:
        print("[Watcher] Active and listening for tasks...")
        try:
            sio.wait()
        except KeyboardInterrupt:
            sio.disconnect()

if __name__ == "__main__":
    main()
