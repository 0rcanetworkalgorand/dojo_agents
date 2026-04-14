import asyncio
import argparse
import json
import os
import sys
from dotenv import load_dotenv
load_dotenv()
from typing import Any
import algosdk
from algosdk import account, atomic_transaction_composer
from algokit_utils import (
    AlgorandClient,
    AssetTransferParams,
    CommonAppCallParams,
    SigningAccount,
    BoxReference
)
from orca_dojo_sdk.wallet import DojoWallet
from orca_dojo_sdk.kite import KiteClient
from orca_dojo_sdk.types import AgentConfig, TaskResult, LaneType
from orca_dojo_sdk.contracts.DojoRegistryClient import DojoRegistryClient, RegisterAgentArgs
from orca_dojo_sdk.contracts.EscrowVaultClient import EscrowVaultClient, LockCollateralArgs
from lanes.research import ActiveResearchLane
from lanes.code import CodeLane
from lanes.data import DataLane
from lanes.outreach import OutreachLane

LANE_MAP = {
    "RESEARCH": ActiveResearchLane,
    "CODE": CodeLane,
    "DATA": DataLane,
    "OUTREACH": OutreachLane
}
from config_loader import load_agent_secrets

# Load Environment Fallbacks
REGISTRY_ID = int(os.getenv("DOJO_REGISTRY_APP_ID", "758273132"))
ESCROW_ID = int(os.getenv("ESCROW_VAULT_APP_ID", "758273134"))
USDC_ID = int(os.getenv("USDC_ASSET_ID", "10458941"))
ALGOD_URL = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")

async def bootstrap_onchain(agent_id: str, agent_address: str, signer: Any, lane: LaneType):
    """Ensure the agent is registered in the DojoRegistry."""
    print(f"Checking on-chain registration for {agent_id}...")
    algorand = AlgorandClient.testnet()
    # Note: Algokit-utils v3 uses AlgorandClient for most things
    registry = DojoRegistryClient(
        algorand=algorand,
        app_id=REGISTRY_ID,
        default_sender=agent_address,
        default_signer=signer
    )

    try:
        # ARC56/v4: Check if agent already exists in box storage (Read-Only)
        print(f"Verifying registration for agent {agent_id}...")
        # In v4, method params are under .params
        agent_data = registry.params.get_agent(args=(agent_id,))
        if agent_data:
            print(f"Agent {agent_id} is verified and registered on-chain.")
            return

    except Exception as e:
        print(f"Identity: Agent {agent_id} is not yet registered by the Admin.")
        print(f"Action required: Run 'python scripts/admin_register_agent.py' to register this identity.")
        print(f"Proceeding with local task loop...")

async def lock_collateral_onchain(taskId: str, amount: int, agent_address: str, signer: Any):
    """Lock USDC collateral for a specific task."""
    print(f"Locking {amount} microUSDC collateral for task {taskId}...")
    algorand = AlgorandClient.testnet()
    escrow = EscrowVaultClient(
        algorand=algorand,
        app_id=ESCROW_ID,
        default_sender=agent_address,
        default_signer=signer
    )
    
    # 1. Create the Asset Transfer Transaction
    # 2. Call lock_collateral passing the txn as an argument
    try:
        # We use a composer or the generated client's helpers
        # EscrowVault expects an axfer group
        asset_transfer = algorand.transactions.asset_transfer(
            AssetTransferParams(
                sender=agent_address,
                receiver=escrow.app_address,
                asset_id=USDC_ID,
                amount=amount
            )
        )
        
        escrow.send.lock_collateral(
            args=LockCollateralArgs(
                task_id=taskId,
                collateral_txn=asset_transfer
            ),
            params=CommonAppCallParams(
                box_references=[BoxReference(app_id=0, name=taskId.encode())]
            )
        )
        print(f"Collateral locked for task {taskId}.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to lock collateral: {e}")
        return False

async def submit_task_onchain(taskId: str, provenanceHash: str | bytes, agent_address: str, signer: Any):
    """Submit Vite AI provenance hash to EscrowVault."""
    print(f"Submitting provenance hash for task {taskId}...")
    algorand = AlgorandClient.testnet()
    escrow = EscrowVaultClient(
        algorand=algorand,
        app_id=ESCROW_ID,
        default_sender=agent_address,
        default_signer=signer
    )

    try:
        # Convert hex string to bytes if necessary
        hash_bytes = provenanceHash if isinstance(provenanceHash, bytes) else bytes.fromhex(provenanceHash)
        
        escrow.send.submit_task(
            args={
                "task_id": taskId,
                "kite_hash": hash_bytes
            },
            params=CommonAppCallParams(
                box_references=[BoxReference(app_id=0, name=taskId.encode())]
            )
        )
        print(f"Provenance hash submitted for task {taskId}.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to submit task: {e}")
        return False

