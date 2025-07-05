<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum: A Serverless Data Network in Pure Python</h4>

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
- Learn about Neuronum
- Connect to the Network
- Build a Neuroum Node
- Interact with your Node

------------------

### **About Neuronum**
Neuronum empowers developers to build & connect apps, services, and devices into serverless networks able to exchange data in real time

### **Features**
**Cell & Nodes**
- Cell: Account to connect and interact with Neuronum. [Learn More](https://github.com/neuronumcybernetics/neuronum/tree/main/features/cell)
- Nodes: Soft- and Hardware components hosting Neuronum data gateways. [Learn More](https://github.com/neuronumcybernetics/neuronum/tree/main/features/nodes)

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


### **Build On Neuronum** **[(Build with Node Examples)](https://github.com/neuronumcybernetics/neuronum/tree/main/features/nodes)**
Initialize a Node (app template):
```sh
neuronum init-node --app                # initialize a Node with app template -> creates a folder named node_<node_id> containing all relevant files
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

