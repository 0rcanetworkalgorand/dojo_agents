import asyncio
from typing import Dict, Any, Optional
from openai import OpenAI
from orca_dojo_sdk.kite import KiteClient
from orca_dojo_sdk.lanes.code import CodeLane as BaseCodeLane
from orca_dojo_sdk.types import TaskResult, AgentConfig, Task
from orca_dojo_sdk.wallet import DojoWallet

class CodeLane(BaseCodeLane):
    """Concrete implementation of the Code lane for 0rca Dojo agents."""

    def __init__(self, agent_id: str, config: AgentConfig, wallet: Optional[DojoWallet] = None):
        super().__init__(config, wallet)
        self.agent_id = agent_id
        self.kite_client = KiteClient(api_key=self.config.metadata.get("kite_api_key", "KITE_MOCK_KEY"))
        print(f"CodeLane executor started for task {self.agent_id}")

    async def process_task(self, task: Task) -> TaskResult:
        """Requirement for BaseAgent: implementation of task processing."""
        # 1. Call self.get_llm_params() to get the model and settings
        llm_params = self.get_llm_params()
        
        # 2. Extract inputs from payload
        description = task.payload.get("description", "")
        language = task.payload.get("language", "python")
        context = task.payload.get("context", "")

        # 3. Construct system prompt
        system_prompt = (
            f"You are an expert software engineer. Write clean, well-commented, "
            f"production-ready {language} code. Return only the code and a brief "
            f"explanation. Do not add unnecessary preamble."
        )

        # 4. Construct user prompt
        user_prompt = f"Task: {description}\n\nContext: {context}"

        # 5. Call the OpenAI API using the model from get_llm_params()
        # Note: openai_api_key must come from self.config (part of sealed config)
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

        # 6. Extract the response text
        output = response.choices[0].message.content

        # 7. Register the output with Kite AI
        # Note: Following the prompt's register_output pattern
        # Falling back to submit_provenance if register_output is missing in SDK
        try:
            kite_hash = await self.kite_client.register_output(
                task_id=task.task_id,
                agent_address=self.config.metadata.get("agent_address", "0x0000"),
                output=output
            )
        except AttributeError:
            # Fallback to current SDK method if register_output doesn't exist
            kite_hash = await self.kite_client.submit_provenance(
                TaskResult(
                    task_id=task.task_id,
                    success=True,
                    output={"code": output},
                    metadata={"agent_id": self.agent_id}
                )
            )

        # 8. Return the result in the exact same format as research.py returns it
        return TaskResult(
            task_id=task.task_id,
            success=True,
            output={"result": output},
            provenance_hash=kite_hash
        )

    def validate_task_payload(self, payload: Dict[str, Any]) -> bool:
        """Requirement for Code lane: must contain 'description' and 'language'."""
        return "description" in payload and "language" in payload
