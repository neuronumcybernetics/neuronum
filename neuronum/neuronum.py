import requests
import socket
from typing import Optional
import ssl
from websocket import create_connection
from typing import List
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

        print("SSL socket set")

        try:

            stream = {
                "label": label,
                "data": data,
            }

            print(f"Connecting to {self.network}")
            self.sock.connect((self.network, 55555))
            print("SSL socket connected")

            if not self.authenticate(self.sock, stx):
                print("Authentication failed. Cannot stream.")
                return

            self.sock.sendall(json.dumps(stream).encode('utf-8'))
            print(f"Sent: {stream}")

        except ssl.SSLError as e:
            print(f"SSL error occurred: {e}")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        finally:
            self.sock.close()
            print("SSL connection closed.")


    def authenticate(self, sock, stx: Optional[str] = None):
            credentials = f"{self.host}\n{self.password}\n{self.synapse}\n{stx}\n"
            sock.sendall(credentials.encode('utf-8'))
            
            response = sock.recv(1024).decode('utf-8')
            print(response)
            return "Authentication successful" in response
    

    def sync(self, stx: Optional[str] = None) -> List[str]:
        stream = []
        try:
            auth = {
                "host": self.host,
                "password": self.password,
                "synapse": self.synapse,
            }

            ws = create_connection(f"wss://{self.network}/sync/{stx}")
            ws.settimeout(1)
            print(f"Auth Payload: {auth}")
            ws.send(json.dumps(auth))

        except Exception as e:
            print(f"Failed to connect: {e}")
            return stream

        try:
            while True:
                message = ws.recv()
                print(f"Received Data: {message}")
                stream.append(message)
        except KeyboardInterrupt:
            print("Closing connection...")
        except Exception as e:
            print(f"Error during data collection: {e}")
        finally:
            ws.close()
            print("Connection closed.")

        return stream
  
__all__ = ['Cell']
