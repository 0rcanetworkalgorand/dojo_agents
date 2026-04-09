import os
import sys
import json
from algosdk import account, mnemonic

# Ensure we can import config_loader from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import ConfigVault

def setup():
    # Use absolute paths for reliability
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vault_dir = os.path.join(base_dir, "vault")
    
    if not os.path.exists(vault_dir):
        os.makedirs(vault_dir)
        print(f"Created vault directory: {vault_dir}")

    # 1. Generate new Algorand account for the agent
    priv_key, pub_addr = account.generate_account()
    agent_mnemonic = mnemonic.from_private_key(priv_key)
    print(f"--- AGENT IDENTITY GENERATED ---")
    print(f"Public Address: {pub_addr}")
    print(f"Mnemonic: {agent_mnemonic}")
    print(f"---------------------------------")

    # 2. Define our Master Vault Key
    # In a real scenario, this would be an input or env var, but for this setup we provide it
    vault_key = "0rca_Dojo_Protocol_v1_Secret!2026_Secure"
    vault = ConfigVault(vault_key)

    # 3. Create Agent identity data
    agent_data = {
        "config": {
            "agent_id": "agent_01",
            "lane": "research",
            "llm_tier": "gpt-4o",
            "bidding_strategy": "balanced"
        },
        "private_key": priv_key,
        "kite_api_key": "KITE_MOCK_API_KEY_123456" # Placeholder for Kite AI provenance
    }

    # 4. Encrypt the data and save to the .enc file
    encrypted_str = vault.encrypt(agent_data)
    vault_path = os.path.join(vault_dir, "agent_01.enc")
    with open(vault_path, "w") as f:
        f.write(encrypted_str)
    
    print(f"SUCCESS: Encrypted vault file created at: {vault_path}")
    print(f"VAULT_KEY: {vault_key}")
    print(f"IMPORTANT: Store this VAULT_KEY securely. You will need it to run the agent.")

if __name__ == "__main__":
    setup()
