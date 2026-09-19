import hashlib
import secrets
from typing import Dict, Any, List

class MultiTenantAuth:
    def __init__(self):
        self.api_keys = {
            "omni_live_master_key_8849": {
                "user_id": "usr_alpha_founder",
                "tier": "tier_institutional",
                "rate_limit_rpm": 600,
                "label": "Master Production API Key"
            }
        }

    def generate_api_key(self, user_id: str, label: str = "Client Key") -> str:
        key = f"omni_{secrets.token_hex(16)}"
        self.api_keys[key] = {
            "user_id": user_id,
            "tier": "tier_pro",
            "rate_limit_rpm": 300,
            "label": label
        }
        return key

    def validate_api_key(self, key: str) -> bool:
        return key in self.api_keys

    def list_keys(self) -> List[Dict[str, Any]]:
        return [
            {"key": k[:8] + "..." + k[-4:], "tier": v["tier"], "label": v["label"]}
            for k, v in self.api_keys.items()
        ]
