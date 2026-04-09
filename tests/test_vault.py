import os
import sys
import json

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import ConfigVault

def test_vault_loop():
    print("Testing Vault Encryption/Decryption...")
    master_key = "test_master_key_123456"
    vault = ConfigVault(master_key)
    
    original_config = {
        "config": {
            "agent_id": "test_agent_001",
            "lane": "research",
            "llm_tier": "high",
            "bidding_strategy": "defensive"
        },
        "private_key": "x01" * 32,
        "kite_api_key": "kite_test_abc123"
    }
    
    # Encrypt
    encrypted_str = vault.encrypt(original_config)
    print(f"Encrypted string length: {len(encrypted_str)}")
    
    # Decrypt
    decrypted_config = vault.decrypt(encrypted_str)
    
    assert decrypted_config["config"]["agent_id"] == "test_agent_001"
    assert decrypted_config["private_key"] == "x01" * 32
    print("Vault loop verification PASSED.")

if __name__ == "__main__":
    try:
        test_vault_loop()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
