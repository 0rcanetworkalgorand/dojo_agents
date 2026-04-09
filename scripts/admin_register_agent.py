import os
import sys
import algosdk
from algokit_utils import AlgorandClient, CommonAppCallParams, BoxReference

# Ensure we can import from the contract clients and agent logic
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir) # dojo-agents
sys.path.append(os.path.join(os.path.dirname(base_dir), "dojo-sdk")) # dojo-sdk

from config_loader import load_agent_secrets
from orca_dojo_sdk.contracts.DojoRegistryClient import DojoRegistryClient, RegisterAgentArgs

def admin_register():
    admin_mnemonic = "bracket inform cricket pact impact mask misery quantum dismiss giant fog mechanic category royal east actual gold easily snow laundry vast gown crater absent denial"
    algorand = AlgorandClient.testnet()
    admin = algorand.account.from_mnemonic(mnemonic=admin_mnemonic)
    
    # 2. Get Agent Identity from the Vault
    agent_id = "agent_01"
    # Ensure VAULT_KEY is available locally for this run if not set
    if not os.getenv("VAULT_KEY"):
        os.environ["VAULT_KEY"] = "0rca_Dojo_Protocol_v1_Secret!2026_Secure"
        
    try:
        secrets = load_agent_secrets(agent_id)
        agent_address = algosdk.account.address_from_private_key(secrets["private_key"])
    except Exception as e:
        print(f"ERROR: Could not load agent secrets: {e}")
        return

    # 3. Initialize Registry Client as Admin
    REGISTRY_ID = 758273132
    registry = DojoRegistryClient(
        algorand=algorand,
        app_id=REGISTRY_ID,
        default_sender=admin.address,
        default_signer=admin.signer
    )
    
    print(f"Administrative Registry Operation:")
    print(f"Admin: {admin.address}")
    print(f"Target Agent: {agent_id} ({agent_address})")
    
    try:
        # Perform the on-chain registration as the authorized ADMIN
        result = registry.send.register_agent(
            args=RegisterAgentArgs(
                agent_id=agent_id,
                sensei=agent_address,
                lane=0, # Default: Research
                config_hash=os.urandom(32)
            ),
            params=CommonAppCallParams(
                box_references=[BoxReference(app_id=0, name=agent_id.encode())]
            )
        )
        print(f"SUCCESS: Agent {agent_id} is now registered on the blockchain.")
        print(f"Transaction ID: {result.tx_id}")
    except Exception as e:
        if "already registered" in str(e).lower():
            print(f"INFO: Agent {agent_id} is already registered on-chain.")
        else:
            print(f"ERROR: On-chain registration failed: {e}")

if __name__ == "__main__":
    admin_register()
