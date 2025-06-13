![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)


### **Getting Started Goals**
- Learn about Neuronum
- Connect to Neuronum
- Build on Neuronum


### **About Neuronum**
Neuronum is a framework to build serverless data gateways automating the processing and distribution of data transmission, storage, and streaming.


### **Network Attributes**
**Cell & Nodes**
- Cell: Account to connect and interact with the Neuronum Network
- Nodes: Software and Hardware components hosting data gateways

**Data Gateways**
- Transmitters (TX): Automate data transfer in standardized formats
- Circuits (CTX): Store data in cloud-based key-value-label databases
- Streams (STX): Stream, synchronize, and control data in real time


#### Requirements
- Python >= 3.8 -> https://www.python.org/downloads/
- neuronum >= 4.0.0 -> https://pypi.org/project/neuronum/


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

Connect Cell:
```sh
neuronum connect-cell                   # connect Cell
```

View connected Cell:
```sh
neuronum view-cell                      # view Cell / output = Connected Cell: 'your_cell'"
```

Disconnect Cell:
```sh
neuronum disconnect-cell                # disconnect Cell
```

Delete Cell:
```sh
neuronum delete-cell                    # delete Cell
```


------------------



### **Build on Neuronum**
Initialize Node (default template):
```sh
neuronum init-node                      # initialize a Node with default template
```

Initialize Node (stream template):
```sh
neuronum init-node --stream id::stx     # initialize a Node with stream template
```

Initialize Node (sync template):
```sh
neuronum init-node --sync id::stx       # initialize a Node with sync template
```

cd to Node folder:
```sh
cd node_node_id                         # change to Node folder
```

Start Node:
```sh
neuronum start-node                     # start Node
```

Start Node (detached mode):
```sh
neuronum start-node --d                 # start Node in "detached" mode
```

Stop Node:
```sh
neuronum stop-node                      # stop Node
```

Connect Node:
```sh
neuronum connect-node                   # connect your Node / Node type / Node description
```

Update Node:
```sh
neuronum update-node                    # update your Node
```

Disconnect Node:
```sh
neuronum disconnect-node                # disconnect your Node
```

Delete Node:
```sh
neuronum delete-node                    # delete your Node
```
