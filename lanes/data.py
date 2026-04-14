import asyncio
from typing import Dict, Any, Optional
from openai import OpenAI
from orca_dojo_sdk.kite import KiteClient
from orca_dojo_sdk.lanes.data import DataLane as BaseDataLane
from orca_dojo_sdk.types import TaskResult, Task
from orca_dojo_sdk.wallet import DojoWallet

class DataLane(BaseDataLane):
    """Concrete implementation of the Data lane for 0rca Dojo agents."""

    def __init__(self, agent_id: str, config: Any, wallet: Optional[DojoWallet] = None):
        super().__init__(config, wallet)
        self.agent_id = agent_id
        self.kite_client = KiteClient(api_key=self.config.get("kite_api_key", "KITE_MOCK_KEY"))

    def _build_system_prompt(self, task: Task) -> str:
        return (
            "You are a master data analyst and scientist. Process the input data "
            "provided, perform the requested analysis or transformation, and return "
            "the results in a clean, structured format."
        )

    def _build_user_prompt(self, task: Task) -> str:
        data = task.payload.get("data", "No data provided")
        operation = task.payload.get("operation", "analyze")
        return f"Operation: {operation}\n\nData: {data}"

    async def process_task(self, task: Task) -> TaskResult:
        """Main task execution loop for the agent."""
        params = self.get_llm_params()
        api_key = self.get_openai_key()

        print(f"DataLane executor started for task {task.task_id}")
        print(f"API call made with model: {params['model']}")

        # Groq Cloud Support
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
        """Requirement for Data lane: must contain 'data' or 'operation'."""
        return "data" in payload or "operation" in payload