async def main(agent_id: str):
    print(f"Agent {agent_id} initializing...")

    # 1. Load Secrets
    try:
        secrets = load_agent_secrets(agent_id)
        # Handle both flat and nested structures for backward/forward compatibility
        config_data = secrets.get("config", secrets)
        config = AgentConfig(**config_data)
        
        # Private key might be in the root or in secrets
        pk = secrets.get("private_key")
        if not pk:
            print(f"WARNING: No private_key found in vault for {agent_id}. Generating a temporary one for demo.")
            wallet = DojoWallet.create_random()
            pk = wallet.private_key
        else:
            wallet = DojoWallet(private_key=pk)
            
        agent_address = wallet.get_public_address()
        signer = atomic_transaction_composer.AccountTransactionSigner(pk)
        print(f"Agent {agent_id} wallet: {agent_address}")
    except Exception as e:
        print(f"FATAL: Wallet setup failed: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. On-Chain Bootstrap
    await bootstrap_onchain(agent_id, agent_address, signer, config.lane)

    # 3. Setup Lane Specific Logic
    lane_key = config.lane.value.upper() if hasattr(config.lane, 'value') else str(config.lane).upper()
    
    if lane_key in LANE_MAP:
        executor_class = LANE_MAP[lane_key]
        executor = executor_class(agent_id, secrets, wallet)
    else:
        print(f"FATAL: Support for lane {config.lane} not yet implemented.", file=sys.stderr)
        sys.exit(1)

    print(f"Agent {agent_id} ({config.lane}) ready for tasks.")
    sys.stdout.flush()
    
    # 4. Task Listening Loop (via stdio JSON-L)
    # Note: On Windows, connect_read_pipe is unstable. We use to_thread for safety.
    print(f"Agent {agent_id} ({config.lane}) ready for tasks.")
    sys.stdout.flush()

    while True:
        # Use to_thread to avoid Blocking on Windows Proactor pipes
        line_raw = await asyncio.to_thread(sys.stdin.readline)
        if not line_raw: break
        line = line_raw.strip()
        if not line: continue
        
        try:
            msg = json.loads(line)
            if msg.get("type") == "TASK_ASSIGN":
                task_id = msg.get("taskId")
                payload = msg.get("payload", {})
                collateral = msg.get("collateralUsdc", 0)
                
                # --- ON-CHAIN ACTION: LOCK COLLATERAL ---
                if collateral > 0:
                    success = await lock_collateral_onchain(task_id, collateral, agent_address, signer)
                    if not success:
                        print(json.dumps({"type": "TASK_FAILED", "taskId": task_id, "message": "Collateral lock failed"}))
                        sys.stdout.flush()
                        continue

                # Execute task via the generic executor
                from orca_dojo_sdk.types import Task
                task_obj = Task(
                    task_id=task_id,
                    lane=config.lane,
                    payload=payload,
                    reward_micro_usdc=0 # Not contextually available here but required by Task model
                )

                try:
                    # Generic task processing following the research.py pattern
                    result_payload = await executor.process_task(task_obj)
                    prov_hash = result_payload.provenance_hash
                    
                    # --- ON-CHAIN ACTION: SUBMIT PROVENANCE HASH ---
                    if prov_hash:
                        submit_success = await submit_task_onchain(task_id, prov_hash, agent_address, signer)
                        if not submit_success:
                            print(json.dumps({"type": "TASK_FAILED", "taskId": task_id, "message": "On-chain hash submission failed"}))
                            sys.stdout.flush()
                            continue

                    # Signal Completion via stdout
                    print(json.dumps({
                        "type": "TASK_COMPLETE",
                        "taskId": task_id,
                        "result": result_payload.model_dump(),
                        "provenanceHash": prov_hash
                    }))
                    sys.stdout.flush()
                except Exception as task_err:
                    print(json.dumps({
                        "type": "TASK_FAILED",
                        "taskId": task_id,
                        "message": str(task_err)
                    }))
                    sys.stdout.flush()
                
        except Exception as e:
            print(json.dumps({"type": "TASK_FAILED", "message": str(e)}))
            sys.stdout.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-id", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.agent_id))
