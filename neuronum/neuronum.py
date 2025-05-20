import requests
import socket
from typing import Optional, Generator
import ssl
from websocket import create_connection
import json

class Cell:
    def __init__(self, host: str, password: str, network: str, synapse: str):
        self.host = host
        self.password = password
        self.network = network
        self.synapse = synapse
        self.sock = None

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse
        }

    def __repr__(self) -> str:
        return f"Cell(host={self.host}, password={self.password}, network={self.network}, synapse={self.synapse})"
    
    
    def authenticate(self, stx: Optional[str] = None):
        credentials = f"{self.host}\n{self.password}\n{self.synapse}\n{stx}\n"
        self.sock.sendall(credentials.encode('utf-8'))

        response = self.sock.recv(1024).decode('utf-8')
        return "Authentication successful" in response
    

    def create_tx(self, descr: str, key_values: dict, ctx: str, label: str, partners: list):
        url = f"https://{self.network}/api/create_tx"

        TX = {
            "descr": descr,
            "key_values": key_values,
            "ctx": ctx,
            "label": label,
            "partners": partners,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=TX,
            )

            response.raise_for_status()

            return response.json()["txID"]

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def delete_tx(self, txID: str):
        url = f"https://{self.network}/api/delete_tx"

        TX = {
            "txID": txID,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=TX,
            )

            response.raise_for_status()

            print(f"Response from Neuronum: {response.json()}")

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
    

    def activate_tx(self, txID: str, data: dict):
        url = f"https://{self.network}/api/activate_tx/{txID}"

        TX = {
            "data": data,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=TX,
            )

            response.raise_for_status()

            print(f"Response from Neuronum: {response.json()}")

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def create_ctx(self, descr: str, partners: list):
        url = f"https://{self.network}/api/create_ctx"

        CTX = {
            "descr": descr,
            "partners": partners,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=CTX,
            )

            response.raise_for_status()

            return response.json()["ctxID"]

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def delete_ctx(self, ctxID: str):
        url = f"https://{self.network}/api/delete_ctx"

        CTX = {
            "ctxID": ctxID,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=CTX,
            )

            response.raise_for_status()

            print(f"Response from Neuronum: {response.json()}")

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def create_stx(self, descr: str, partners: list):
        url = f"https://{self.network}/api/create_stx"

        STX = {
            "descr": descr,
            "partners": partners,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=STX,
            )

            response.raise_for_status()["stxID"]

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def delete_stx(self, stxID: str):
        url = f"https://{self.network}/api/delete_stx"

        STX = {
            "stxID": stxID,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=STX,
            )

            response.raise_for_status()

            print(f"Response from Neuronum: {response.json()}")

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def register_node(self, descr: str, mode: str, stx: str):
        if mode == "public":
            url = f"https://{self.network}/api/register_node/public"
        elif mode == "private":
            url = f"https://{self.network}/api/register_node/private"
        else:
            return {"error": "Invalid mode", "message": "Mode has to be 'public' or 'private'"}

        node_data = {
            "descr": descr,
            "mode": mode,
            "stream": stx,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=node_data,
            )

            response.raise_for_status()

            return response.json()["nodeID"]

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def delete_node(self, nodeID: str):
        url = f"https://{self.network}/api/delete_node"

        delete_node = {
            "nodeID": nodeID,
            "cell": self.to_dict()
        }

        try:
            response = requests.post(
                url,
                json=delete_node,
            )

            response.raise_for_status()
            print(response.json())

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def list_tx(self, cellID: str):
        full_url = f"https://{self.network}/api/list_tx"
        
        list_tx = {
            "cell": self.to_dict(),  
            "cellID": cellID
        }

        try:
            response = requests.post(full_url, json=list_tx)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def list_ctx(self, cellID: str):
        full_url = f"https://{self.network}/api/list_ctx"
        
        list_ctx = {
            "cell": self.to_dict(),  
            "cellID": cellID
        }

        try:
            response = requests.post(full_url, json=list_ctx)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def list_stx(self, cellID: str):
        full_url = f"https://{self.network}/api/list_stx"
        
        list_stx = {
            "cell": self.to_dict(),  
            "cellID": cellID
        }

        try:
            response = requests.post(full_url, json=list_stx)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def connect(self):
            url = f"https://{self.network}/api/connect"

            test = {
                "cell": self.to_dict() 
            }

            try:
                response = requests.post(url, json=test)
                response.raise_for_status()
                print(response.json()["connection"]) 
            except requests.exceptions.RequestException as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

        
    def store(self, label: str, data: dict, ctx: Optional[str] = None):
        if ctx:
            full_url = f"https://{self.network}/api/store_in_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/api/store"
        
        store = {
            "label": label,
            "data": data,
            "cell": self.to_dict()  
        }

        try:
            response = requests.post(full_url, json=store)
            response.raise_for_status()
            print(f"Response from Neuronum: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def load(self, label: str, ctx: Optional[str] = None):
        if ctx:
            full_url = f"https://{self.network}/api/load_from_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/api/load"

        load = {
            "label": label,
            "cell": self.to_dict() 
        }

        try:
            response = requests.post(full_url, json=load)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def delete(self, label: str, ctx: Optional[str] = None):
        if ctx:
            full_url = f"https://{self.network}/api/delete_from_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/api/delete"

        delete = {
            "label": label,
            "cell": self.to_dict() 
        }

        try:
            response = requests.post(full_url, json=delete)
            response.raise_for_status()
            print(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def clear(self, ctx: Optional[str] = None):
        if ctx:
            full_url = f"https://{self.network}/api/clear_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/api/clear"

        clear = {
            "cell": self.to_dict() 
        }

        try:
            response = requests.post(full_url, json=clear)
            response.raise_for_status()
            print(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def stream(self, label: str, data: dict, stx: Optional[str] = None):
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock = context.wrap_socket(raw_sock, server_hostname=self.network)

        try:
            print(f"Connecting to {self.network}")
            self.sock.connect((self.network, 55555))

            if not self.authenticate(stx):
                print("Authentication failed. Cannot stream.")
                return

            stream = {
                "label": label,
                "data": data,
            }

            self.sock.sendall(json.dumps(stream).encode('utf-8'))
            print(f"Sent: {stream}")

        except ssl.SSLError as e:
            print(f"SSL error occurred: {e}")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        finally:
            self.sock.close()


    def sync(self, stx: Optional[str] = None) -> Generator[str, None, None]:
        auth = {
            "host": self.host,
            "password": self.password,
            "synapse": self.synapse,
        }

        try:
            ws = create_connection(f"wss://{self.network}/sync/{stx}")
            ws.send(json.dumps(auth))
            print("Stream connection set...")

            try:
                while True:
                    try:
                        raw_operation = ws.recv()
                        operation = json.loads(raw_operation)
                        print("Listening to Stream...")
                        yield operation

                    except socket.timeout:
                        print("No initial data received. Continuing to listen...") 
                        continue 

            except KeyboardInterrupt:
                print("Stream-Synchronization ended!")
            except Exception as e:
                print(f"Error: {e}")
            finally:
                ws.close()
                print("Connection closed.")

        except KeyboardInterrupt:
            print("Stream-Synchronization ended!")
            ws.close()
            print("Connection closed. Goodbye!")


__all__ = ['Cell']
