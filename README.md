![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)


## **Getting Started Goals**
- Learn about Neuronum
- Connect to Neuronum
- Build on Neuronum
- Interact with Neuronum


### **About Neuronum**
Neuronum is a framework to build serverless connected app & data gateways automating the processing and distribution of data transmission, storage, and streaming.


### **Features**
**Cell & Nodes**
- Cell: Account to connect and interact with Neuronum
- Nodes: Soft- and Hardware components hosting gateways

**Gateways**
- Transmitters (TX): Securely transmit and receive data packages
- Circuits (CTX): Store data in cloud-based key-value-label databases
- Streams (STX): Stream, synchronize, and control data in real time


#### Requirements
- Python >= 3.8 -> https://www.python.org/downloads/
- neuronum >= 5.3.0 -> https://pypi.org/project/neuronum/


------------------


### **Connect to Neuronum**
Installation
```sh
pip install neuronum                    # install neuronum dependencies
```

Create Cell:
```sh
neuronum create-cell                    # create Cell / Cell type / Cell network 
```

or

Connect Cell:
```sh
neuronum connect-cell                   # connect Cell
```

------------------


### **Build on Neuronum**
Initialize Node (app template):
```sh
neuronum init-node --app                # initialize a Node with app template
```

Change into Node folder
```sh
cd node_node_id                         # change directory
```

Start Node:
```sh
neuronum start-node                     # start Node
```

**Node Examples**
Visit: https://github.com/neuronumcybernetics/neuronum/tree/main/how_tos/nodes


------------------


### **Interact with Neuronum**
1. Visit: https://neuronum.net
2. Connect your Cell
3. Explore Transmitters
4. Activate Transmitters