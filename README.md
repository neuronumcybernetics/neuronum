![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)

A Getting Started into the Neuronum Network: Build, deploy and automate serverless data infrastructures for an interconnected world

### **What's New in neuronum 3.0.2**
- Added CLI feature in `neuronum connect-node`: Select whether your Node will be publicly or privately listed

### **New Feature Set**
- **Cell/Cell-CLI**: Create and manage your Neuronum Cell, a unique identity for interacting with the Network, directly from the command line.
- **Nodes/Node-CLI**: Setup and manage Neuronum Nodes, the software and hardware components that power the Network, via the command line.
- **Transmitters (TX)**: Automate economic data transfer using predefined templates for standardized data exchange.
- **Circuits (CTX)**: Store, manage, and retrieve structured data with Circuits, a cloud-based Key-Value-Label database.
- **Streams (STX)**: Stream, synchronize, and control data in real time, enabling dynamic and responsive data flows.
- **Contracts/Tokens**: Automate service exchange and authorization, ensuring secure interactions between Cells and Nodes.
- **Scan**: Discover Cells and Nodes via BLE-based scanning, powered by Bleak, for seamless network integration.
- **Cellai**: A local AI assistant currently in development (version 0.0.1). While still evolving, Cellai is designed to automate communication between Cells and Nodes, optimizing intelligent data flow and network interactions in future releases.


## Getting Started Goals
- Create a Cell to start interacting with the Network
- Setup a private Node that streams and syncs the message: Hello, Neuronum!
- Connect your Node to the Neuronum Network


### Requirements
- Python >= 3.8 -> https://www.python.org/downloads/
- neuronum >= 3.0.0 -> https://pypi.org/project/neuronum/


### Installation
Install the Neuronum library:
```sh
$ pip install neuronum         # install the neuronum dependencies
```

### Neuronum Cell
Create your Cell:
```sh
$ neuronum create-cell         # create Cell / select network and type
```

Connect your Cell:
```sh
$ neuronum connect-cell        # connect Cell
```

View connected Cell:
```sh
$ neuronum view-cell           # view Cell ID / output = Connected Cell: 'your_cell_id'"
```

### Neuronum Node
Initialize your Node:
```sh
$ neuronum init-node           # initialize a Node with default template
```

cd into Node Folder:
```sh
$ cd node_nodeID               # change directory
```

Start your Node:
```sh
$ neuronum start-node          # start Node / scan = Off / output = "Hello, Neuronum!"
```

Stop your Node:
```sh
$ neuronum stop-node           # stop Node
```

Connect your Node:
```sh
$ neuronum connect-node        # connect your Node / Choose Node Type = private / Node description = Test Node
```

Update your Node:
```sh
$ neuronum update-node         # update your Node
```

Disconnect your Node:
```sh
$ neuronum disconnect-node     # disconnect your Node
```

Delete your Node:
```sh
$ neuronum delete-node         # delete your Node
```