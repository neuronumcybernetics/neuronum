import aiohttp
import aiofiles
from typing import AsyncGenerator, Optional, Dict, Any, List
import websockets
import json
import asyncio
import base64
import ssl
import os
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from websockets.exceptions import ConnectionClosed, WebSocketException
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from abc import ABC, abstractmethod
from bip_utils import Bip39MnemonicValidator, Bip39Languages, Bip39SeedGenerator, Bip39MnemonicGenerator
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
import hashlib
import asyncio

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Exceptions
class NeuronumError(Exception):
    """Base exception for Neuronum errors"""
    pass


class AuthenticationError(NeuronumError):
    """Raised when authentication fails"""
    pass


class EncryptionError(NeuronumError):
    """Raised when encryption/decryption fails"""
    pass


class CellNotFoundError(NeuronumError):
    """Raised when a cell cannot be found"""
    pass


class NetworkError(NeuronumError):
    """Raised when network operations fail"""
    pass


# Configuration
@dataclass
class ClientConfig:
    """Client configuration settings"""
    network: str = "neuronum.net"
    cache_expiry: int = 3600
    credentials_path: Path = Path.home() / ".neuronum"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 60.0
    websocket_ping_interval: int = 20
    websocket_ping_timeout: int = 10


class CryptoManager:
    """Handles all cryptographic operations"""
    
    def __init__(self, private_key: Optional[ec.EllipticCurvePrivateKey] = None):
        self._private_key = private_key
        self._public_key = private_key.public_key() if private_key else None
    
    def sign_message(self, message: bytes) -> str:
        """Sign a message with the private key"""
        if not self._private_key:
            raise EncryptionError("Private key not available for signing")
        
        try:
            signature = self._private_key.sign(message, ec.ECDSA(hashes.SHA256()))
            return base64.b64encode(signature).decode()
        except Exception as e:
            logger.error("Failed to sign message", exc_info=True)
            raise EncryptionError(f"Message signing failed: {e}")
    
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format"""
        if not self._public_key:
            raise EncryptionError("Public key not available")
        
        pem_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_bytes.decode('utf-8')
    
    def load_public_key_from_pem(self, pem_string: str) -> ec.EllipticCurvePublicKey:
        """Load a public key from PEM format"""
        try:
            return serialization.load_pem_public_key(
                pem_string.encode(), 
                backend=default_backend()
            )
        except Exception as e:
            logger.error("Failed to load public key from PEM", exc_info=True)
            raise EncryptionError(f"Failed to load public key: {e}")
    
    @staticmethod
    def safe_b64decode(data: str) -> bytes:
        """Safely decode base64 with proper padding"""
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += '=' * padding
        return base64.urlsafe_b64decode(data)
    
    def encrypt_with_ecdh_aesgcm(
        self, 
        public_key: ec.EllipticCurvePublicKey, 
        plaintext_dict: Dict[str, Any]
    ) -> Dict[str, str]:
        """Encrypt data using ECDH + AES-GCM"""
        try:
            ephemeral_private = ec.generate_private_key(ec.SECP256R1())
            shared_secret = ephemeral_private.exchange(ec.ECDH(), public_key)
            derived_key = HKDF(
                algorithm=hashes.SHA256(), 
                length=32, 
                salt=None, 
                info=b'handshake data'
            ).derive(shared_secret)
            
            aesgcm = AESGCM(derived_key)
            nonce = os.urandom(12)
            plaintext_bytes = json.dumps(plaintext_dict).encode()
            ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
            
            ephemeral_public_bytes = ephemeral_private.public_key().public_bytes(
                serialization.Encoding.X962, 
                serialization.PublicFormat.UncompressedPoint
            )
            
            return {
                'ciphertext': base64.urlsafe_b64encode(ciphertext).rstrip(b'=').decode(),
                'nonce': base64.urlsafe_b64encode(nonce).rstrip(b'=').decode(),
                'ephemeralPublicKey': base64.urlsafe_b64encode(ephemeral_public_bytes).rstrip(b'=').decode()
            }
        except Exception as e:
            logger.error("Encryption failed", exc_info=True)
            raise EncryptionError(f"Encryption failed: {e}")
    
    def decrypt_with_ecdh_aesgcm(
        self, 
        ephemeral_public_key_bytes: bytes, 
        nonce: bytes, 
        ciphertext: bytes
    ) -> Dict[str, Any]:
        """Decrypt data using ECDH + AES-GCM"""
        if not self._private_key:
            raise EncryptionError("Private key not available for decryption")
        
        try:
            ephemeral_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), ephemeral_public_key_bytes
            )
            shared_secret = self._private_key.exchange(ec.ECDH(), ephemeral_public_key)
            derived_key = HKDF(
                algorithm=hashes.SHA256(), 
                length=32, 
                salt=None, 
                info=b'handshake data'
            ).derive(shared_secret)
            
            aesgcm = AESGCM(derived_key)
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext_bytes.decode())
        except Exception as e:
            logger.error("Decryption failed", exc_info=True)
            raise EncryptionError(f"Decryption failed: {e}")


class CacheManager:
    """Manages cell cache with async file operations"""
    
    def __init__(self, config: ClientConfig):
        self.config = config
        self.cache_file = config.credentials_path / "cells.json"
        self._lock = asyncio.Lock()
        self._memory_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_time: Optional[float] = None
    
    async def get_cells(self) -> List[Dict[str, Any]]:
        """Get cached cells if valid, otherwise fetch new"""
        async with self._lock:
            # Check memory cache first
            if self._is_memory_cache_valid():
                logger.debug("Using in-memory cache")
                return self._memory_cache
            
            # Check file cache
            if await self._is_file_cache_valid():
                logger.debug("Using file cache")
                cells = await self._load_from_file()
                self._update_memory_cache(cells)
                return cells
            
            return None
    
    async def update_cells(self, cells: List[Dict[str, Any]]) -> None:
        """Update cache with new cell data"""
        async with self._lock:
            self._update_memory_cache(cells)
            await self._save_to_file(cells)
    
    def _is_memory_cache_valid(self) -> bool:
        """Check if memory cache is still valid"""
        if not self._memory_cache or not self._cache_time:
            return False
        return (time.time() - self._cache_time) < self.config.cache_expiry
    
    async def _is_file_cache_valid(self) -> bool:
        """Check if file cache is still valid"""
        if not self.cache_file.exists():
            return False
        
        try:
            file_mtime = os.path.getmtime(self.cache_file)
            return (time.time() - file_mtime) < self.config.cache_expiry
        except OSError:
            return False
    
    async def _load_from_file(self) -> List[Dict[str, Any]]:
        """Load cells from cache file"""
        try:
            async with aiofiles.open(self.cache_file, 'r') as f:
                content = await f.read()
                return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load cache file: {e}")
            return []
    
    async def _save_to_file(self, cells: List[Dict[str, Any]]) -> None:
        """Save cells to cache file"""
        try:
            self.config.credentials_path.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(self.cache_file, 'w') as f:
                await f.write(json.dumps(cells, indent=4))
            logger.debug("Cache file updated")
        except Exception as e:
            logger.error(f"Failed to save cache file: {e}")
    
    def _update_memory_cache(self, cells: List[Dict[str, Any]]) -> None:
        """Update in-memory cache"""
        self._memory_cache = cells
        self._cache_time = time.time()


class NetworkClient:
    """Handles all network operations with proper session management"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    def __del__(self):
        """Cleanup: warn if session wasn't properly closed"""
        if self._session and not self._session.closed:
            logger.warning(
                "NetworkClient session was not properly closed. "
                "Use 'async with NetworkClient(...)' or call close() explicitly."
            )
    
    async def _ensure_session(self):
        """Ensure session exists, create if needed"""
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    connector = aiohttp.TCPConnector(
                        limit=100,  # Connection pool limit
                        limit_per_host=30,
                        ttl_dns_cache=300,
                        force_close=False  # Allow connection reuse
                    )
                    timeout = aiohttp.ClientTimeout(
                        total=self.config.timeout,
                        connect=10,
                        sock_read=self.config.timeout
                    )
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout
                    )
                    logger.debug("Created new HTTP session")
    
    async def close(self):
        """Explicitly close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Closed HTTP session")
            self._session = None
    
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def post_request(
        self, 
        url: str, 
        payload: Dict[str, Any],
        retry_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Make POST request with retry logic"""
        await self._ensure_session()
        
        try:
            async with self._session.post(url, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error {e.status} for URL: {url}")
            if retry_count < self.config.max_retries and e.status >= 500:
                return await self._retry_request(url, payload, retry_count)
            raise NetworkError(f"HTTP {e.status} error")
        except aiohttp.ClientError as e:
            logger.error(f"Client error for URL {url}: {e}")
            if retry_count < self.config.max_retries:
                return await self._retry_request(url, payload, retry_count)
            raise NetworkError(f"Client error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for URL {url}: {e}")
            raise NetworkError(f"Unexpected error: {e}")
    
    async def delete_request(
        self,
        url: str,
        payload: Dict[str, Any],
        retry_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Make DELETE request with retry logic"""
        await self._ensure_session()
        
        try:
            async with self._session.delete(url, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error {e.status} for URL: {url}")
            if retry_count < self.config.max_retries and e.status >= 500:
                return await self._retry_delete_request(url, payload, retry_count)
            raise NetworkError(f"HTTP {e.status} error")
        except aiohttp.ClientError as e:
            logger.error(f"Client error for URL {url}: {e}")
            if retry_count < self.config.max_retries:
                return await self._retry_delete_request(url, payload, retry_count)
            raise NetworkError(f"Client error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for URL {url}: {e}")
            raise NetworkError(f"Unexpected error: {e}")
    
    async def _retry_request(
        self, 
        url: str, 
        payload: Dict[str, Any], 
        retry_count: int
    ) -> Optional[Dict[str, Any]]:
        """Retry POST request with exponential backoff"""
        delay = min(
            self.config.retry_delay * (2 ** retry_count),
            self.config.max_retry_delay
        )
        logger.info(f"Retrying POST request in {delay}s (attempt {retry_count + 1})")
        await asyncio.sleep(delay)
        return await self.post_request(url, payload, retry_count + 1)
    
    async def _retry_delete_request(
        self,
        url: str,
        payload: Dict[str, Any],
        retry_count: int
    ) -> Optional[Dict[str, Any]]:
        """Retry DELETE request with exponential backoff"""
        delay = min(
            self.config.retry_delay * (2 ** retry_count),
            self.config.max_retry_delay
        )
        logger.info(f"Retrying DELETE request in {delay}s (attempt {retry_count + 1})")
        await asyncio.sleep(delay)
        return await self.delete_request(url, payload, retry_count + 1)


class BaseClient(ABC):
    """Base client with common functionality"""
    
    def __init__(self, config: Optional[ClientConfig] = None):
        self.config = config or ClientConfig()
        self.env: Dict[str, str] = {}
        self._crypto: Optional[CryptoManager] = None
        self._cache_manager = CacheManager(self.config)
        self._network_client = NetworkClient(self.config)
        self.host = ""
        self.network = self.config.network
    
    @abstractmethod
    def _load_private_key(self) -> Optional[ec.EllipticCurvePrivateKey]:
        """Load private key - to be implemented by subclasses"""
        pass
    
    def _init_crypto(self, private_key: Optional[ec.EllipticCurvePrivateKey]) -> None:
        """Initialize crypto manager with private key"""
        self._crypto = CryptoManager(private_key)
    
    def to_dict(self) -> Dict[str, str]:
        """Create authentication payload"""
        if not self._crypto:
            logger.warning("Crypto manager not initialized")
            timestamp = str(int(time.time()))
            return {
                "host": self.host,
                "signed_message": "",
                "message": f"host={self.host};timestamp={timestamp}"
            }
        
        timestamp = str(int(time.time()))
        message = f"host={self.host};timestamp={timestamp}"
        
        try:
            signed_message = self._crypto.sign_message(message.encode())
        except EncryptionError:
            logger.error("Failed to sign authentication message")
            signed_message = ""
        
        return {
            "host": self.host,
            "signed_message": signed_message,
            "message": message
        }
    
    async def _get_target_cell_public_key(self, cell_id: str) -> str:
        """Get public key for target cell"""
        # Try cached cells first
        cells = await self.list_cells(update=False)
        
        for cell in cells:
            if cell.get('cell_id') == cell_id:
                public_key = cell.get('public_key', {})
                if public_key:
                    return public_key
        
        # Refresh cache and try again
        logger.info(f"Cell {cell_id} not in cache, refreshing")
        cells = await self.list_cells(update=True)
        
        for cell in cells:
            if cell.get('cell_id') == cell_id:
                public_key = cell.get('public_key', {})
                if public_key:
                    return public_key
        
        raise CellNotFoundError(f"Cell not found: {cell_id}")
    
    async def list_cells(self, update: bool = False) -> List[Dict[str, Any]]:
        """List all available cells with optional cache refresh"""
        if not update:
            cached_cells = await self._cache_manager.get_cells()
            if cached_cells is not None:
                return cached_cells

        full_url = f"https://{self.network}/api/list_cells"
        payload = {"cell": self.to_dict()}
        
        try:
            data = await self._network_client.post_request(full_url, payload)
            cells = data.get("Cells", []) if data else []
            await self._cache_manager.update_cells(cells)
            return cells
        except NetworkError as e:
            logger.error(f"Failed to fetch cells: {e}")
            return []
        
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available Neuronum tools"""
        full_url = f"https://{self.network}/api/list_tools"
        payload = {"cell": self.to_dict()}
        
        try:
            data = await self._network_client.post_request(full_url, payload)
            tools = data.get("Tools", []) if data else []
            return tools
        except NetworkError as e:
            logger.error(f"Failed to fetch cells: {e}")
            return []
    
    async def tx_response(
        self,
        transmitter_id: str,
        data: Dict[str, Any],
        client_public_key_str: str
    ) -> None:
        """Send encrypted response to transmitter"""
        if not self._crypto:
            raise EncryptionError("Crypto manager not initialized")
        
        if not client_public_key_str:
            raise ValueError("client_public_key_str is required")
        
        url = f"https://{self.network}/api/tx_response/{transmitter_id}"
        
        public_key = self._crypto.load_public_key_from_pem(client_public_key_str)
        encrypted_payload = self._crypto.encrypt_with_ecdh_aesgcm(public_key, data)
        payload = {"data": encrypted_payload, "cell": self.to_dict()}
        
        await self._network_client.post_request(url, payload)
        logger.info(f"Response sent to transmitter {transmitter_id}")
    
    async def activate_tx(
        self,
        cell_id: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Activate encrypted transaction with cell and return decrypted response"""
        if not self._crypto:
            raise EncryptionError("Crypto manager not initialized")
        
        url = f"https://{self.network}/api/activate_tx/{cell_id}"
        payload = {"cell": self.to_dict()}

        public_key_pem_str = await self._get_target_cell_public_key(cell_id)
        public_key_object = self._crypto.load_public_key_from_pem(public_key_pem_str)

        data_to_encrypt = data.copy()
        data_to_encrypt["public_key"] = self._crypto.get_public_key_pem()
        encrypted_payload = self._crypto.encrypt_with_ecdh_aesgcm(
            public_key_object, 
            data_to_encrypt
        )
        payload["data"] = {"encrypted": encrypted_payload}
        
        response_data = await self._network_client.post_request(url, payload)
        
        if not response_data or "response" not in response_data:
            logger.warning("Unexpected or missing response")
            return response_data
        
        inner_response = response_data["response"]

        if "ciphertext" in inner_response:
            try:
                ephemeral_public_key_bytes = CryptoManager.safe_b64decode(
                    inner_response["ephemeralPublicKey"]
                )
                nonce = CryptoManager.safe_b64decode(inner_response["nonce"])
                ciphertext = CryptoManager.safe_b64decode(inner_response["ciphertext"])
                
                return self._crypto.decrypt_with_ecdh_aesgcm(
                    ephemeral_public_key_bytes, nonce, ciphertext
                )
            except EncryptionError:
                logger.error("Failed to decrypt response")
                return None
        else:
            logger.debug("Received unencrypted response")
            return inner_response
    
    async def sync(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Sync with network and yield operations as they arrive"""
        if not isinstance(self, Cell):
            raise ValueError("sync must be called from a Cell instance")

        cell = getattr(self, 'host', None)
        if not cell:
            raise ValueError("host is required for Cell sync")

        full_url = f"wss://{self.network}/sync/{cell}"

        logger.info(f"Starting sync with {cell}")

        retry_count = 0
        while True:
            try:
                auth_payload = self.to_dict()

                ssl_context = ssl.create_default_context()

                async with websockets.connect(
                    full_url,
                    ssl=ssl_context,
                    ping_interval=self.config.websocket_ping_interval,
                    ping_timeout=self.config.websocket_ping_timeout,
                    close_timeout=10
                ) as ws:
                    await ws.send(json.dumps(auth_payload))
                    logger.info(f"Connected and authenticated to {cell}")
                    retry_count = 0

                    while True:
                        try:
                            raw_operation = await asyncio.wait_for(
                                ws.recv(),
                                timeout=self.config.timeout
                            )
                            operation = json.loads(raw_operation)

                            if "encrypted" in operation.get("data", {}):
                                encrypted_data = operation["data"]["encrypted"]

                                try:
                                    ephemeral_public_key_bytes = CryptoManager.safe_b64decode(
                                        encrypted_data["ephemeralPublicKey"]
                                    )
                                    nonce = CryptoManager.safe_b64decode(
                                        encrypted_data["nonce"]
                                    )
                                    ciphertext = CryptoManager.safe_b64decode(
                                        encrypted_data["ciphertext"]
                                    )

                                    decrypted_data = self._crypto.decrypt_with_ecdh_aesgcm(
                                        ephemeral_public_key_bytes, nonce, ciphertext
                                    )

                                    operation["data"].update(decrypted_data)
                                    operation["data"].pop("encrypted")
                                    yield operation
                                except EncryptionError:
                                    logger.error("Failed to decrypt operation")
                            else:
                                logger.warning("Received unencrypted data")

                        except asyncio.TimeoutError:
                            continue
                        except ConnectionClosed as e:
                            logger.warning(f"Connection closed: {e.code} - {e.reason}")
                            break
                        except Exception as e:
                            logger.error(f"Error in receive loop: {e}")
                            break

            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
            except Exception as e:
                logger.error(f"General error in sync: {e}")

            retry_count += 1
            delay = 5.0
            logger.info(f"Reconnecting in {delay}s (attempt {retry_count})")
            await asyncio.sleep(delay)
    
    async def stream(self, cell_id: str, data: Dict[str, Any]) -> bool:
        """Stream encrypted data to target cell via WebSocket"""
        if not isinstance(self, Cell):
            raise ValueError("stream must be called from a Cell instance")
        
        if not getattr(self, 'host', None):
            raise ValueError("host is required for Cell stream")
        
        if not self._crypto:
            raise EncryptionError("Crypto manager not initialized")

        public_key_pem_str = await self._get_target_cell_public_key(cell_id)
        public_key_object = self._crypto.load_public_key_from_pem(public_key_pem_str)

        data_to_encrypt = data.copy()
        data_to_encrypt["public_key"] = self._crypto.get_public_key_pem()
        encrypted_payload = self._crypto.encrypt_with_ecdh_aesgcm(
            public_key_object, 
            data_to_encrypt
        )
        
        auth_payload = self.to_dict()
        data_payload = {"data": {"encrypted": encrypted_payload}}
        send_payload = {**auth_payload, **data_payload}
        
        full_url = f"wss://{self.network}/stream/{cell_id}"
        
        try:
            ssl_context = ssl.create_default_context()
            async with websockets.connect(
                full_url,
                ssl=ssl_context,
                ping_interval=self.config.websocket_ping_interval,
                ping_timeout=self.config.websocket_ping_timeout,
                close_timeout=10
            ) as ws:
                await ws.send(json.dumps(send_payload))
                logger.info(f"Data streamed to {cell_id}")
                
                try:
                    ack = await asyncio.wait_for(ws.recv(), timeout=2)
                    logger.debug(f"Server acknowledgment: {ack}")
                except asyncio.TimeoutError:
                    logger.debug("No immediate acknowledgment (data sent)")
                except Exception as e:
                    logger.warning(f"Error reading acknowledgment: {e}")
                
                return True
        except WebSocketException as e:
            logger.error(f"WebSocket error during stream: {e}")
            return False
        except Exception as e:
            logger.error(f"Error during stream: {e}")
            return False
        
    def sign_connect_message(self, private_key: EllipticCurvePrivateKey, message: bytes) -> str:
        """Sign message using private key and return base64-encoded signature"""
        try:
            signature = private_key.sign(
                message,
                ec.ECDSA(hashes.SHA256())
            )
            return base64.b64encode(signature).decode()
        except Exception as e:
            print(f"Error: Error signing message: {e}")
            return ""
        
    async def connect_cell(self, mnemonic):
        if len(mnemonic.split()) != 12:
            print("false lenght")
            return

        print(mnemonic)
        if not Bip39MnemonicValidator(Bip39Languages.ENGLISH).IsValid(mnemonic):
            print("Error: Invalid mnemonic. Please ensure it is 12 valid BIP-39 words.")
            return

        try:
            seed = Bip39SeedGenerator(mnemonic).Generate()
            digest = hashlib.sha256(seed).digest()
            int_key = int.from_bytes(digest, "big")
            private_key = ec.derive_private_key(int_key, ec.SECP256R1(), default_backend())
            public_key = private_key.public_key()

            pem_private = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            pem_public = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

        except Exception as e:
            print(f"Error: Error generating keys from mnemonic: {e}")
            return
        
        timestamp = str(int(time.time()))
        message = f"public_key={pem_public.decode('utf-8')};timestamp={timestamp}"
        signature_b64 = self.sign_connect_message(private_key, message.encode())

        url = "https://neuronum.net/api/connect_cell"
        connect_data = {
            "public_key": pem_public.decode("utf-8"),
            "signed_message": signature_b64,
            "message": message
        }

        try:
            response_data = await self._network_client.post_request(url, connect_data)

            print(response_data)
            if response_data:
                host = response_data.get("host", False)
                cell_type = response_data.get("cell_type", False)
                operator = response_data.get("operator", False)
                print(host)
            
        except NetworkError as e:
            print(f"Error connecting cell: {e}")
            return
        except Exception as e:
            print(f"Unexpected error during API call: {e}")
            return

        if host:
            neuronum_folder_path = Path.home() / ".neuronum"
            neuronum_folder_path.mkdir(parents=True, exist_ok=True)

            env_path = neuronum_folder_path / ".env"
            env_content = f"HOST={host}\nMNEMONIC=\"{mnemonic}\"\nTYPE={cell_type}\nOPERATOR={operator}\n"

            env_path.write_text(env_content)

            public_key_pem_file = neuronum_folder_path / "public_key.pem"
            with open(public_key_pem_file, "wb") as key_file:
                    key_file.write(pem_public)

            private_key_pem_file = neuronum_folder_path / "private_key.pem"
            with open(private_key_pem_file, "wb") as key_file:
                    key_file.write(pem_private)

            return host
        else:
            print("Error: Failed to retrieve host from server.")

    async def disconnect_cell(self):
        if self.host:
            neuronum_folder_path = Path.home() / ".neuronum"
            files_to_delete = [
                neuronum_folder_path / ".env",
                neuronum_folder_path / "private_key.pem",
                neuronum_folder_path / "public_key.pem",
                neuronum_folder_path / "cells.json",
                neuronum_folder_path / "nodes.json",
            ]

            for file_path in files_to_delete:
                try:
                    if file_path.exists():
                        await asyncio.to_thread(os.unlink, file_path)
                except Exception as e:
                    print(f"Warning: Failed to delete {file_path.name}: {e}")
        else:
            print(f"Error: Neuronum Cell '{self.host}' deletion failed on server.")

    async def delete_cell(self):
        if not self.host:
            print("Error: Cell host is not loaded. Cannot delete.")
            return

        url = f"https://{self.network}/api/delete_cell"

        cell_data = self.to_dict()
    
        payload = {
            "host": cell_data.get("host"),
            "signed_message": cell_data.get("signed_message"),
            "message": cell_data.get("message")
        }

        status = False
        try:
            response_data = await self._network_client.delete_request(url, payload)

            print(response_data)
            if response_data:
                status = response_data.get("status", False)
            
        except NetworkError as e:
            print(f"Error deleting cell: {e}")
            return
        except Exception as e:
            print(f"Unexpected error during API call: {e}")
            return

        if status:
            print(f"Neuronum Cell '{self.host}' successfully deleted from server. Removing local files...")

            neuronum_folder_path = Path.home() / ".neuronum"
            files_to_delete = [
                neuronum_folder_path / ".env",
                neuronum_folder_path / "private_key.pem",
                neuronum_folder_path / "public_key.pem",
                neuronum_folder_path / "cells.json",
                neuronum_folder_path / "nodes.json",
            ]

            for file_path in files_to_delete:
                try:
                    if file_path.exists():
                        await asyncio.to_thread(os.unlink, file_path)
                except Exception as e:
                    print(f"Warning: Failed to delete {file_path.name}: {e}")
        else:
            print(f"Error: Neuronum Cell '{self.host}' deletion failed on server.")

    def derive_keys_from_mnemonic(self, mnemonic: str):
        """Derive EC-SECP256R1 keys from BIP-39 mnemonic"""
        try:
            seed = Bip39SeedGenerator(mnemonic).Generate()
            digest = hashlib.sha256(seed).digest()
            int_key = int.from_bytes(digest, "big")
            
            private_key = ec.derive_private_key(int_key, ec.SECP256R1(), default_backend())
            public_key = private_key.public_key()

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
            return None, None, None, None

    async def add_employee(self, employee_name):
        employee_mnemonic = Bip39MnemonicGenerator().FromWordsNumber(12)
        _, _, _, employee_pem_public = self.derive_keys_from_mnemonic(employee_mnemonic)
        
        if not employee_pem_public:
            return

        employee_public_key = employee_pem_public.decode("utf-8")

        url = f"https://{self.network}/api/create_employee_cell"
        cell_data = self.to_dict()

        payload = {
            "host": cell_data.get("host"),
            "signed_message": cell_data.get("signed_message"),
            "message": cell_data.get("message"),
            "employee_public_key": employee_public_key,
            "employee_name": employee_name
        }

        try:
            response_data = await self._network_client.post_request(url, payload)

            print(response_data)
            if response_data:
                employee_cell = response_data.get("host", False)
                return employee_mnemonic, employee_cell 
            
        except NetworkError as e:
            print(f"Error adding employee: {e}")
            return
        except Exception as e:
            print(f"Unexpected error during API call: {e}")
            return
        
    def base64url_encode(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

    def create_dns_challenge_value(self, public_key_pem: bytes) -> str:
        try:
            key_hash = hashlib.sha256(public_key_pem).digest()
            challenge_value = self.base64url_encode(key_hash)
            return challenge_value
        except Exception as e:
            print(f"Error: Error creating DNS challenge value: {e}")
            return ""
        
    async def confirm_business(self):
        business_mnemonic = Bip39MnemonicGenerator().FromWordsNumber(12)
        _, _, _, business_pem_public = self.derive_keys_from_mnemonic(business_mnemonic)
        
        if not business_pem_public:
            return

        business_public_key = business_pem_public.decode("utf-8")
        challenge_value = self.create_dns_challenge_value(business_pem_public)

        if not challenge_value:
            return

        return business_mnemonic, challenge_value, business_public_key
    
    async def validate_cell(self, business_mnemonic, business_name, business_domain, challenge_value):
        url = f"https://{self.network}/api/create_business_cell"

        _, _, _, business_pem_public = self.derive_keys_from_mnemonic(business_mnemonic)

        business_public_key = business_pem_public.decode("utf-8")

        payload = {
            "public_key": business_public_key,
            "domain": business_domain,
            "challenge_value": challenge_value,
            "company_name": business_name
        }

        try:
            response_data = await self._network_client.post_request(url, payload)

            print(response_data)
            if response_data:
                if response_data.get("status") == "verified" and response_data.get("host"):
                    return "success"
                else:
                    return "failed"
            else:
                return "failed"
            
        except NetworkError as e:
            print(f"Error validating cell: {e}")
            return "failed"
        except Exception as e:
            print(f"Unexpected error during API call: {e}")
            return "failed"


class Cell(BaseClient):
    """Cell client implementation"""
    
    def __init__(self, config: Optional[ClientConfig] = None):
        super().__init__(config)
        self.env = self._load_env()
        private_key = self._load_private_key()
        self._init_crypto(private_key)
        
        self.host = self.env.get("HOST", "")
        self.cell_type = self.env.get("TYPE", "")
        if not self.host or self.cell_type:
            logger.warning("HOST not set in environment")
    
    def _load_private_key(self) -> Optional[ec.EllipticCurvePrivateKey]:
        """Load private key from credentials folder"""
        credentials_path = self.config.credentials_path
        credentials_path.mkdir(parents=True, exist_ok=True)
        
        key_path = credentials_path / "private_key.pem"
        
        try:
            with open(key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(), 
                    password=None, 
                    backend=default_backend()
                )
            
            stat = os.stat(key_path)
            if stat.st_mode & 0o177:
                logger.warning(
                    f"Private key file has insecure permissions: {oct(stat.st_mode)}. "
                    f"Automatically fixing permissions to 0600 for security."
                )
                try:
                    os.chmod(key_path, 0o600)
                    logger.info(f"Successfully set permissions to 0600 on {key_path}")
                except Exception as chmod_error:
                    logger.error(
                        f"Failed to fix permissions automatically: {chmod_error}. "
                        f"Please manually run: chmod 600 {key_path}"
                    )
                    raise PermissionError(
                        f"Cannot fix insecure permissions on private key. "
                        f"Please run: chmod 600 {key_path}"
                    )

            logger.info("Private key loaded successfully")
            return private_key
        except FileNotFoundError:
            logger.error(f"Private key not found at {key_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading private key: {e}")
            return None
    
    def _load_env(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_path = self.config.credentials_path / ".env"
        env_data = {}
        
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_data[key.strip()] = value.strip()
            logger.info("Environment loaded successfully")
            return env_data
        except FileNotFoundError:
            logger.error(f"Environment file not found at {env_path}")
            return {}
        except Exception as e:
            logger.error(f"Error loading environment: {e}")
            return {}
    
    async def close(self):
        """Close network client session"""
        await self._network_client.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.close()

