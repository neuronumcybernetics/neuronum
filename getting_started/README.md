![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)

A Getting Started into the Neuronum Network

## Getting Started Goals
- **Neuronum Cell**: Create a Cell to start interacting with the Network
- **Neuronum Node**: Setup a Node that streams and syncs the message: Hello, Neuronum! in real-time


### Requirements
- Python >= 3.8 -> https://www.python.org/downloads/
- Neuronum Lib >= 1.7.2 -> https://pypi.org/project/neuronum/


### Installation
Install the Neuronum library:
```sh
$ pip install neuronum         # install the neuronum dependencies using pip
```

### Neuronum Cell
Create your Cell:
```sh
$ neuronum create-cell         # create Cell / select network and type
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
$ cd node_your_node_id         # change directory
```

Start your Node:
```sh
$ neuronum start-node          # start Node / output = "Hello, Neuronum!"
```

Stop your Node:
```sh
$ neuronum stop-node           # stop Node
```
