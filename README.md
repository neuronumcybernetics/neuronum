<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum: An E2EE Data Engine</h4>

<p align="center">
  <a href="https://neuronum.net">
    <img src="https://img.shields.io/badge/Website-Neuronum-blue" alt="Website">
  </a>
  <a href="https://github.com/neuronumcybernetics/neuronum">
    <img src="https://img.shields.io/badge/Docs-Read%20now-green" alt="Documentation">
  </a>
  <a href="https://pypi.org/project/neuronum/">
    <img src="https://img.shields.io/pypi/v/neuronum.svg" alt="PyPI Version">
  </a><br>
  <img src="https://img.shields.io/badge/Python-3.8%2B-yellow" alt="Python Version">
  <a href="https://github.com/neuronumcybernetics/neuronum/blob/main/LICENSE.md">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  </a>
</p>

------------------

### **Getting Started into the Neuronum Network**
In this brief getting started guide, you will:
- [Learn about Neuronum](#about-neuronum)
- [Connect to the Network](#connect-to-neuronum)
- [Transmit Data Securely](#transmit-data-securely)
- [Receive Data Securely](#receive-data-securely)

------------------

### **About Neuronum**
Neuronum is a real-time, end-to-end encrypted data engine built in Python. It enables secure communication between devices and services by encrypting data client-side using the recipient's public key. Encrypted messages are transmitted through a passive relay server and decrypted on the recipient’s device using its private key. The relay server facilitates connectivity but cannot access or alter the content of messages.

### Requirements
- Python >= 3.8

------------------

### **Connect To Neuronum**
Installation (optional but recommended: create a virtual environment)
```sh
pip install neuronum
```

Create your Cell (your secure identity):
```sh
neuronum create-cell
```

or

Connect an existing Cell (your secure identity):
```sh
neuronum connect-cell
```

------------------


### **Transmit Data Securely** 
```python
import asyncio
from neuronum import Cell

async def main():
    
    async with Cell() as cell: 

        data = {
            "some": "data"  # Replace with your actual payload
        }

        # Use activate_tx() if you expect a response from the other cell
        # Replace id with the actual Cell ID
        tx_response = await cell.activate_tx("id::cell", data)
        print(tx_response)

        # Stream data to another cell (no response expected)
        # Replace id with the actual Cell ID
        await cell.stream("id::cell", data)

if __name__ == '__main__':
    asyncio.run(main())
```


### **Receive Data Securely** 
```python
import asyncio
from neuronum import Cell

async def main():
    async with Cell() as cell: 
        
        async for transmitter in cell.sync():
            ts_str = transmitter.get("time")
            data = transmitter.get("data")
            transmitter_id = transmitter.get("transmitter_id")   
            client_public_key = data.get("public_key", {})  

            response_data = {
                "json": "Data Received Securely - Your request was processed successfully",
                "html": """
                    <!DOCTYPE html>
                    <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                        <title>Secure Data Response</title>
                    </head>
                    <body>
                        <h3>Data Received Securely</h3>
                        <p>Your request was processed successfully.</p>
                    </body>
                    </html>
                """
            }
            await cell.tx_response(transmitter_id, response_data, client_public_key)

if __name__ == '__main__':
    asyncio.run(main())
```

