import aiohttp
from typing import AsyncGenerator
import websockets
import json
import asyncio
import base64
import os
from pathlib import Path
from websockets.exceptions import ConnectionClosed
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend


class Cell:
    def __init__(self, private_key_path: str, public_key_path: str):
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path
        self.queue = asyncio.Queue()
        self.host = self._load_host()
        self.network = self._load_network()
        self.synapse = self._load_synapse()
        self.password = self._load_password()
        self._private_key = self._load_private_key()
        self._public_key = self._load_public_key()


    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse
        }

    def _load_private_key(self):
        try:
            with open(self.private_key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
                print("Private key loaded successfully.")
                return private_key
        except FileNotFoundError:
            print(f"Private key file not found at {self.private_key_path}.")
            return None
        
    def _load_host(self):
        credentials_folder_path = Path.home() / ".neuronum"
        env_path = credentials_folder_path / ".env"

        env_data = {}  

        try:
            with open(env_path, "r") as f:
                for line in f:
                    key, value = line.strip().split("=")
                    env_data[key] = value

            host = env_data.get("HOST", "")
            return host
        except FileNotFoundError:
            print(f"Cell Host not found")
            return None
        

    def _load_password(self):
        credentials_folder_path = Path.home() / ".neuronum"
        env_path = credentials_folder_path / ".env"

        env_data = {}  

        try:
            with open(env_path, "r") as f:
                for line in f:
                    key, value = line.strip().split("=")
                    env_data[key] = value

            host = env_data.get("PASSWORD", "")
            return host
        except FileNotFoundError:
            print(f"Cell Password not found")
            return None
        
    def _load_synapse(self):
        credentials_folder_path = Path.home() / ".neuronum"
        env_path = credentials_folder_path / ".env"

        env_data = {}  

        try:
            with open(env_path, "r") as f:
                for line in f:
                    key, value = line.strip().split("=")
                    env_data[key] = value

            host = env_data.get("SYNAPSE", "")
            return host
        except FileNotFoundError:
            print(f"Cell Synapse not found")
            return None
        
    def _load_network(self):
        credentials_folder_path = Path.home() / ".neuronum"
        env_path = credentials_folder_path / ".env"

        env_data = {}  

        try:
            with open(env_path, "r") as f:
                for line in f:
                    key, value = line.strip().split("=")
                    env_data[key] = value

            host = env_data.get("NETWORK", "")
            return host
        except FileNotFoundError:
            print(f"Cell Network not found")
            return None


    def _load_public_key(self):
        try:
            with open(self.public_key_path, "rb") as f:
                public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend()
                )
                print("Public key loaded successfully.")
                print(public_key)
                return public_key
        except FileNotFoundError:
            print(f"Public key file not found at {self.public_key_path}. Deriving from private key.")
            if self._private_key:
                return self._private_key.public_key()
            else:
                return None


    def get_public_key_jwk(self):
        public_key = self._load_public_key()
        if not public_key:
            print("Public key not loaded. Cannot generate JWK.")
            return None
        
        print("Public key loaded successfully.")
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
            print(f"Decryption failed: {e}")
            return None


    async def sync(self, node_id: str) -> AsyncGenerator[str, None]:
        full_url = f"wss://{self.network}/sync/{node_id}"
        auth_payload = {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse,
        }
        while True:
            try:
                async with websockets.connect(full_url) as ws:
                    await ws.send(json.dumps(auth_payload))
                    print("Connected to WebSocket.")
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


    async def list_nodes(self):
        full_url = f"https://{self.network}/api/list_nodes"
        list_nodes_payload = {
            "cell": self.to_dict()
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=list_nodes_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Nodes", [])
            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def activate_tx(self, node_id: str, data: dict):
        url = f"https://{self.network}/api/activate_tx/{node_id}"
        
        nodes = await self.list_nodes()

        target_public_key_pem = None
        target_node = node_id

        for node in nodes:
            node_ids = node.get('config', {}).get('data_gateways', [])
            for node_id_entry in node_ids:
                if node_id_entry.get('node_id') == target_node:
                    target_public_key_pem = node.get('config', {}).get('public_key')
                    break
            if target_public_key_pem:
                break

        if not target_public_key_pem:
            print(f"Target node not found or public key is missing.")
            return None

        try:
            print(target_public_key_pem)
            partner_public_key_jwk = self._load_public_key_from_pem(target_public_key_pem)
            if not partner_public_key_jwk:
                print("Failed to convert public key to JWK format. Aborting.")
                return None
            
            partner_public_key = self._load_public_key_from_jwk(partner_public_key_jwk)
            if not partner_public_key:
                print("Failed to load partner's public key. Aborting.")
                return None

            data_to_encrypt = data.copy()
            data_to_encrypt["publicKey"] = self.get_public_key_jwk()

            encrypted_payload = self._encrypt_with_ecdh_aesgcm(partner_public_key, data_to_encrypt)

            TX = {
                "data": {
                "encrypted": encrypted_payload
                },
                "cell": self.to_dict()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=TX) as response:
                    if response.status == 504:
                        print(f"Gateway Timeout: No response from transmitter for txID: {node_id}")
                        return None
                    
                    response.raise_for_status()
                    
                    response_data = await response.json()
                    
                    if "response" in response_data:
                        inner_response = response_data["response"]
                        
                        if "ciphertext" in inner_response:
                            ephemeral_public_key_b64 = inner_response["ephemeralPublicKey"]
                            ephemeral_public_key_b64 += '=' * ((4 - len(ephemeral_public_key_b64) % 4) % 4)
                            ephemeral_public_key_bytes = base64.urlsafe_b64decode(ephemeral_public_key_b64)

                            nonce_b64 = inner_response["nonce"]
                            nonce_b64 += '=' * ((4 - len(nonce_b64) % 4) % 4)
                            nonce = base64.urlsafe_b64decode(nonce_b64)
                            
                            ciphertext_b64 = inner_response["ciphertext"]
                            ciphertext_b64 += '=' * ((4 - len(ciphertext_b64) % 4) % 4)
                            ciphertext = base64.urlsafe_b64decode(ciphertext_b64)
                            
                            decrypted_response = self._decrypt_with_ecdh_aesgcm(
                                ephemeral_public_key_bytes, nonce, ciphertext
                            )
                            
                            if decrypted_response:
                                return decrypted_response
                            else:
                                print("Failed to decrypt server response.")
                                return None
                        else:
                            print("Server response was not encrypted as expected.")
                            return inner_response

                    else:
                        print("Unexpected response format.")
                        return response_data

        except aiohttp.ClientResponseError as e:
            print(f"HTTP Error: {e.status}, Message: {e.message}, URL: {e.request_info.url}")
            return None

        except aiohttp.ClientError as e:
            print(f"Connection Error: {e}")
            return None

        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
            

    def _load_public_key_from_jwk(self, jwk):
        try:
            print(jwk)
            x = base64.urlsafe_b64decode(jwk['x'] + '==')
            y = base64.urlsafe_b64decode(jwk['y'] + '==')
            public_numbers = ec.EllipticCurvePublicNumbers(
                int.from_bytes(x, 'big'),
                int.from_bytes(y, 'big'),
                ec.SECP256R1()
            )
            return public_numbers.public_key(default_backend())
        except (KeyError, ValueError, TypeError) as e:
            print(f"Error loading public key from JWK string: {e}")
            return None
        

    def _load_public_key_from_pem(self, pem_string: str):
        try:
            print(pem_string)
            corrected_pem_string = pem_string.replace("-----BEGINPUBLICKEY-----", "-----BEGIN PUBLIC KEY-----")
            corrected_pem_string = corrected_pem_string.replace("-----ENDPUBLICKEY-----", "-----END PUBLIC KEY-----")

            public_key = serialization.load_pem_public_key(
                corrected_pem_string.encode(),
                backend=default_backend()
            )

            public_numbers = public_key.public_numbers()
            x_bytes = public_numbers.x.to_bytes((public_numbers.x.bit_length() + 7) // 8, 'big')
            y_bytes = public_numbers.y.to_bytes((public_numbers.y.bit_length() + 7) // 8, 'big')
            return {
                "kty": "EC",
                "crv": "P-256",
                "x": base64.urlsafe_b64encode(x_bytes).rstrip(b'=').decode('utf-8'),
                "y": base64.urlsafe_b64encode(y_bytes).rstrip(b'=').decode('utf-8')
            }
        except Exception as e:
            print(f"Error loading public key from PEM string: {e}")
            return None


    def _encrypt_with_ecdh_aesgcm(self, public_key, plaintext_dict):
        ephemeral_private = ec.generate_private_key(ec.SECP256R1())
        ephemeral_public = ephemeral_private.public_key()
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
        ephemeral_public_bytes = ephemeral_public.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )
        return {
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'nonce': base64.b64encode(nonce).decode(),
            'ephemeralPublicKey': base64.b64encode(ephemeral_public_bytes).decode()
        }
    

    async def tx_response(self, transmitter_id: str, data: dict, client_public_key_str):
        if isinstance(client_public_key_str, str):
            try:
                client_public_key_jwk = json.loads(client_public_key_str)
            except json.JSONDecodeError:
                print("Failed to decode client public key from string. Aborting response.")
                return
        elif isinstance(client_public_key_str, dict):
            client_public_key_jwk = client_public_key_str
        else:
            print("Invalid type for client public key. Expected str or dict. Aborting response.")
            return
        public_key = self._load_public_key_from_jwk(client_public_key_jwk)
        if not public_key:
            print("Failed to load public key. Aborting response.")
            return
        encrypted_payload = self._encrypt_with_ecdh_aesgcm(public_key, data)
        url = f"https://{self.network}/api/tx_response/{transmitter_id}"
        tx_response = {
            "data": encrypted_payload,
            "cell": self.to_dict()
        }
        async with aiohttp.ClientSession() as session:
            try:
                for _ in range(2):
                    async with session.post(url, json=tx_response) as response:
                        response.raise_for_status()
                        data = await response.json()
                print(data["message"])
            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")
           
__all__ = ['Cell']