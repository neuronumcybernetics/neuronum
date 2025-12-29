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
import subprocess
import sys
import os
import signal 

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
@click.option('--server-dir', default=None, help='Path to neuronum-server directory (default: ./neuronum-server)')
def start_server(server_dir):
    """Sets up and starts the Neuronum Server with vLLM."""

    # Determine server directory
    if server_dir is None:
        server_dir = Path.cwd() / "neuronum-server"
    else:
        server_dir = Path(server_dir)

    # Check if neuronum-server exists, if not clone it
    if not server_dir.exists():
        click.echo("📦 Neuronum Server not found. Cloning repository...")
        try:
            subprocess.run([
                "git", "clone",
                "https://github.com/neuronumcybernetics/neuronum-server.git",
                str(server_dir)
            ], check=True)
            click.echo("✅ Repository cloned successfully!")
        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Failed to clone repository: {e}")
            return
        except FileNotFoundError:
            click.echo("❌ Git is not installed. Please install git first.")
            return

    # Check if Cell credentials exist
    if not ENV_FILE.exists():
        click.echo("❌ No Cell credentials found!")
        click.echo("Please run 'neuronum create-cell' or 'neuronum connect-cell' first")
        return

    # Check if server is already running
    server_pid_file = server_dir / ".server_pid"

    if server_pid_file.exists():
        try:
            with open(server_pid_file, 'r') as f:
                pid = int(f.read().strip())
            # Check if process is actually running
            os.kill(pid, 0)  # This will raise an exception if process doesn't exist
            click.echo("⚠️  Neuronum Server is already running!")
            click.echo(f"📋 View logs: tail -f {server_dir}/server.log")
            click.echo(f"🛑 To restart, first run: neuronum stop-agent")
            return
        except (OSError, ValueError, ProcessLookupError):
            # Process is not running, clean up stale PID file
            click.echo("ℹ️  Cleaning up stale PID file...")
            server_pid_file.unlink(missing_ok=True)

    # Navigate to server directory and run setup script
    click.echo(f"🚀 Starting Neuronum Server from {server_dir}...")

    start_script = server_dir / "start_neuronum_server.sh"
    if not start_script.exists():
        click.echo(f"❌ Start script not found at {start_script}")
        return

    try:
        # Make script executable
        os.chmod(start_script, 0o755)

        # Run the start script
        result = subprocess.run(
            ["bash", str(start_script)],
            cwd=str(server_dir),
            check=False
        )

        if result.returncode == 0:
            click.echo("\n✅ Neuronum Server started successfully!")
            click.echo(f"📋 View logs: tail -f {server_dir}/server.log")
            click.echo(f"📋 View vLLM logs: tail -f {server_dir}/vllm_server.log")
            click.echo("🛑 Stop server: neuronum stop-agent")
        else:
            click.echo(f"\n⚠️ Server start script exited with code {result.returncode}")

    except Exception as e:
        click.echo(f"❌ Error starting server: {e}")


@click.command()
@click.option('--server-dir', default=None, help='Path to neuronum-server directory (default: ./neuronum-server)')
def stop_server(server_dir):
    """Stops the Neuronum Server and vLLM processes."""

    # Determine server directory
    if server_dir is None:
        server_dir = Path.cwd() / "neuronum-server"
    else:
        server_dir = Path(server_dir)

    if not server_dir.exists():
        click.echo(f"❌ Neuronum Server directory not found at {server_dir}")
        return

    stop_script = server_dir / "stop_neuronum_server.sh"
    if not stop_script.exists():
        click.echo(f"❌ Stop script not found at {stop_script}")
        return

    click.echo("🛑 Stopping Neuronum Server...")

    try:
        # Make script executable
        os.chmod(stop_script, 0o755)

        # Run the stop script
        subprocess.run(
            ["bash", str(stop_script)],
            cwd=str(server_dir),
            check=True
        )

        click.echo("✅ Neuronum Server stopped successfully!")

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Error stopping server: {e}")
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}")


# --- CLI Registration ---
cli.add_command(create_cell)
cli.add_command(connect_cell)
cli.add_command(view_cell)
cli.add_command(delete_cell)
cli.add_command(disconnect_cell)
cli.add_command(init_tool)
cli.add_command(update_tool)
cli.add_command(delete_tool)
cli.add_command(start_server)
cli.add_command(stop_server)

if __name__ == "__main__":
    cli()