from typing import Dict, Any, Optional
from openai import OpenAI
from orca_dojo_sdk.kite import KiteClient
from orca_dojo_sdk.lanes.code import CodeLane as BaseCodeLane
from orca_dojo_sdk.types import TaskResult, Task
from orca_dojo_sdk.wallet import DojoWallet

class CodeLane(BaseCodeLane):
    """Concrete implementation of the Code lane for 0rca Dojo agents."""

    def __init__(self, agent_id: str, config: Any, wallet: Optional[DojoWallet] = None):
        super().__init__(config, wallet)
        self.agent_id = agent_id
        self.kite_client = KiteClient(api_key=self.config.get("kite_api_key", "KITE_MOCK_KEY"))

    def _build_system_prompt(self, task: Task) -> str:
        language = task.payload.get("language", "python")
        return (
            f"You are an expert software engineer specializing in {language}. "
            f"Write clean, well-commented, and production-ready code. "
            f"Return only the code and a concise explanation."
        )

    def _build_user_prompt(self, task: Task) -> str:
        description = task.payload.get("description", "write code")
        context = task.payload.get("context", "None")
        return f"Task: {description}\n\nContext: {context}"

    async def process_task(self, task: Task) -> TaskResult:
        """Main task execution loop for the agent."""
        params = self.get_llm_params()
        api_key = self.get_openai_key()

        print(f"CodeLane executor started for task {task.task_id}")
        print(f"OpenAI API call made with model: {params['model']}")

        client = OpenAI(api_key=api_key)

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
        """Requirement for Code lane: must contain 'description' or 'query'."""
        return "description" in payload or "query" in payload
