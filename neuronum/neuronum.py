import aiohttp
from typing import Optional, AsyncGenerator
import ssl
import websockets
import json
import asyncio

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
    

    async def stream(self, label: str, data: dict, stx: Optional[str] = None, retry_delay: int = 3):
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        while True:
            try:
                reader, writer = await asyncio.open_connection(self.network, 55555, ssl=context, server_hostname=self.network)

                credentials = f"{self.host}\n{self.password}\n{self.synapse}\n{stx}\n"
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
                    "data": data,
                }

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


    async def sync(self, stx: Optional[str] = None) -> AsyncGenerator[str, None]:
        full_url = f"wss://{self.network}/sync/{stx}"
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
                            yield operation

                        except asyncio.TimeoutError:
                            print("No data received. Continuing...")
                        except websockets.exceptions.ConnectionClosedError as e:
                            print(f"Connection closed with error: {e}. Reconnecting...")
                            break
                        except Exception as e:
                            print(f"Unexpected error in recv loop: {e}")
                            break

            except websockets.exceptions.WebSocketException as e:
                print(f"WebSocket error occurred: {e}. Retrying in 5 seconds...")
            except Exception as e:
                print(f"General error occurred: {e}. Retrying in 5 seconds...")

            await asyncio.sleep(3)
           

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
                    data = await response.json()
                    if data.get("success") == True:
                                if "json" in data.get("response"):
                                    return data.get("response").get("json")
                                elif "html" in data.get("response"):
                                    return "Info: HTML response available. Please activate TX in browser."
                                else:
                                    return "Info: Response received but contains no usable content."
                    else:
                        print(data["success"], data["message"])

            except aiohttp.ClientError as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


    async def tx_response(self, txID: str, client: str, data: dict):
        url = f"https://{self.network}/api/tx_response/{txID}"

        tx_response = {
            "client": client,
            "data": data,
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


    async def notify(self, receiver: str, title: str, message: str):
        full_url = f"https://{self.network}/api/notify"

        notify_payload = {
            "receiver": receiver,
            "notification": {
                "title": title,
                "message": message
            },
            "cell": self.to_dict()
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(full_url, json=notify_payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Notification sent successfully: {data}")
                    return data

            except aiohttp.ClientError as e:
                print(f"HTTP error while sending notification: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")


__all__ = ['Cell']
