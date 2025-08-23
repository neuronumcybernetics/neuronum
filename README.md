<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum: The Real Time Data Engine</h4>

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

### **A Getting Started into the Neuronum Network**
In this brief getting started guide, you will:
- [Learn about Neuronum](#about-neuronum)
- [Connect to the Network](#connect-to-neuronum)
- [Build a Neuronum Node](#build-on-neuronum)
- [Interact with your Node](#interact-with-neuronum)

------------------

### **About Neuronum**
Neuronum is the real-time data engine designed for developers to build event-driven apps and services in minutes using high-level Python

### **Features**
**Cell & Nodes**
- Cell: Account to connect and interact with Neuronum. [Learn More](https://github.com/neuronumcybernetics/neuronum/tree/main/features/cell)
- Nodes (Apps): Soft- and Hardware components hosting Neuronum data gateways. [Learn More](https://github.com/neuronumcybernetics/neuronum/tree/main/features/nodes)

**Data Gateways**
- Transmitters (TX): Securely transmit and receive data packages. [Learn More](https://github.com/neuronumcybernetics/neuronum/tree/main/features/transmitters)
- Circuits (CTX): Store data in cloud-based key-value-label databases. [Learn More](https://github.com/neuronumcybernetics/neuronum/tree/main/features/circuits)
- Streams (STX): Stream, synchronize, and control data in real time. [Learn More](https://github.com/neuronumcybernetics/neuronum/tree/main/features/streams)

### Requirements
- Python >= 3.8
- neuronum >= 5.5.0

------------------

### **Connect To Neuronum**
Installation (optional but recommended: create a virtual environment)
```sh
pip install neuronum                    # install Neuronum dependencies
```

Create your Cell:
```sh
neuronum create-cell                    # create Cell / Cell type / Cell network 
```

or

Connect your Cell:
```sh
neuronum connect-cell                   # connect Cell
```

------------------


### **Build On Neuronum** 
To dive deeper into Neuronum App development, visit & build with [Node Examples](https://github.com/neuronumcybernetics/neuronum/tree/main/features/nodes/examples)

Initialize a Node (app template):
```sh
neuronum init-node --app                # initialize a Node with app template
```

This command prompts you to enter a Node description (e.g Test App) and creates a new directory named node_<node_id> containing the following files:

.env
```env
NODE=your_node_id
HOST=your_cell_id
PASSWORD=your_password
NETWORK=neuronum.net
SYNAPSE=your_synapse                    # auth token
```

app.py
```python
import asyncio
import neuronum
import os
from dotenv import load_dotenv

load_dotenv()
host = os.getenv("HOST")
password = os.getenv("PASSWORD")
network = os.getenv("NETWORK")
synapse = os.getenv("SYNAPSE")

cell = neuronum.Cell(
    host=host,
    password=password,
    network=network,
    synapse=synapse
)

async def main():      
    STX = "id::stx"                                          
    async for operation in cell.sync(STX):       
        txID = operation.get("txID")
        client = operation.get("operator")                    
                            
        if txID == "id::tx":             
            data = {
                "json": f"Hello {client}",
                "html": f"""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>Greeting Node</title>
  </head>
  <body>
    <div class="card">
      <h1>Hello, {client}</h1>
    </div>
  </body>
</html>
"""

            }
            await cell.tx_response(txID, client, data)

asyncio.run(main())
```

config.json (required if you want to make your app accessible to Cellai (currently in testing))
```json
{                       
    "data_gateways": [
        {
        "type": "stream",
        "id": "id::stx",
        "info": "provide a detailed description about the stream"
        },
        {
        "type": "transmitter",
        "id": "id::tx",
        "info": "provide a detailed description about the transmitter"
        },
        {
        "type": "circuit",
        "id": "id::ctx",
        "info": "provide a detailed description about the circuit"
        }
    ]
}
```

NODE.md (required if you want to publish your App)
```
### NODE.md: Create a detailed Markdown File on how to interact with this Node
```


Change into Node folder
```sh
cd node_node_id                         # change directory
```

Start your Node:
```sh
neuronum start-node                     # start Node
```

------------------

### **Interact with Neuronum**
#### **Web-based**
1. [Visit Neuronum](https://neuronum.net)
2. [Connect your Cell](https://neuronum.net/connect)
3. [Explore Transmitters](https://neuronum.net/explore)
4. Activate Transmitters

#### **Code-based**
```python
import asyncio
import neuronum

cell = neuronum.Cell(                                   # set Cell connection
    host="host",                                        # Cell host
    password="password",                                # Cell password
    network="neuronum.net",                             # Cell network -> neuronum.net
    synapse="synapse"                                   # Cell synapse
)

async def main():
                                                            
    TX = "id::tx"                                       # select the Transmitter TX
    data = {"say": "hello"}
    tx_response = await cell.activate_tx(TX, data)      # activate TX - > get response back
    print(tx_response)                                  # print tx response
                                      
asyncio.run(main())
```

#### **CLI-based**
```sh
neuronum activate --tx id::tx 'say:hello'
```

#### **Cellai**
Cellai is a mobile interface that lets you interact with Neuronum apps using natural language. It is currently in testing.

