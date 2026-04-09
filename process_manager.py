import asyncio
import json
import logging
from typing import Dict, Any, List, Type
from lanes.research import ActiveResearchLane
from lanes.code import CodeLane
from lanes.data import DataLane
from lanes.outreach import OutreachLane
from orca_dojo_sdk.types import Task, TaskResult, LaneType

LANE_MAP: Dict[str, Any] = {
    "RESEARCH": ActiveResearchLane,
    "CODE": CodeLane,
    "DATA": DataLane,
    "OUTREACH": OutreachLane
}

class AgentProcess:
    """Manages an individual agent worker process."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.process = None

    async def spawn(self):
        """Spawns the agent as a subprocess."""
        self.process = await asyncio.create_subprocess_exec(
            "python", "main.py", "--agent-id", self.agent_id,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        logging.info(f"Spawned agent {self.agent_id} (PID: {self.process.pid})")

    async def send_command(self, cmd: str, payload: Dict[str, Any]):
        """Sends a JSON command to the agent subprocess."""
        if not self.process or not self.process.stdin:
            raise RuntimeError(f"Agent {self.agent_id} process not running.")
        
        msg = json.dumps({"command": cmd, "payload": payload}) + "\n"
        self.process.stdin.write(msg.encode())
        await self.process.stdin.drain()

    async def listen(self):
        """Listens for responses from the agent process."""
        if not self.process or not self.process.stdout:
            return
            
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            
            try:
                msg = json.loads(line.decode().strip())
                # Handle agent signals (heartbeats, logs, task status)
                print(f"[AGENT:{self.agent_id}] {msg}")
            except json.JSONDecodeError:
                print(f"[AGENT:{self.agent_id}:RAW] {line.decode().strip()}")

class ProcessManager:
    """Orchestrates multiple agent processes."""

    def __init__(self):
        self.agents: Dict[str, AgentProcess] = {}

    async def start_agent(self, agent_id: str):
        agent = AgentProcess(agent_id)
        await agent.spawn()
        self.agents[agent_id] = agent
        # Run listeners in the background
        asyncio.create_task(agent.listen())

    async def stop_agent(self, agent_id: str):
        if agent_id in self.agents:
            self.agents[agent_id].process.terminate()
            del self.agents[agent_id]

async def dispatch_task(task: Task, executor_instance: Any) -> TaskResult:
    """
    Dispatches a task to the correct lane executor.
    """
    lane_key = task.lane.value.upper() if hasattr(task.lane, 'value') else str(task.lane).upper()
    
    if lane_key not in LANE_MAP:
        raise ValueError(f"Unknown lane: {task.lane}")
    
    # The executor_instance should be an instance of the class mapped in LANE_MAP
    return await executor_instance.process_task(task)

if __name__ == "__main__":
    async def main():
        manager = ProcessManager()
        print("Process manager ready. Waiting for IPC messages.")
        # Minimal loop to keep manager alive or handle IPC
        while True:
            await asyncio.sleep(3600)
            
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
