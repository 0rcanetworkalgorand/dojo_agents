import asyncio
from typing import Dict, Any, Optional
from orca_dojo_sdk.lanes.research import ResearchLane
from orca_dojo_sdk.types import TaskResult, AgentConfig
from orca_dojo_sdk.wallet import DojoWallet


class ActiveResearchLane(ResearchLane):
    """Concrete implementation of the Research lane for 0rca Dojo agents."""

    def __init__(self, agent_id: str, config: AgentConfig, wallet: Optional[DojoWallet] = None):
        super().__init__(config, wallet)
        self.agent_id = agent_id

    async def perform_research(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Executes a research task using an LLM (mocked here, can be extended to OpenAI).
        """
        print(f"Agent {self.agent_id} starting research on: {query}")
        
        # Simulate logic: In real implementation, this would call GPT-4/SearchTool
        await asyncio.sleep(2)
        
        result = f"Synthesized research report for '{query}' based on context '{context}'."
        return result

    async def process_task(self, task: Task) -> TaskResult:
        """Requirement for BaseAgent: implementation of task processing."""
        query = task.payload.get("query", "")
        context = task.payload.get("context", {})
        
        output_text = await self.perform_research(query, context)
        
        return TaskResult(
            task_id=task.task_id,
            success=True,
            output={"result": output_text}
        )

    def validate_task_payload(self, payload: Dict[str, Any]) -> bool:
        """Requirement for Research lane: must contain a valid 'query'."""
        return "query" in payload
