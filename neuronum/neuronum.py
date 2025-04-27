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
        print(response)
        return "Authentication successful" in response
    

    def activate(self, txID: str, data: dict):
        url = f"https://{self.network}/activateTX/{txID}"

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



    def register(self, node: str, mode: str, stx: str):
        if mode == "public":
            url = f"https://{self.network}/register/node/public"
        elif mode == "private":
            url = f"https://{self.network}/register/node/private"
        else:
            return {"error": "Invalid mode", "message": "Mode has to be 'public' or 'private'"}

        node_data = {
            "name": node,
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

            print(f"Response from Neuronum: {response.json()}")

        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")



    def test_connection(self):
            url = f"https://{self.network}/testConnection"

            test = {
                "cell": self.to_dict() 
            }

            try:
                response = requests.post(url, json=test)
                response.raise_for_status()
                print(response.json())
            except requests.exceptions.RequestException as e:
                print(f"Error sending request: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

        
    def store(self, label: str, data: dict, ctx: Optional[str] = None):
        if ctx:
            full_url = f"https://{self.network}/store_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/store"
        
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
            full_url = f"https://{self.network}/load_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/load"
        
        print(f"Full URL: {full_url}")

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
            full_url = f"https://{self.network}/delete_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/delete"
        
        print(f"Full URL: {full_url}")

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
            full_url = f"https://{self.network}/clear_ctx/{ctx}"
        else:
            full_url = f"https://{self.network}/clear"
        
        print(f"Full URL: {full_url}")

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
        ws = None

        try:
            while True:
                try:
                    ws = create_connection(f"wss://{self.network}/sync/{stx}")
                    ws.settimeout(1)
                    ws.send(json.dumps(auth))
                    print("Stream connection set...")

                    try:
                        raw_operation = ws.recv()
                        operation = json.loads(raw_operation)
                        print("Listening to Stream...")
                        yield operation

                        ws.settimeout(None)

                        while True:
                            raw_operation = ws.recv()
                            operation = json.loads(raw_operation)
                            yield operation
                    except socket.timeout:
                        print("No initial data received. Retrying connection...")
                        ws.close()

                except KeyboardInterrupt:
                    print("Stream-Synchronization ended!")
                    if ws:
                        ws.close()
                    print("Connection closed. Exiting.")
                    return
                except Exception as e:
                    print(f"{e}")
                finally:
                    if ws:
                        ws.close()
                        print("Connection closed.")
        except KeyboardInterrupt:
            print("Stream-Synchronization ended!")
            if ws:
                ws.close()
            print("Connection closed. Goodbye!")


__all__ = ['Cell']
