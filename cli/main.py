import click
import questionary
from pathlib import Path
import requests
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


def save_credentials(host: str, mnemonic: str, pem_public: bytes, pem_private: bytes):
    """Saves host, mnemonic, and keys to the .neuronum directory."""
    try:
        NEURONUM_PATH.mkdir(parents=True, exist_ok=True)
        
        # Save .env with host and mnemonic (Sensitive data)
        env_content = f"HOST={host}\nMNEMONIC=\"{mnemonic}\""
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

@click.command()
def create_cell():
    """Creates a new Community Cell with a randomly generated key pair."""
    
    # 1. Generate Mnemonic and Keys
    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(12)
    private_key, public_key, pem_private, pem_public = derive_keys_from_mnemonic(mnemonic)

    if not private_key:
        return

    # 2. Call API to Create Cell
    click.echo("🔗 Requesting new cell creation from server...")
    url = f"{API_BASE_URL}/create_cell"
    create_data = {"public_key": pem_public.decode("utf-8")}

    try:
        response = requests.post(url, json=create_data, timeout=10)
        response.raise_for_status()
        host = response.json().get("host")

    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error communicating with the server: {e}")
        return

    # 3. Save Credentials
    if host:
        if save_credentials(host, mnemonic, pem_public, pem_private):
            click.echo("\n" + "=" * 50)
            click.echo("  ✅ WELCOME TO NEURONUM! Cell Created Successfully.")
            click.echo("=" * 50)
            click.echo(f"  Host: {host}")
            click.echo(f"  Mnemonic (CRITICAL! Back this up!):")
            click.echo(f"  {mnemonic}")
            click.echo("-" * 50)
            click.echo(f"Credentials saved to: {NEURONUM_PATH}")
        else:
            # Error saving credentials already echoed in helper
            pass
    else:
        click.echo("❌ Error: Server did not return a host. Cell creation failed.")


@click.command()
def connect_cell():
    """Connects to an existing Community Cell using a 12-word mnemonic."""

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
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Error connecting to cell: {e}")
        return

    # 5. Save Credentials
    if host:
        if save_credentials(host, mnemonic, pem_public, pem_private):
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


# --- CLI Registration ---
cli.add_command(create_cell)
cli.add_command(view_cell)
cli.add_command(connect_cell)
cli.add_command(delete_cell)

if __name__ == "__main__":
    cli()
