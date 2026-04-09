import os
import json
import base64
import binascii
from dotenv import load_dotenv
load_dotenv()
from typing import Dict, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# --- MODULE LEVEL VALIDATION (GAP 2) ---
_vault_key_hex = os.environ.get("VAULT_KEY", "")
if not _vault_key_hex:
    raise EnvironmentError(
        "VAULT_KEY environment variable is not set. "
        "dojo-agents cannot start without it."
    )
if len(_vault_key_hex) != 64:
    raise EnvironmentError(
        f"VAULT_KEY must be exactly 64 hex characters (32 bytes). "
        f"Got {len(_vault_key_hex)} characters."
    )
try:
    VAULT_KEY_BYTES = bytes.fromhex(_vault_key_hex)
except binascii.Error as e:
    raise EnvironmentError(
        f"VAULT_KEY is not valid hex: {e}"
    )

# --- LLM TIER MAPPING (GAP 1) ---
LLM_TIER_MAP = {
  "Standard": {
    "model": "gpt-4o-mini",
    "max_tokens": 2000,
    "temperature": 0.3,
    "cost_per_1k_tokens_usd": 0.00015
  },
  "Pro": {
    "model": "gpt-4o",
    "max_tokens": 4000,
    "temperature": 0.3,
    "cost_per_1k_tokens_usd": 0.005
  },
  "Elite": {
    "model": "gpt-4o",
    "max_tokens": 8000,
    "temperature": 0.2,
    "cost_per_1k_tokens_usd": 0.005
  }
}

class ConfigVault:
    """Manages encryption and decryption of agent configurations."""

    def __init__(self, master_key_bytes: bytes):
        """
        Initializes the vault with a master key in bytes.
        """
        self.master_key = master_key_bytes
        # Use a fixed salt for simplicity in this version, can be extended to per-file salts
        self.salt = b'0rca_swarm_dojo_salt'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
            backend=default_backend()
        )
        self.derived_key = kdf.derive(self.master_key)
        self.aesgcm = AESGCM(self.derived_key)

    def encrypt(self, data: Dict[str, Any]) -> str:
        """Encrypts dictionary data to a base64 string."""
        nonce = os.urandom(12)
        plaintext = json.dumps(data).encode()
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
        # Encoded as nonce + ciphertext
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted_str: str) -> Dict[str, Any]:
        """Decrypts a base64 string back into dictionary data."""
        data = base64.b64decode(encrypted_str)
        nonce = data[:12]
        ciphertext = data[12:]
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())

def load_agent_secrets(agent_id: str) -> Dict[str, Any]:
    """
    Loads and decrypts agent configuration from the vault.
    Expects VAULT_KEY environment variable to be set.
    """
    vault = ConfigVault(VAULT_KEY_BYTES)
    vault_path = os.path.join(os.getcwd(), "vault", f"{agent_id}.enc")
    
    if not os.path.exists(vault_path):
        raise FileNotFoundError(f"Vault file for agent {agent_id} not found at {vault_path}")
        
    with open(vault_path, "r") as f:
        encrypted_config = f.read()
        
    decrypted_config = vault.decrypt(encrypted_config)
    
    # Resolve LLM params based on tier (GAP 1)
    tier = decrypted_config.get("llm_tier", "Standard")
    if tier not in LLM_TIER_MAP:
        raise ValueError(f"Unknown LLM tier in config: {tier}. "
                         f"Must be one of: {list(LLM_TIER_MAP.keys())}")
    
    decrypted_config["llm_params"] = LLM_TIER_MAP[tier]
    return decrypted_config
