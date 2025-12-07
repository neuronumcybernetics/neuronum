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
    try:
        NEURONUM_PATH.mkdir(parents=True, exist_ok=True)
        
        # Save .env with host and mnemonic (Sensitive data)
        env_content = f"HOST={host}\nMNEMONIC=\"{mnemonic}\"\nTYPE={cell_type}\n"
        ENV_FILE.write_text(env_content)
        
        # Save PEM files
        PUBLIC_KEY_FILE.write_bytes(pem_public)
        PRIVATE_KEY_FILE.write_bytes(pem_private)
        
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

# ... (existing CLI Group and Commands)

@click.command()
def create_cell():
    """Creates a new Cell with a randomly generated key pair."""
    cell_type = questionary.select(
        "Choose Cell type:",
        choices=["business", "employee"]
    ).ask()

    if not cell_type:
        click.echo("Cell creation canceled.")
        return
    
    if cell_type == "employee":
        # Load all credentials to check for the required Business key
        credentials = load_credentials()
        if not credentials:
            # Error already echoed in helper
            return

        host = credentials['host']
        private_key = credentials['private_key']
        
        # 1. Check if the user is connected to a Business Cell (must be the Business owner to register)
        if not host:
            click.echo("\n❌ This action is restricted to **Business Cells** only and requires a connected Business Cell.")
            click.echo("Please run `create-cell` and select 'business', or run `connect-cell` first.")
            return

        # 2. Get the unique identifier and generate new keys for the employee
        employee_name = questionary.text("Enter the unique **Work ID** (Employee Username, e.g., 'jane.doe'):").ask()
        if not employee_name:
            click.echo("Work ID registration canceled.")
            return
        
        employee_mnemonic = Bip39MnemonicGenerator().FromWordsNumber(12)
        _, _, _, employee_pem_public = derive_keys_from_mnemonic(employee_mnemonic)
        
        if not employee_pem_public:
            return

        employee_public_key = employee_pem_public.decode("utf-8")

        # 3. Prepare the signed message (Business Cell signs the new Work ID key)
        timestamp = str(int(time.time()))
        message = f"host={host};timestamp={timestamp}"
        signature_b64 = sign_message(private_key, message.encode())

        if not signature_b64:
            return

        # 4. Call API to Associate
        click.echo(f"🔗 Requesting registration of Employee '{employee_name}' with Business Cell '{host}'...")
        url = f"{API_BASE_URL}/create_employee_cell"
        register_data = {
            "host": host,
            "signed_message": signature_b64,
            "message": message,
            "employee_public_key": employee_public_key,
            "employee_name": employee_name
        }

        try:
            response = requests.post(url, json=register_data, timeout=10)
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("status") == "verified" and response_data.get("host"):
                work_cell_id = response_data.get("host")
                if work_cell_id:
                    click.echo("\n" + "=" * 60)
                    click.echo(f"  ✅ WORK ID REGISTERED on Server.")
                    click.echo(f"  Work ID Host: {work_cell_id}")
                    click.echo("\n  >>> INSTRUCT THE EMPLOYEE TO RUN `python neuronum_cli.py connect-cell`")
                    click.echo(f"  >>> and enter the following MNEMONIC:")
                    click.echo("-" * 60)
                    click.echo(f"  {employee_mnemonic}")
                    click.echo("-" * 60)
            else:
                click.echo(f"❌ Registration failed. Server detail: {response_data.get('detail', 'Unknown failure.')}")
                return
                
        except requests.exceptions.RequestException as e:
            click.echo(f"❌ Error communicating with the server: {e}")
            return
        
        return # Exit the functio

    # 1. Generate Mnemonic and Keys for both types
    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(12)
    private_key, public_key, pem_private, pem_public = derive_keys_from_mnemonic(mnemonic)

    if not private_key:
        return

    public_key_pem_str = pem_public.decode("utf-8")
    
    # --- Business Cell Logic (DNS Challenge) ---
    if cell_type == "business":
        company_name = questionary.text("Enter your full Company Name e.g., Neuronum Cybernetics UG").ask()
        domain = questionary.text("Enter your FQDN (e.g., mycompany.com):").ask()
        if not domain:
            click.echo("Business cell creation canceled. Host is required.")
            return

        # Generate the DNS challenge value
        challenge_value = create_dns_challenge_value(pem_public)
        
        if not challenge_value:
            return

        # 2. Instruct User on DNS TXT Record
        click.echo("\n" + "=" * 60)
        click.echo("⚠️ DNS TXT Challenge Required")
        click.echo("=" * 60)
        click.echo(f"To prove ownership of '{domain}', please create a **DNS TXT record**.")
        click.echo(f"This record must be placed on the subdomain **_neuronum.{domain}**.")
        click.echo(f"\nName: **_neuronum.{domain}**")
        click.echo(f"Type:      **TXT**")
        click.echo(f"Value:     **{challenge_value}**")
        click.echo("-" * 60)
        
        # Pause for user action
        questionary.press_any_key_to_continue("Press any key to continue once the DNS record is published...").ask()
        click.echo("Attempting verification...")

        # 3. Call API to Create/Verify Cell (Pass public_key, host, and challenge)
        url = f"{API_BASE_URL}/create_business_cell"
        create_data = {
            "public_key": public_key_pem_str,
            "domain": domain,
            "challenge_value": challenge_value,
            "company_name": company_name # Optional: Server might re-calculate but good to send
        }
        
        try:
            # Server will check DNS for the TXT record, then create the cell
            response = requests.post(url, json=create_data, timeout=30) # Increased timeout for DNS propagation
            response.raise_for_status()
            response_data = response.json()
            
            # Check if server confirmed verification and creation
            if response_data.get("status") == "verified" and response_data.get("host"):
                # 4. Save Credentials
                host = response_data.get("host")
                cell_type = response_data.get("cell_type")
                if host and cell_type:
                    if save_credentials(host, mnemonic, pem_public, pem_private, cell_type):
                        click.echo("\n" + "=" * 50)
                        click.echo("  ✅ BUSINESS CELL CREATED! DNS verified and keys saved.")
                        click.echo(f"  Host: {host}")
                        click.echo(f"  Mnemonic (CRITICAL! Back this up!):")
                        click.echo(f"  {mnemonic}")
                        click.echo("-" * 50)
                        click.echo(f"Credentials saved to: {NEURONUM_PATH}")
                    # else: Error saving already echoed in helper
            else:
                click.echo(f"❌ Verification failed. Server response: {response_data.get('detail', 'Unknown failure.')}")
                return

        except requests.exceptions.HTTPError as e:
        # This catches all 4xx and 5xx errors.
            try:
                # Attempt to parse the server's detailed JSON error body (FastAPI format)
                error_data = e.response.json()
                error_detail = error_data.get("detail", "Unknown server error.")
                
                # Print the specific detail message provided by the server
                click.echo(f"❌ Verification failed. HTTP {e.response.status_code} Error: {error_detail}")

                # Specific handling for the DNS verification failure (403)
                if e.response.status_code == 403:
                    click.echo("\n👉 Please double-check that the TXT record is published and correctly set.")

            except:
                # If the response isn't JSON or doesn't have a 'detail' field
                click.echo(f"❌ Server Error ({e.response.status_code}): {e.response.text}")
            return

        except requests.exceptions.RequestException as e:
            # This catches network issues (DNS failure, connection refused, timeout, etc.)
            click.echo(f"❌ Network Error: Could not communicate with the server. Details: {e}")
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
"""
Simple Standardized MCP Server Example
Demonstrates the official MCP protocol with stdio transport.
"""

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create server instance
app = Server("simple-example")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools using standard MCP protocol."""
    return [
        Tool(
            name="echo",
            description="Echo back a message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo back"
                    }
                },
                "required": ["message"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls using standard MCP protocol."""

    if name == "echo":
        message = arguments.get("message", "")
        return [TextContent(
            type="text",
            text=f"Echo: {message}"
        )]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
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
            tool_id = response.json().get("tool_id", False)
            click.echo(f"Neuronum Tool '{tool_id}' updated!")
        except requests.exceptions.RequestException as e:
            click.echo(f"❌ Error communicating with the server during deletion: {e}")
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


# --- CLI Registration ---
cli.add_command(create_cell)
cli.add_command(connect_cell)
cli.add_command(view_cell)
cli.add_command(delete_cell)
cli.add_command(disconnect_cell)
cli.add_command(init_tool)
cli.add_command(update_tool)
cli.add_command(delete_tool)

if __name__ == "__main__":
    cli()