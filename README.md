![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)


### **Getting Started Goals**
- Learn about Neuronum
- Connect to Neuronum
- Build on Neuronum


### **About Neuronum**
Neuronum is a central serverless data gateway automating the processing and distribution of data transmission, storage, and streaming.
In practice, Neuronum forms an interconnected network of soft- and hardware components (Nodes) exchanging data in real time.


### **Network Attributes**
**Cell & Nodes**
- Cell: Account to connect and interact with the Neuronum Network
- Nodes: Software and Hardware components connected to Neuronum

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
pip install neuronum         # install neuronum dependencies
```

Create Cell:
```sh
neuronum create-cell         # create Cell / select network and type
```

Connect Cell:
```sh
neuronum connect-cell        # connect Cell
```

View connected Cell:
```sh
neuronum view-cell           # view Cell ID / output = Connected Cell: 'your_cell_id'"
```


------------------



### **Build on Neuronum**
Initialize Node:
```sh
neuronum init-node           # initialize a Node with default template
```

cd to Node folder:
```sh
cd node_node_id              # change to Node folder
```

Start Node:
```sh
neuronum start-node          # start Node (--d flag for detached mode) / output = "Hello, Neuronum!"
```

Stop Node:
```sh
neuronum stop-node           # stop Node
```

Connect Node:
```sh
neuronum connect-node        # connect your Node / Node Type = private / Node description = Test Node
```

Update Node:
```sh
neuronum update-node         # update your Node
```

Disconnect Node:
```sh
neuronum disconnect-node     # disconnect your Node
```

Delete Node:
```sh
neuronum delete-node         # delete your Node
```
