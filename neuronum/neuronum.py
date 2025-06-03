import aiohttp
from typing import Optional, AsyncGenerator
import ssl
import websockets
import json
import asyncio
from bleak import BleakScanner

class Cell:
    def __init__(self, host: str, password: str, network: str, synapse: str):
        self.host = host
        self.password = password
        self.network = network
        self.synapse = synapse
        self.queue = asyncio.Queue()

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse
        }

    def __repr__(self) -> str:
        return f"Cell(host={self.host}, password={self.password}, network={self.network}, synapse={self.synapse})"
           

    async def create_tx(self, descr: str, key_values: dict, stx: str, label: str, partners: list):
        url = f"https://{self.network}/api/create_tx"

        TX = {
            "descr": descr,
            "key_values": key_values,
            "stx": stx,
            "label": label,
            "partners": partners,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=TX) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["txID"]

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def delete_tx(self, txID: str):
        url = f"https://{self.network}/api/delete_tx"

        TX = {
            "txID": txID,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=TX) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")
    

    async def activate_tx(self, txID: str, data: dict):
        url = f"https://{self.network}/api/activate_tx/{txID}"

        TX = {
            "data": data,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=TX) as response:
                    response.raise_for_status()
                    response.raise_for_status()
                    data = await response.json()
                    print(data["message"])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def create_ctx(self, descr: str, partners: list):
        url = f"https://{self.network}/api/create_ctx"

        CTX = {
            "descr": descr,
            "partners": partners,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=CTX) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["ctxID"]

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def delete_ctx(self, ctxID: str):
        url = f"https://{self.network}/api/delete_ctx"

        CTX = {
            "ctxID": ctxID,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=CTX) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def create_stx(self, descr: str, partners: list):
        url = f"https://{self.network}/api/create_stx"

        STX = {
            "descr": descr,
            "partners": partners,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=STX) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["stxID"]

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def delete_stx(self, stxID: str):
        url = f"https://{self.network}/api/delete_stx"

        STX = {
            "stxID": stxID,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=STX) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def list_cells(self):
        full_url = f"https://{self.network}/api/list_cells"

        list_cells_payload = {
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url, json=list_cells_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Cells", [])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def list_tx(self):
        full_url = f"https://{self.network}/api/list_tx"

        list_tx_payload = {
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url, json=list_tx_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Transmitters", [])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def list_ctx(self):
        full_url = f"https://{self.network}/api/list_ctx"

        list_ctx_payload = {
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url, json=list_ctx_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Circuits", [])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def list_stx(self):
        full_url = f"https://{self.network}/api/list_stx"

        list_stx_payload = {
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url, json=list_stx_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Streams", [])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def list_nodes(self):
        full_url = f"https://{self.network}/api/list_nodes"

        list_nodes_payload = {
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url, json=list_nodes_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Nodes", [])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

        
    async def store(self, label: str, data: dict, ctx: Optional[str] = None):
        full_url = f"https://{self.network}/api/store_in_ctx/{ctx}" if ctx else f"https://{self.network}/api/store"

        store_payload = {
            "label": label,
            "data": data,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=store_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def load(self, label: str, ctx: Optional[str] = None):
        full_url = f"https://{self.network}/api/load_from_ctx/{ctx}" if ctx else f"https://{self.network}/api/load"

        load_payload = {
            "label": label,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=load_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def delete(self, label: str, ctx: Optional[str] = None):
        full_url = f"https://{self.network}/api/delete_from_ctx/{ctx}" if ctx else f"https://{self.network}/api/delete"

        delete_payload = {
            "label": label,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=delete_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def clear(self, ctx: Optional[str] = None):
        full_url = f"https://{self.network}/api/clear_ctx/{ctx}" if ctx else f"https://{self.network}/api/clear"

        clear_payload = {
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=clear_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def stream(self, label: str, data: dict, stx: Optional[str] = None):
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        try:
            reader, writer = await asyncio.open_connection(self.network, 55555, ssl=context, server_hostname=self.network)

            credentials = f"{self.host}\n{self.password}\n{self.synapse}\n{stx}\n"
            writer.write(credentials.encode("utf-8"))
            await writer.drain()

            response = await reader.read(1024)
            response_text = response.decode("utf-8")

            if "Authentication successful" not in response_text:
                print("Authentication failed")
                writer.close()
                await writer.wait_closed()
                return

            stream_payload = {
                "label": label,
                "data": data,
            }

            writer.write(json.dumps(stream_payload).encode("utf-8"))
            await writer.drain()
            print(f"Sent: {stream_payload}")

        except ssl.SSLError as e:
            print(f"SSL error occurred: {e}")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        finally:
            writer.close()
            await writer.wait_closed()



    async def sync(self, stx: Optional[str] = None) -> AsyncGenerator[str, None]:
        full_url = f"wss://{self.network}/sync/{stx}"
        
        auth_payload = {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse,
        }

        try:
            async with websockets.connect(full_url) as ws:
                await ws.send(json.dumps(auth_payload))
                print("Listening to Stream...")

                try:
                    while True:
                        try:
                            raw_operation = await ws.recv()
                            operation = json.loads(raw_operation)
                            yield operation

                        except asyncio.TimeoutError:
                            print("No initial data received. Continuing to listen...")
                            continue

                except asyncio.CancelledError:
                    print("Connection closed.")

        except websockets.exceptions.WebSocketException as e:
            print(f"WebSocket error occurred: {e}")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")


    async def sign_contract(self, contractID: str):
        full_url = f"https://{self.network}/api/sign_contract"

        sign_contract_payload = {
            "contractID": contractID,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=sign_contract_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("token")

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def validate_token(self, token: str, cp: str, contractID: str):
        full_url = f"https://{self.network}/api/validate_token"

        validate_payload = {
            "token": token,
            "cp": cp,
            "contractID": contractID,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=validate_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("validity")

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def request_token(self, cp: str, contractID: str):
        full_url = f"https://{self.network}/api/request_token"

        request_token_payload = {
            "cp": cp,
            "contractID": contractID,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=request_token_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

    
    async def present_token(self, token: str, cp: str, contractID: str):
        full_url = f"https://{self.network}/api/present_token"

        present_token_payload = {
            "token": token,
            "cp": cp,
            "contractID": contractID,
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=present_token_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def create_contract(self, descr: str, details: dict, partners: list):
        full_url = f"https://{self.network}/api/create_contract"

        create_contract_payload = {
            "cell": self.to_dict(),
            "descr": descr,
            "details": details,
            "partners": partners
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=create_contract_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("contractID")

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def delete_contract(self, contractID: str):
        full_url = f"https://{self.network}/api/delete_contract"

        request_payload = {
            "cell": self.to_dict(),
            "contractID": contractID
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=request_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response from Neuronum: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def list_contracts(self):
        full_url = f"https://{self.network}/api/list_contracts"

        list_contracts_payload = {
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url, json=list_contracts_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Contracts", [])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

        
    def device_found(self, device, advertisement_data):
        if device.name and (device.name.endswith("::cell") or device.name.endswith("::node")):
            asyncio.create_task(self.queue.put(f"{device.name} - {device.address}"))

    async def scan(self):
        print("Scanning for Neuronum Cells & Nodes")

        scanner = BleakScanner(self.device_found)
        await scanner.start()

        try:
            while True:
                yield await self.queue.get()
        except asyncio.CancelledError:
            await scanner.stop()


__all__ = ['Cell']
