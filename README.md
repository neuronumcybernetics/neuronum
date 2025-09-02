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
Visit & build with [Node Examples](https://github.com/neuronumcybernetics/neuronum/tree/main/features/nodes/examples) to gain deeper knowledge on how to build on Neuronum.

To get started, initialize a new Node with the command below. 
```sh
neuronum init-node
```

This command will prompt you for a description (e.g., Test App) and will create

1. A Stream (STX) so your App can receive requests, and a Transmitter (TX) to match those requests
2. A new directory named "Test App_<your_node_id>" with the following files

.env: Stores your Node's credentials for connecting to the network.

app.py: The main Python script that contains your Node's core logic.

NODE.md: Public documentation that provides instructions for interacting with your Node.

config.json: A configuration file that stores metadata about your app and enables Cellai to interact with your Node's data gateways.

ping.html: A static HTML file used to render web-based responses.

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

#### **Cellai (in Testing)**
Cellai is an AI tool for developers to test their apps built on Neuronum and will soon be published to the Google Play Store.

