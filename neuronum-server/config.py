"""
Configuration loader for Neuronum Server.
Loads configuration from server.config file and Cell credentials from ~/.neuronum/
"""

import os
import re
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def load_cell_credentials():
    """Load Cell credentials from ~/.neuronum/ directory.

    Returns:
        dict: Dictionary with 'host', 'private_key', 'public_key'
    """
    neuronum_path = Path.home() / ".neuronum"
    env_file = neuronum_path / ".env"
    private_key_file = neuronum_path / "private_key.pem"

    if not env_file.exists():
        raise FileNotFoundError(
            "No Cell credentials found. Please run 'neuronum create-cell' or 'neuronum connect-cell' first."
        )

    # Load host from .env
    host = None
    with open(env_file, 'r') as f:
        for line in f:
            if line.startswith('HOST='):
                host = line.split('=', 1)[1].strip()
                break

    if not host:
        raise ValueError("HOST not found in ~/.neuronum/.env")

    # Load private key
    if not private_key_file.exists():
        raise FileNotFoundError("Private key file not found at ~/.neuronum/private_key.pem")

    with open(private_key_file, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )

    public_key = private_key.public_key()

    return {
        'host': host,
        'private_key': private_key,
        'public_key': public_key
    }


def load_config(config_file="server.config"):
    """Load configuration from server.config file.

    Args:
        config_file: Path to the configuration file

    Returns:
        dict: Configuration dictionary with all settings
    """
    config = {}

    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file '{config_file}' not found")

    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse key = value lines
            if '=' in line:
                # Split on first = only
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove inline comments
                if '#' in value:
                    value = value.split('#')[0].strip()

                # Parse the value
                config[key] = parse_value(value)

    return config


def parse_value(value):
    """Parse a configuration value from string to appropriate Python type.

    Args:
        value: String value from config file

    Returns:
        Parsed value (str, int, float, bool, or set)
    """
    # Remove quotes if present
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]

    # Parse integers
    if re.match(r'^-?\d+$', value):
        return int(value)

    # Parse floats
    if re.match(r'^-?\d+\.\d+$', value):
        return float(value)

    # Parse booleans
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'

    # Parse sets (e.g., {"a","b","c"})
    if value.startswith('{') and value.endswith('}'):
        # Extract items from set notation
        items = value[1:-1].split(',')
        parsed_items = set()
        for item in items:
            item = item.strip()
            # Remove quotes from each item
            if (item.startswith('"') and item.endswith('"')) or \
               (item.startswith("'") and item.endswith("'")):
                item = item[1:-1]
            parsed_items.add(item)
        return parsed_items

    # Return as string if no other type matches
    return value


# Load configuration
_config = load_config()

# Load Cell credentials
_cell_creds = load_cell_credentials()

# Export Cell credentials
HOST = _cell_creds['host']
PRIVATE_KEY = _cell_creds['private_key']
PUBLIC_KEY = _cell_creds['public_key']

# Export all configuration variables
LOG_FILE = _config.get("LOG_FILE", "agent.log")
DB_PATH = _config.get("DB_PATH", "agent_memory.db")
TASKS_DIR = _config.get("TASKS_DIR", "./tasks")

MODEL_MAX_TOKENS = _config.get("MODEL_MAX_TOKENS", 512)
MODEL_TEMPERATURE = _config.get("MODEL_TEMPERATURE", 0.3)
MODEL_TOP_P = _config.get("MODEL_TOP_P", 0.85)

VLLM_MODEL_NAME = _config.get("VLLM_MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")
VLLM_HOST = _config.get("VLLM_HOST", "127.0.0.1")
VLLM_PORT = _config.get("VLLM_PORT", 8000)
VLLM_API_BASE = _config.get("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

CONVERSATION_HISTORY_LIMIT = _config.get("CONVERSATION_HISTORY_LIMIT", 10)
KNOWLEDGE_RETRIEVAL_LIMIT = _config.get("KNOWLEDGE_RETRIEVAL_LIMIT", 5)
FTS5_STOPWORDS = _config.get("FTS5_STOPWORDS", {"what","is","the","of","and","how","do","does","a","an","to","it","i","can","you"})
