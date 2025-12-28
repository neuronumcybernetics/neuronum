import click
import questionary
from pathlib import Path
import requests
import asyncio
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
import base64
import time
import hashlib
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator
from bip_utils import Bip39MnemonicValidator, Bip39Languages 
import json 

# --- Configuration Constants ---
NEURONUM_PATH = Path.home() / ".neuronum"
ENV_FILE = NEURONUM_PATH / ".env"
PUBLIC_KEY_FILE = NEURONUM_PATH / "public_key.pem"
PRIVATE_KEY_FILE = NEURONUM_PATH / "private_key.pem"
API_BASE_URL = "https://neuronum.net/api"

# --- Utility Functions ---

def sign_message(private_key: EllipticCurvePrivateKey, message: bytes) -> str:
    """Signs a message using the given private key and returns a base64 encoded signature."""
    try:
        signature = private_key.sign(
            message,
            ec.ECDSA(hashes.SHA256())
        )
        return base64.b64encode(signature).decode()
    except Exception as e:
        click.echo(f"❌ Error signing message: {e}")
        return ""

def derive_keys_from_mnemonic(mnemonic: str):
    """Derives EC-SECP256R1 keys from a BIP-39 mnemonic's seed."""
    try:
        seed = Bip39SeedGenerator(mnemonic).Generate()
        # Hash the seed to get a deterministic and strong key derivation input
        digest = hashlib.sha256(seed).digest()
        int_key = int.from_bytes(digest, "big")
        
        # Derive the private key
        private_key = ec.derive_private_key(int_key, ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()

        # Serialize keys to PEM format
        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        pem_public = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_key, public_key, pem_private, pem_public
    
    except Exception as e:
        click.echo(f"❌ Error generating keys from mnemonic: {e}")
        return None, None, None, None

def base64url_encode(data: bytes) -> str:
    """Base64url encodes bytes (no padding, URL-safe characters)."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def create_dns_challenge_value(public_key_pem: bytes) -> str:
    """
    Creates a DNS TXT challenge value from the public key.
    
    This simulates creating an ACME-style key authorization by hashing 
    the public key (a proxy for account key) and then base64url encoding it.
    """
    try:
        # A simple, secure challenge value: SHA256(PublicKey_PEM) base64url encoded
        key_hash = hashlib.sha256(public_key_pem).digest()
        challenge_value = base64url_encode(key_hash)
        return challenge_value
    except Exception as e:
        click.echo(f"❌ Error creating DNS challenge value: {e}")
        return ""

def save_credentials(host: str, mnemonic: str, pem_public: bytes, pem_private: bytes, cell_type: str):
    """Saves host, mnemonic, and keys to the .neuronum directory."""
    import os
    try:
        NEURONUM_PATH.mkdir(parents=True, exist_ok=True)

        # Save .env with host and mnemonic (Sensitive data)
        env_content = f"HOST={host}\nMNEMONIC=\"{mnemonic}\"\nTYPE={cell_type}\n"
        ENV_FILE.write_text(env_content)
        # Set restrictive permissions on .env file (600)
        os.chmod(ENV_FILE, 0o600)

        # Save PEM files
        PUBLIC_KEY_FILE.write_bytes(pem_public)
        # Public key can be world-readable (644)
        os.chmod(PUBLIC_KEY_FILE, 0o644)

        PRIVATE_KEY_FILE.write_bytes(pem_private)
        # Private key must be owner-only (600)
        os.chmod(PRIVATE_KEY_FILE, 0o600)

        return True
    except Exception as e:
        click.echo(f"❌ Error saving credentials: {e}")
        return False

def load_credentials():
    """Loads host, mnemonic, and private key from local files."""
    credentials = {}
    try:
        # Load .env data (Host and Mnemonic)
        if not ENV_FILE.exists():
            click.echo("Error: No credentials found. Please create or connect a cell first.")
            return None

        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Clean up quotes from mnemonic
                    credentials[key] = value.strip().strip('"')

        credentials['host'] = credentials.get("HOST")
        credentials['mnemonic'] = credentials.get("MNEMONIC")
        
        # Load Private Key
        with open(PRIVATE_KEY_FILE, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )
            credentials['private_key'] = private_key
            credentials['public_key'] = private_key.public_key()

        return credentials
    
    except FileNotFoundError:
        click.echo("Error: Credentials files are incomplete. Try deleting the '.neuronum' folder or reconnecting.")
        return None
    except Exception as e:
        click.echo(f"Error loading credentials: {e}")
        return None

# --- CLI Group ---

@click.group()
def cli():
    """Neuronum CLI Tool for Community Cell management."""
    pass

# --- CLI Commands ---

@click.command()
def create_cell():
    """Creates a new Community Cell with a freshly generated 12-word mnemonic."""

    click.echo("🆕 Creating a new Community Cell...")
    click.echo("⚠️  Save your mnemonic in a secure location! You'll need it to access your Cell.\n")

    # 1. Generate a new 12-word mnemonic
    mnemonic_obj = Bip39MnemonicGenerator().FromWordsNumber(12)
    mnemonic = str(mnemonic_obj)

    # 2. Derive keys from the mnemonic
    private_key, public_key, pem_private, pem_public = derive_keys_from_mnemonic(mnemonic)
    if not private_key:
        return

    # 3. Generate SSH public key (OpenSSH format)
    try:
        ssh_public = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
    except Exception as e:
        click.echo(f"❌ Error generating SSH public key: {e}")
        return

    # 4. Call API to create the cell
    click.echo("📡 Registering new Cell on Neuronum network...")
    url = f"{API_BASE_URL}/create_community_cell"

    payload = {
        "public_key": pem_public.decode("utf-8"),
        "ssh_public_key": ssh_public.decode("utf-8")
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        response_data = response.json()

        if response_data.get("success") == "True" and response_data.get("host"):
            host = response_data.get("host")
            cell_type = "community"  # New cells are community type

            # 5. Save credentials locally
            if save_credentials(host, mnemonic, pem_public, pem_private, cell_type):
                click.echo(f"\n✅ Community Cell created successfully!")
                click.echo(f"🆔 Host: {host}")
                click.echo(f"\n🔑 Your 12-word mnemonic (SAVE THIS SECURELY):")
                click.echo(f"   {mnemonic}")
                click.echo(f"\n💡 This mnemonic is the ONLY way to recover your Cell.")
                click.echo(f"   Write it down and store it in a safe place!\n")
            else:
                click.echo("⚠️  Cell created on server but failed to save locally.")
                click.echo(f"Your mnemonic: {mnemonic}")
        else:
            error_msg = response_data.get("message", "Unknown error")
            click.echo(f"❌ Failed to create Cell: {error_msg}")

    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error communicating with server: {e}")
        return


@click.command()
def connect_cell():
    """Connects to an existing Cell using a 12-word mnemonic."""

    # 1. Get and Validate Mnemonic
    mnemonic = questionary.text("Enter your 12-word BIP-39 mnemonic (space separated):").ask()

    if not mnemonic:
        click.echo("Connection canceled.")
        return

    mnemonic = " ".join(mnemonic.strip().split())
    words = mnemonic.split()

    if len(words) != 12:
        click.echo("❌ Mnemonic must be exactly 12 words.")
        return

    if not Bip39MnemonicValidator(Bip39Languages.ENGLISH).IsValid(mnemonic):
      click.echo("❌ Invalid mnemonic. Please ensure all words are valid BIP-39 words.")
      return

    # 2. Derive Keys
    private_key, public_key, pem_private, pem_public = derive_keys_from_mnemonic(mnemonic)
    if not private_key:
        return
    
    # 3. Prepare Signed Message
    timestamp = str(int(time.time()))
    public_key_pem_str = pem_public.decode('utf-8')
    message = f"public_key={public_key_pem_str};timestamp={timestamp}"
    signature_b64 = sign_message(private_key, message.encode())

    if not signature_b64:
        return

    # 4. Call API to Connect
    click.echo("🔗 Attempting to connect to cell...")
    url = f"{API_BASE_URL}/connect_cell"
    connect_data = {
        "public_key": public_key_pem_str,
        "signed_message": signature_b64,
        "message": message
    }

    try:
        response = requests.post(url, json=connect_data, timeout=10)
        response.raise_for_status()
        host = response.json().get("host")
        cell_type = response.json().get("cell_type")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error connecting to cell: {e}")
        return

    # 5. Save Credentials
    if host and cell_type:
        if save_credentials(host, mnemonic, pem_public, pem_private, cell_type):
            click.echo(f"🔗 Successfully connected to Community Cell '{host}'.")
        # Error saving credentials already echoed in helper
    else:
        click.echo("❌ Failed to retrieve host from server. Connection failed.")


@click.command()
def view_cell():
    """Displays the connection status and host name of the current cell."""
    
    credentials = load_credentials()
    
    if credentials:
        click.echo("\n--- Neuronum Cell Status ---")
        click.echo(f"Status: ✅ Connected")
        click.echo(f"Host:   {credentials['host']}")
        click.echo(f"Path:   {NEURONUM_PATH}")
        click.echo(f"Key Type: {credentials['private_key'].curve.name} (SECP256R1)")
        click.echo("----------------------------")


@click.command()
def delete_cell():
    """Deletes the locally stored credentials and requests cell deletion from the server."""
    
    # 1. Load Credentials
    credentials = load_credentials()
    if not credentials:
        # Error already echoed in helper
        return

    host = credentials['host']
    private_key = credentials['private_key']

    # 2. Confirmation
    confirm = click.confirm(f"Are you sure you want to permanently delete connection to '{host}'?", default=False)
    if not confirm:
        click.echo("Deletion canceled.")
        return

    # 3. Prepare Signed Message
    timestamp = str(int(time.time()))
    message = f"host={host};timestamp={timestamp}"
    signature_b64 = sign_message(private_key, message.encode())

    if not signature_b64:
        return

    # 4. Call API to Delete
    click.echo(f"🗑️ Requesting deletion of cell '{host}'...")
    url = f"{API_BASE_URL}/delete_cell"
    payload = {
        "host": host,
        "signed_message": signature_b64,
        "message": message
    }

    try:
        response = requests.delete(url, json=payload, timeout=10)
        response.raise_for_status()
        status = response.json().get("status", False)
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error communicating with the server during deletion: {e}")
        return

    # 5. Cleanup Local Files
    if status:
        try:
            ENV_FILE.unlink(missing_ok=True)
            PRIVATE_KEY_FILE.unlink(missing_ok=True)
            PUBLIC_KEY_FILE.unlink(missing_ok=True)
            
            click.echo(f"✅ Neuronum Cell '{host}' has been deleted and local credentials removed.")
        except Exception as e:
            click.echo(f"⚠️ Warning: Successfully deleted cell on server, but failed to clean up all local files: {e}")
    else:
        click.echo(f"❌ Neuronum Cell '{host}' deletion failed on server.")


@click.command()
def disconnect_cell():
    """Removes local credentials without deleting the cell on the server."""
    
    # Check if any files exist to avoid unnecessary actions
    if not ENV_FILE.exists() and not PRIVATE_KEY_FILE.exists() and not PUBLIC_KEY_FILE.exists():
        click.echo("ℹ️ No local Neuronum credentials found to disconnect.")
        return

    # 1. Confirmation
    confirm = click.confirm("Are you sure you want to disconnect? This will remove all local key files and the mnemonic, but your cell will remain active on the server.", default=False)
    if not confirm:
        click.echo("Disconnection canceled.")
        return

    # 2. Cleanup Local Files
    click.echo(f"🗑️ Removing local credentials from: {NEURONUM_PATH}")
    
    files_removed = 0
    
    try:
        if ENV_FILE.exists():
            ENV_FILE.unlink()
            files_removed += 1
        
        if PRIVATE_KEY_FILE.exists():
            PRIVATE_KEY_FILE.unlink()
            files_removed += 1
            
        if PUBLIC_KEY_FILE.exists():
            PUBLIC_KEY_FILE.unlink()
            files_removed += 1
            
        if files_removed > 0:
            click.echo(f"✅ Successfully disconnected. Your credentials are now removed locally.")
            click.echo("You can reconnect later using your 12-word mnemonic (via `connect-cell`).")
        else:
            click.echo("ℹ️ No credentials were found to remove.")
            
    except Exception as e:
        click.echo(f"❌ Error during local file cleanup: {e}")


@click.command()
def init_tool():
    name = click.prompt("Enter a Tool Name").strip()
    descr = click.prompt("Enter a brief Tool description").strip()
    asyncio.run(async_init_tool(descr, name))

async def async_init_tool(descr, name):
    credentials = load_credentials()
    if not credentials:
        return

    host = credentials['host']
    private_key = credentials['private_key']

    # 3. Prepare Signed Message
    timestamp = str(int(time.time()))
    message = f"host={host};timestamp={timestamp}"
    signature_b64 = sign_message(private_key, message.encode())

    if not signature_b64:
        return

    url = f"{API_BASE_URL}/init_tool"
    payload = {
        "host": host,
        "signed_message": signature_b64,
        "message": message,
        "name": name,
        "descr": descr
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        tool_id = response.json().get("tool_id", False)
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error communicating with the server during deletion: {e}")
        return
    
    tool_folder = name + "_" + tool_id
    project_path = Path(tool_folder)
    project_path.mkdir(exist_ok=True)
                                                                                                           
    tool_path = project_path / "tool.py"
    tool_path.write_text('''\
from mcp.server.fastmcp import FastMCP

# Create server instance
mcp = FastMCP("simple-example")

@mcp.tool()
def echo(message: str) -> str:
    """Echo back a message"""
    return f"Echo: {message}"

if __name__ == "__main__":
    mcp.run()
''')
    
    config_path = project_path / "tool.config"
    await asyncio.to_thread(
    config_path.write_text,
f"""{{
  "tool_meta": {{
    "tool_id": "{tool_id}",
    "version": "1.0.0",
    "name": "{name}",
    "description": "{descr}",
    "audience": "private",
    "logo": "https://neuronum.net/static/logo.png"
  }},
  "legals": {{
    "terms": "https://url_to_your/terms",
    "privacy_policy": "https://url_to_your/privacy_policy"
  }},
  "requirements": [],
  "variables": []
}}"""

)
    click.echo(f"Neuronum Tool '{tool_id}' initialized!")


@click.command()
def update_tool():
    try:
        with open("tool.config", "r") as f:
            config_data = json.load(f)

        with open("tool.py", "r") as f:
            tool_script = f.read()

        audience = config_data.get("tool_meta", {}).get("audience", "")
        tool_id = config_data.get("tool_meta", {}).get("tool_id", "")

    except FileNotFoundError as e:
        click.echo(f"Error: File not found - {e.filename}")
        return
    except click.ClickException as e:
        click.echo(e.format_message())
        return
    except Exception as e:
        click.echo(f"Error reading files: {e}")
        return

    asyncio.run(async_update_tool(config_data, tool_script, tool_id, audience))


async def async_update_tool(config_data, tool_script: str, tool_id: str, audience: str):
    credentials = load_credentials()
    if not credentials:
        return

    host = credentials['host']
    private_key = credentials['private_key']

    # 3. Prepare Signed Message
    timestamp = str(int(time.time()))
    message = f"host={host};timestamp={timestamp}"
    signature_b64 = sign_message(private_key, message.encode())

    if not signature_b64:
        return

    url = f"{API_BASE_URL}/update_tool"
    payload = {
        "host": host,
        "signed_message": signature_b64,
        "message": message,
        "tool_id": tool_id,
        "config": config_data,
        "script": tool_script,
        "audience": audience
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        response_data = response.json()
        
        if response_data.get("success"):
            tool_id = response_data.get("tool_id")
            message = response_data.get("message", "Tool updated!")
            
            # Check if DNS verification is needed
            if "verify Ownership" in message:
                click.echo(f"Tool '{tool_id}' updated as private.")
                click.echo(f"{message}")
                click.echo(f"Please use the ceLL Client (ceLLai) software to verify ownership over your domain and publish tools")
            else:
                click.echo(f"✅ Tool '{tool_id}' updated successfully!")
                if audience == "public":
                    click.echo(f"Audience: Public")
                else:
                    click.echo(f"Audience: Private")
        else:
            error_message = response_data.get("message", "Unknown error")
            click.echo(f"❌ Failed to update tool: {error_message}")
            
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error communicating with the server: {e}")
        return

                   

@click.command()
def delete_tool():
    try:
        with open("tool.config", "r") as f:
            config_data = json.load(f)

        tool_id = config_data.get("tool_meta", {}).get("tool_id", "")

    except FileNotFoundError as e:
        click.echo(f"Error: File not found - {e.filename}")
        return
    except click.ClickException as e:
        click.echo(e.format_message())
        return
    except Exception as e:
        click.echo(f"Error reading files: {e}")
        return

    # 1. Load Credentials
    credentials = load_credentials()
    if not credentials:
        # Error already echoed in helper
        return

    host = credentials['host']
    private_key = credentials['private_key']

    # 2. Confirmation
    confirm = click.confirm(f"Are you sure you want to permanently delete your Neuronu Tool '{tool_id}'?", default=False)
    if not confirm:
        click.echo("Deletion canceled.")
        return

    # 3. Prepare Signed Message
    timestamp = str(int(time.time()))
    message = f"host={host};timestamp={timestamp}"
    signature_b64 = sign_message(private_key, message.encode())

    if not signature_b64:
        return

    # 4. Call API to Delete
    click.echo(f"🗑️ Requesting deletion of cell '{host}'...")
    url = f"{API_BASE_URL}/delete_tool"
    payload = {
        "host": host,
        "signed_message": signature_b64,
        "message": message,
        "tool_id": tool_id
    }

    try:
        response = requests.delete(url, json=payload, timeout=10)
        response.raise_for_status()
        status = response.json().get("status", False)
        if status:
            click.echo(f"✅ Neuronum Tool '{tool_id}' has been deleted!")
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error communicating with the server during deletion: {e}")
        return


@click.command()
def serve_agent():
    """Downloads, configures, and starts the Neuronum Server."""
    import os
    import subprocess
    import shutil

    click.echo("🤖 Neuronum Server Setup\n")

    # Check if git is installed
    if not shutil.which("git"):
        click.echo("❌ Git is not installed. Please install git first.")
        return

    # Check if Python 3 is installed
    if not shutil.which("python3"):
        click.echo("❌ Python 3 is not installed. Please install Python 3.8 or higher.")
        return

    # Prompt for installation directory
    default_path = str(Path.home() / "neuronum-server")
    install_path = questionary.text(
        "Where should the agent be installed?",
        default=default_path
    ).ask()

    if not install_path:
        click.echo("❌ Installation cancelled.")
        return

    install_path = Path(install_path).expanduser()

    # Check if directory already exists
    if install_path.exists():
        overwrite = questionary.confirm(
            f"Directory {install_path} already exists. Do you want to overwrite it?",
            default=False
        ).ask()

        if not overwrite:
            click.echo("❌ Installation cancelled.")
            return

        click.echo(f"🗑️  Removing existing directory...")
        shutil.rmtree(install_path)

    # Clone the repository
    click.echo("\n📥 Cloning neuronum-server repository...")
    repo_url = "https://github.com/neuronumcybernetics/neuronum-server.git"

    try:
        subprocess.run(
            ["git", "clone", repo_url, str(install_path)],
            check=True,
            capture_output=True
        )
        click.echo("✅ Repository cloned successfully")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to clone repository: {e.stderr.decode()}")
        return

    # Configuration section
    click.echo("\n⚙️  Agent Configuration\n")

    # Get mnemonic
    use_existing = questionary.confirm(
        "Do you want to use your existing Cell mnemonic from 'neuronum connect-cell'?",
        default=True
    ).ask()

    if use_existing:
        # Try to read from .neuronum/.env
        if ENV_FILE.exists():
            env_content = ENV_FILE.read_text()
            for line in env_content.split('\n'):
                if line.startswith('MNEMONIC='):
                    mnemonic = line.split('=', 1)[1].strip('"')
                    click.echo(f"✅ Using existing Cell mnemonic")
                    break
            else:
                click.echo("❌ Could not find mnemonic in ~/.neuronum/.env")
                mnemonic = questionary.text("Enter your 12-word mnemonic:").ask()
        else:
            click.echo("❌ No existing Cell found. Please run 'neuronum connect-cell' first.")
            mnemonic = questionary.text("Enter your 12-word mnemonic:").ask()
    else:
        mnemonic = questionary.text("Enter your 12-word mnemonic:").ask()

    if not mnemonic:
        click.echo("❌ Mnemonic is required.")
        return

    # Validate mnemonic
    try:
        Bip39MnemonicValidator(mnemonic).Validate()
    except Exception:
        click.echo("❌ Invalid mnemonic. Please check your 12-word phrase.")
        return

    # LLM Model selection
    click.echo("\n🧠 LLM Model Configuration\n")

    model_options = [
        "Qwen/Qwen2.5-3B-Instruct (Recommended - 3B parameters)",
        "Qwen/Qwen2.5-1.5B-Instruct (Lighter - 1.5B parameters)",
        "Qwen/Qwen2.5-7B-Instruct (Larger - 7B parameters, more capable)",
        "Custom (enter your own)"
    ]

    model_choice = questionary.select(
        "Select the LLM model to use:",
        choices=model_options
    ).ask()

    if model_choice.startswith("Custom"):
        model_name = questionary.text(
            "Enter model name (e.g., 'Qwen/Qwen2.5-7B-Instruct'):",
            default="Qwen/Qwen2.5-3B-Instruct"
        ).ask()
    else:
        model_name = model_choice.split(" (")[0]

    # Advanced settings
    configure_advanced = questionary.confirm(
        "Do you want to configure advanced settings? (temperature, max_tokens, etc.)",
        default=False
    ).ask()

    if configure_advanced:
        max_tokens = questionary.text(
            "Max tokens per response:",
            default="512"
        ).ask()

        temperature = questionary.text(
            "Temperature (0.0-1.0, lower = more deterministic):",
            default="0.3"
        ).ask()

        top_p = questionary.text(
            "Top-p nucleus sampling (0.0-1.0):",
            default="0.85"
        ).ask()
    else:
        max_tokens = "512"
        temperature = "0.3"
        top_p = "0.85"

    # Write configuration to server.config
    config_file = install_path / "server.config"

    click.echo("\n📝 Writing configuration...")

    config_content = f"""# ============================================================================
# Neuronum Server CONFIGURATION
# ============================================================================
# This file contains all configuration parameters for the Neuronum Server.
# Modify these values to customize the agent's behavior.

# --- Cell ---
MNEMONIC = "{mnemonic}"


# --- File Paths ---
LOG_FILE = "agent.log"
DB_PATH = "agent_memory.db"
TASKS_DIR = "./tasks"

# --- Model Configuration ---
# Maximum tokens to generate in responses (business use: longer, complete answers)
MODEL_MAX_TOKENS = {max_tokens}

# Temperature for sampling (0.0 = deterministic, 1.0 = creative)
# Lower temperature for business: more focused, consistent, and reliable responses
MODEL_TEMPERATURE = {temperature}

# Nucleus sampling parameter (top-p)
# Lower top-p for business: more predictable and coherent outputs
MODEL_TOP_P = {top_p}

# --- vLLM Server Configuration ---
# Model to load in vLLM server
# Examples: "Qwen/Qwen2.5-3B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct", "meta-llama/Llama-3.2-3B-Instruct"
VLLM_MODEL_NAME = "{model_name}"

# Server host (127.0.0.1 for local only, 0.0.0.0 to allow external connections)
VLLM_HOST = "127.0.0.1"

# Server port
VLLM_PORT = 8000

# Base URL for the vLLM API server (constructed from host and port)
VLLM_API_BASE = "http://127.0.0.1:8000/v1"

# --- Database/RAG Configuration ---
# Number of recent conversation messages to include in context
# Higher for business: better context retention for multi-turn conversations
CONVERSATION_HISTORY_LIMIT = 10

# Maximum number of knowledge chunks to retrieve from database
# Higher for business: more comprehensive knowledge retrieval
KNOWLEDGE_RETRIEVAL_LIMIT = 5

# Stop words to exclude from FTS5 search queries
FTS5_STOPWORDS = {{"what","is","the","of","and","how","do","does","a","an","to","it","i","can","you"}}
"""

    config_file.write_text(config_content)
    click.echo("✅ Configuration saved")

    # Ask if user wants to run setup now
    click.echo("\n🚀 Setup Complete!\n")

    run_now = questionary.confirm(
        "Do you want to start the agent now? (This will create venv, install dependencies, and launch the agent)",
        default=True
    ).ask()

    if run_now:
        click.echo("\n📦 Running setup.sh...\n")
        click.echo("=" * 60)

        try:
            # Make setup.sh executable
            setup_script = install_path / "setup.sh"
            os.chmod(setup_script, 0o755)

            # Run setup.sh
            subprocess.run(
                ["bash", str(setup_script)],
                cwd=str(install_path),
                check=True
            )
        except subprocess.CalledProcessError as e:
            click.echo(f"\n❌ Setup failed. Please check the error above.")
            click.echo(f"\nYou can manually start the agent by running:")
            click.echo(f"  cd {install_path}")
            click.echo(f"  ./setup.sh")
        except KeyboardInterrupt:
            click.echo("\n\n⚠️  Setup interrupted by user.")
    else:
        click.echo("\nTo start the agent later, run:")
        click.echo(f"  cd {install_path}")
        click.echo(f"  ./setup.sh")
        click.echo("\nOr manually:")
        click.echo(f"  cd {install_path}")
        click.echo(f"  python3 -m venv venv")
        click.echo(f"  source venv/bin/activate")
        click.echo(f"  pip install -r requirements.txt")
        click.echo(f"  python start_vllm_server.py  # in separate terminal")
        click.echo(f"  python server.py")


@click.command()
def stop_agent():
    """Stops the running Neuronum Server and vLLM server."""
    import os
    import signal
    import psutil

    click.echo("🛑 Stopping Neuronum Server\n")

    # Check default installation path
    default_path = Path.home() / "neuronum-server"

    # Ask for agent directory
    agent_path = questionary.text(
        "Enter the agent installation directory:",
        default=str(default_path)
    ).ask()

    if not agent_path:
        click.echo("❌ Operation cancelled.")
        return

    agent_path = Path(agent_path).expanduser()

    if not agent_path.exists():
        click.echo(f"❌ Directory {agent_path} does not exist.")
        return

    vllm_pid_file = agent_path / ".vllm_pid"
    stopped_anything = False

    # Stop vLLM server
    if vllm_pid_file.exists():
        try:
            vllm_pid = int(vllm_pid_file.read_text().strip())

            # Check if process exists
            try:
                process = psutil.Process(vllm_pid)
                process_name = process.name()

                click.echo(f"📍 Found vLLM server (PID: {vllm_pid}, Name: {process_name})")

                confirm = questionary.confirm(
                    f"Stop vLLM server?",
                    default=True
                ).ask()

                if confirm:
                    click.echo("⏳ Stopping vLLM server...")
                    process.terminate()

                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=10)
                        click.echo("✅ vLLM server stopped gracefully")
                    except psutil.TimeoutExpired:
                        click.echo("⚠️  vLLM server didn't stop gracefully, forcing...")
                        process.kill()
                        click.echo("✅ vLLM server force-stopped")

                    vllm_pid_file.unlink()
                    stopped_anything = True

            except psutil.NoSuchProcess:
                click.echo(f"⚠️  vLLM server (PID: {vllm_pid}) is not running")
                vllm_pid_file.unlink()

        except Exception as e:
            click.echo(f"❌ Error stopping vLLM server: {e}")
    else:
        click.echo("ℹ️  No vLLM PID file found")

    # Find and stop server.py process
    click.echo("\n🔍 Looking for server.py process...")

    found_agent = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and 'server.py' in ' '.join(cmdline):
                # Check if it's in the correct directory
                cwd = proc.info.get('cwd', '')
                if str(agent_path) in cwd or any(str(agent_path) in arg for arg in cmdline):
                    found_agent = True
                    pid = proc.info['pid']

                    click.echo(f"📍 Found server.py (PID: {pid})")

                    confirm = questionary.confirm(
                        f"Stop server.py?",
                        default=True
                    ).ask()

                    if confirm:
                        click.echo("⏳ Stopping agent...")
                        proc.terminate()

                        try:
                            proc.wait(timeout=10)
                            click.echo("✅ Agent stopped gracefully")
                        except psutil.TimeoutExpired:
                            click.echo("⚠️  Agent didn't stop gracefully, forcing...")
                            proc.kill()
                            click.echo("✅ Agent force-stopped")

                        stopped_anything = True

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if not found_agent:
        click.echo("ℹ️  No server.py process found")

    if stopped_anything:
        click.echo("\n✅ Shutdown complete!")
    else:
        click.echo("\n✅ No running processes found")


# --- CLI Registration ---
cli.add_command(create_cell)
cli.add_command(connect_cell)
cli.add_command(view_cell)
cli.add_command(delete_cell)
cli.add_command(disconnect_cell)
cli.add_command(init_tool)
cli.add_command(update_tool)
cli.add_command(delete_tool)
cli.add_command(serve_agent)
cli.add_command(stop_agent)

if __name__ == "__main__":
    cli()