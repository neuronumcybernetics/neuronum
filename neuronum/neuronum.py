import aiohttp
from typing import Optional, AsyncGenerator, Union
import websockets
import json
import asyncio
import base64
import os
import ssl
from pathlib import Path
from websockets.exceptions import ConnectionClosed
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

class Node:
    def __init__(self, id: str, private_key: str, public_key: str):
        self.node_id = id
        self.private_key_path = private_key
        self.public_key_path = public_key
        self.queue = asyncio.Queue()
        self.env = self._load_env()
        self.host = self.env.get("HOST", "")
        self.network = self.env.get("NETWORK", "")
        self.synapse = self.env.get("SYNAPSE", "")
        self.password = self.env.get("PASSWORD", "")
        self._private_key = self._load_private_key()
        self._public_key = self._load_public_key()


    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse
        }
    

    def _load_env(self) -> dict:
        credentials_folder_path = Path.home() / ".neuronum"
        env_path = credentials_folder_path / ".env"
        env_data = {}
        try:
            with open(env_path, "r") as f:
                for line in f:
                    key, value = line.strip().split("=")
                    env_data[key] = value
            return env_data
        except FileNotFoundError:
            print(f"Cell credentials (.env) not found at {env_path}")
            return {}


    def _load_private_key(self):
        try:
            with open(self.private_key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
        except FileNotFoundError:
            print(f"Private key file not found at {self.private_key_path}.")
            return None


    def _load_public_key(self):
        try:
            with open(self.public_key_path, "rb") as f:
                return serialization.load_pem_public_key(f.read(), backend=default_backend())
        except FileNotFoundError:
            print(f"Public key file not found. Deriving from private key.")
            return self._private_key.public_key() if self._private_key else None


    def get_public_key_jwk(self):
        public_key = self._load_public_key()
        if not public_key:
            print("Public key not loaded. Cannot generate JWK.")
            return None
        public_numbers = public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes((public_numbers.x.bit_length() + 7) // 8, 'big')
        y_bytes = public_numbers.y.to_bytes((public_numbers.y.bit_length() + 7) // 8, 'big')
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": base64.urlsafe_b64encode(x_bytes).rstrip(b'=').decode('utf-8'),
            "y": base64.urlsafe_b64encode(y_bytes).rstrip(b'=').decode('utf-8')
        }


    def _decrypt_with_ecdh_aesgcm(self, ephemeral_public_key_bytes, nonce, ciphertext):
        try:
            ephemeral_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), ephemeral_public_key_bytes
            )
            shared_secret = self._private_key.exchange(ec.ECDH(), ephemeral_public_key)
            derived_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'handshake data').derive(shared_secret)
            aesgcm = AESGCM(derived_key)
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext_bytes.decode())
        except Exception as e:
            print(f"Decryption failed: {e}")
            return None


    def _encrypt_with_ecdh_aesgcm(self, public_key, plaintext_dict):
        ephemeral_private = ec.generate_private_key(ec.SECP256R1())
        shared_secret = ephemeral_private.exchange(ec.ECDH(), public_key)
        derived_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'handshake data').derive(shared_secret)
        aesgcm = AESGCM(derived_key)
        nonce = os.urandom(12)
        plaintext_bytes = json.dumps(plaintext_dict).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        ephemeral_public_bytes = ephemeral_private.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        return {
            'ciphertext': base64.urlsafe_b64encode(ciphertext).rstrip(b'=').decode(),
            'nonce': base64.urlsafe_b64encode(nonce).rstrip(b'=').decode(),
            'ephemeralPublicKey': base64.urlsafe_b64encode(ephemeral_public_bytes).rstrip(b'=').decode()
        }


    def _load_public_key_from_jwk(self, jwk):
        try:
            x_bytes = base64.urlsafe_b64decode(jwk['x'] + '==')
            y_bytes = base64.urlsafe_b64decode(jwk['y'] + '==')
            public_numbers = ec.EllipticCurvePublicNumbers(
                int.from_bytes(x_bytes, 'big'),
                int.from_bytes(y_bytes, 'big'),
                ec.SECP256R1()
            )
            return public_numbers.public_key(default_backend())
        except Exception as e:
            print(f"Error loading public key from JWK: {e}")
            return None


    def _load_public_key_from_pem(self, pem_string: str):
        try:
            corrected_pem = pem_string.replace("-----BEGINPUBLICKEY-----", "-----BEGIN PUBLIC KEY-----") \
                                      .replace("-----ENDPUBLICKEY-----", "-----END PUBLIC KEY-----")
            public_key = serialization.load_pem_public_key(corrected_pem.encode(), backend=default_backend())
            return public_key
        except Exception as e:
            print(f"Error loading public key from PEM: {e}")
            return None


    async def _get_target_node_public_key(self, node_id: str):
        nodes = await self.list_nodes()
        for node in nodes:
            app_metadata = node.get('config', {}).get('app_metadata', {})
            if app_metadata.get('node_id') == node_id:
                pem = node.get('config', {}).get('public_key')
                if not pem:
                    print(f"Public key missing for node: {node_id}")
                    return None
                public_key = self._load_public_key_from_pem(pem)
                if not public_key:
                    return None
                return public_key
        print(f"Target node not found: {node_id}")
        return None


    async def _post_request(self, url, payload):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                print(f"HTTP Error: {e.status}, URL: {url}")
            except Exception as e:
                print(f"Unexpected error: {e}")
        return None


    async def list_nodes(self):
        full_url = f"https://{self.network}/api/list_nodes"
        payload = {"cell": self.to_dict()}
        data = await self._post_request(full_url, payload)
        return data.get("Nodes", []) if data else []


    async def tx_response(self, transmitter_id: str, data: dict, client_public_key_str: Optional[Union[str, dict]] = None, encrypted: Optional[bool] = True):
        url = f"https://{self.network}/api/tx_response/{transmitter_id}"
        
        if encrypted:
            if not client_public_key_str:
                print("Error: client_public_key_str is required for encrypted responses.")
                return

            public_key_jwk = json.loads(client_public_key_str) if isinstance(client_public_key_str, str) else client_public_key_str
            public_key = self._load_public_key_from_jwk(public_key_jwk)
            if not public_key:
                return

            encrypted_payload = self._encrypt_with_ecdh_aesgcm(public_key, data)
            payload = {"data": encrypted_payload, "cell": self.to_dict()}
        else:
            payload = {"data": data, "cell": self.to_dict()}
        
        await self._post_request(url, payload)


    async def activate_tx(self, node_id: str, data: dict, encrypted: Optional[bool] = True):
        url = f"https://{self.network}/api/activate_tx/{node_id}"
        payload = {"cell": self.to_dict()}
        
        if encrypted:
            public_key = await self._get_target_node_public_key(node_id)
            if not public_key: return None
            data_to_encrypt = data.copy()
            data_to_encrypt["publicKey"] = self.get_public_key_jwk()
            encrypted_payload = self._encrypt_with_ecdh_aesgcm(public_key, data_to_encrypt)
            payload["data"] = {"encrypted": encrypted_payload}
        else:
            payload["data"] = data

        response_data = await self._post_request(url, payload)
        
        if encrypted:
            if not response_data or "response" not in response_data:
                print("Unexpected or missing response.")
                return response_data
            inner_response = response_data["response"]
            if "ciphertext" in inner_response:
                ephemeral_public_key_bytes = base64.urlsafe_b64decode(inner_response["ephemeralPublicKey"] + '==')
                nonce = base64.urlsafe_b64decode(inner_response["nonce"] + '==')
                ciphertext = base64.urlsafe_b64decode(inner_response["ciphertext"] + '==')
                return self._decrypt_with_ecdh_aesgcm(ephemeral_public_key_bytes, nonce, ciphertext)
            else:
                print("Server response was not encrypted as expected.")
                return inner_response
        else:
            return response_data


    async def sync(self) -> AsyncGenerator[str, None]:
        full_url = f"wss://{self.network}/sync/{self.node_id}"
        auth_payload = {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse,
        }
        while True:
            try:
                async with websockets.connect(full_url) as ws:
                    await ws.send(json.dumps(auth_payload))
                    print("Node syncing...")
                    while True:
                        try:
                            raw_operation = await ws.recv()
                            operation = json.loads(raw_operation)
                            
                            if "encrypted" in operation.get("data", {}):
                                encrypted_data = operation["data"]["encrypted"]
                                
                                ephemeral_public_key_b64 = encrypted_data["ephemeralPublicKey"]
                                ephemeral_public_key_b64 += '=' * ((4 - len(ephemeral_public_key_b64) % 4) % 4)
                                ephemeral_public_key_bytes = base64.urlsafe_b64decode(ephemeral_public_key_b64)

                                nonce_b64 = encrypted_data["nonce"]
                                nonce_b64 += '=' * ((4 - len(nonce_b64) % 4) % 4)
                                nonce = base64.urlsafe_b64decode(nonce_b64)
                                
                                ciphertext_b64 = encrypted_data["ciphertext"]
                                ciphertext_b64 += '=' * ((4 - len(ciphertext_b64) % 4) % 4)
                                ciphertext = base64.urlsafe_b64decode(ciphertext_b64)
                                
                                decrypted_data = self._decrypt_with_ecdh_aesgcm(
                                    ephemeral_public_key_bytes, nonce, ciphertext
                                )
                                
                                if decrypted_data:
                                    operation["data"].update(decrypted_data)
                                    operation["data"].pop("encrypted")
                                    yield operation
                                else:
                                    print("Failed to decrypt incoming data. Skipping...")
                            else:
                                yield operation
                        except asyncio.TimeoutError:
                            print("No data received. Continuing...")
                        except ConnectionClosed as e:
                            if e.code == 1000:
                                print(f"WebSocket closed cleanly (code 1000). Reconnecting...")
                            else:
                                print(f"Connection closed with error code {e.code}: {e.reason}. Reconnecting...")
                            break
                        except Exception as e:
                            print(f"Unexpected error in recv loop: {e}")
                            break
            except websockets.exceptions.WebSocketException as e:
                print(f"WebSocket error occurred: {e}. Retrying in 5 seconds...")
            except Exception as e:
                print(f"General error occurred: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(3)


    async def stream(self, label: str, data: dict, node_id: str = None, encrypted: Optional[bool] = True, retry_delay: int = 3):
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        target_node_public_key = None
        if encrypted:
            target_node_public_key = await self._get_target_node_public_key(node_id)
            if not target_node_public_key:
                print("Failed to get target node's public key. Cannot stream data.")
                return

        while True:
            try:
                reader, writer = await asyncio.open_connection(self.network, 55555, ssl=context, server_hostname=self.network)

                credentials = f"{self.host}\n{self.password}\n{self.synapse}\n{node_id}\n"
                writer.write(credentials.encode("utf-8"))
                await writer.drain()

                response = await reader.read(1024)
                response_text = response.decode("utf-8").strip()

                if "Authentication successful" not in response_text:
                    print("Authentication failed, retrying...")
                    writer.close()
                    await writer.wait_closed()
                    await asyncio.sleep(retry_delay)
                    continue
                
                stream_payload = {
                    "label": label,
                    "data": data.copy()
                }
                
                if encrypted:
                    data_to_encrypt = data.copy()
                    data_to_encrypt["publicKey"] = self.get_public_key_jwk()
                    
                    encrypted_payload = self._encrypt_with_ecdh_aesgcm(target_node_public_key, data_to_encrypt)
                    stream_payload["data"] = {"encrypted": encrypted_payload}

                writer.write(json.dumps(stream_payload).encode("utf-8"))
                await writer.drain()

                response = await reader.read(1024)
                response_text = response.decode("utf-8").strip()

                if response_text == "Sent":
                    print(f"Success: {response_text} - {stream_payload}")
                    break
                else:
                    print(f"Error sending: {stream_payload}")

            except (ssl.SSLError, ConnectionError) as e:
                print(f"Connection error: {e}, retrying...")
                await asyncio.sleep(retry_delay)
            except Exception as e:
                print(f"Unexpected error: {e}, retrying...")
                await asyncio.sleep(retry_delay)
            finally:
                if 'writer' in locals():
                    writer.close()
                    await writer.wait_closed()