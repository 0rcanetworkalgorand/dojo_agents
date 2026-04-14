from typing import Dict, Any, Optional
from openai import OpenAI
from orca_dojo_sdk.lanes.research import ResearchLane as BaseResearchLane
from orca_dojo_sdk.types import TaskResult, Task
from orca_dojo_sdk.wallet import DojoWallet
from orca_dojo_sdk.kite import KiteClient


class ActiveResearchLane(BaseResearchLane):
    """Concrete implementation of the Research lane for 0rca Dojo agents."""

    def __init__(self, agent_id: str, config: Any, wallet: Optional[DojoWallet] = None):
        super().__init__(config, wallet)
        self.agent_id = agent_id
        # Note: In real production, this would be a real Kite API key or URL
        self.kite_client = KiteClient(api_key=self.config.get("kite_api_key", "KITE_MOCK_KEY"))

    def _build_system_prompt(self, task: Task) -> str:
        return (
            "You are a world-class research assistant. Provide thorough, accurate, "
            "and objective information. Cite sources where possible and maintain "
            "a professional tone."
        )

    def _build_user_prompt(self, task: Task) -> str:
        return (
            f"Research Task: {task.payload.get('query', task.task_id)}\n"
            f"Context: {task.payload.get('context', 'None provided')}"
        )

    async def process_task(self, task: Task) -> TaskResult:
        """Main task execution loop for the agent."""
        params = self.get_llm_params()
        api_key = self.get_openai_key()

        print(f"ResearchLane executor started for task {task.task_id}")
        print(f"API call made with model: {params['model']}")

        # Groq Cloud Support: Use Groq endpoint if key starts with gsk_
        base_url = None
        if api_key.startswith("gsk_"):
            base_url = "https://api.groq.com/openai/v1"
            print("Using Groq Cloud API endpoint.")

        client = OpenAI(api_key=api_key, base_url=base_url)

        response = client.chat.completions.create(
            model=params["model"],
            max_tokens=params["max_tokens"],
            temperature=params["temperature"],
            messages=[
                {"role": "system", "content": self._build_system_prompt(task)},
                {"role": "user", "content": self._build_user_prompt(task)}
            ]
        )

        output = response.choices[0].message.content

        # Register output with Kite AI for attribution
        kite_hash = await self.kite_client.submit_provenance(
            TaskResult(
                task_id=task.task_id,
                success=True,
                output={"result": output},
                metadata={"agent_id": self.agent_id}
            )
        )
        print(f"Kite AI attribution hash received: {kite_hash}")

        return TaskResult(
            task_id=task.task_id,
            success=True,
            output={"result": output},
            provenance_hash=kite_hash
        )

    def validate_task_payload(self, payload: Dict[str, Any]) -> bool:
        """Requirement for Research lane: must contain a valid 'query'."""
        return "query" in payload or "description" in payload
