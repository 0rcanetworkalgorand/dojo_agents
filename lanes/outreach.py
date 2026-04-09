import asyncio
from typing import Dict, Any, Optional
from openai import OpenAI
from orca_dojo_sdk.kite import KiteClient
from orca_dojo_sdk.lanes.outreach import OutreachLane as BaseOutreachLane
from orca_dojo_sdk.types import TaskResult, AgentConfig, Task
from orca_dojo_sdk.wallet import DojoWallet

class OutreachLane(BaseOutreachLane):
    """Concrete implementation of the Outreach lane for 0rca Dojo agents."""

    def __init__(self, agent_id: str, config: AgentConfig, wallet: Optional[DojoWallet] = None):
        super().__init__(config, wallet)
        self.agent_id = agent_id
        self.kite_client = KiteClient(api_key=self.config.metadata.get("kite_api_key", "KITE_MOCK_KEY"))
        print(f"OutreachLane executor started for task {self.agent_id}")

    async def process_task(self, task: Task) -> TaskResult:
        """Requirement for BaseAgent: implementation of task processing."""
        # 1. Call self.get_llm_params()
        llm_params = self.get_llm_params()
        
        # 2. Extract inputs from payload
        description = task.payload.get("description", "")
        recipient_context = task.payload.get("recipient_context", "")
        tone = task.payload.get("tone", "professional")
        length = task.payload.get("length", "medium")

        # 3. Construct system prompt
        system_prompt = (
            f"You are an expert copywriter specializing in outreach and communication. "
            f"Write persuasive, human-sounding {tone} messages. Do not use clichés. "
            f"Be concise and specific. Length: {length}."
        )

        # 4. Construct user prompt
        user_prompt = (
            f"Prompt: {description}\n\n"
            f"Recipient: {recipient_context}"
        )

        # 5. Call the OpenAI API
        api_key = self.config.metadata.get("openai_api_key")
        if not api_key:
            raise ValueError("openai_api_key missing from agent configuration.")
            
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=llm_params["model"],
            max_tokens=llm_params["max_tokens"],
            temperature=llm_params["temperature"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        # 6. Extract output text
        output = response.choices[0].message.content

        # 7. Register with Kite AI
        try:
            kite_hash = await self.kite_client.register_output(
                task_id=task.task_id,
                agent_address=self.config.metadata.get("agent_address", "0x0000"),
                output=output
            )
        except AttributeError:
            kite_hash = await self.kite_client.submit_provenance(
                TaskResult(
                    task_id=task.task_id,
                    success=True,
                    output={"outreach": output},
                    metadata={"agent_id": self.agent_id}
                )
            )

        # 8. Return in the same result format
        return TaskResult(
            task_id=task.task_id,
            success=True,
            output={"result": output},
            provenance_hash=kite_hash
        )

    def validate_task_payload(self, payload: Dict[str, Any]) -> bool:
        """Requirement for Outreach lane: must contain 'description' and 'recipient_context'."""
        return "description" in payload and "recipient_context" in payload
