import asyncio
from typing import Dict, Any, Optional
from openai import OpenAI
from orca_dojo_sdk.kite import KiteClient
from orca_dojo_sdk.lanes.outreach import OutreachLane as BaseOutreachLane
from orca_dojo_sdk.types import TaskResult, Task
from orca_dojo_sdk.wallet import DojoWallet

class OutreachLane(BaseOutreachLane):
    """Concrete implementation of the Outreach lane for 0rca Dojo agents."""

    def __init__(self, agent_id: str, config: Any, wallet: Optional[DojoWallet] = None):
        super().__init__(config, wallet)
        self.agent_id = agent_id
        self.kite_client = KiteClient(api_key=self.config.get("kite_api_key", "KITE_MOCK_KEY"))

    def _build_system_prompt(self, task: Task) -> str:
        return (
            "You are a persuasive and professional outreach specialist. Your goal "
            "is to create engaging messages that build rapport and achieve their "
            "clear objective while maintaining a helpful, non-spammy tone."
        )

    def _build_user_prompt(self, task: Task) -> str:
        recipient = task.payload.get("recipient", "a potential partner")
        goal = task.payload.get("goal", "introduction")
        context = task.payload.get("context", "None")
        return f"Recipient: {recipient}\nGoal: {goal}\nContext: {context}"

    async def process_task(self, task: Task) -> TaskResult:
        """Main task execution loop for the agent."""
        params = self.get_llm_params()
        api_key = self.get_openai_key()

        print(f"OutreachLane executor started for task {task.task_id}")
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
        """Requirement for Outreach lane: must contain 'recipient' or 'goal'."""
        return "recipient" in payload or "goal" in payload
