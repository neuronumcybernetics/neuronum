![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)

A Getting Started into the Neuronum Network

## Getting Started Goals
- **Neuronum Cell**: Create a "Cell" to start interacting with the Network
- **Node**: Setup a Neuronum Node that synchronizes real-time data of the Node: https://neuronum.net/node/lPW178VeY0WV::node


### Requirements
- Python >= 3.8 -> https://www.python.org/downloads/
- Neuronum Lib >= 1.7.2 -> https://pypi.org/project/neuronum/


### Installation
Install the Neuronum library:
```sh
$ pip install neuronum
```

### Neuronum Cell
Create your Cell:
```sh
$ neuronum create-cell                              # select community cell / select neuronum.net
```

View connected Cell:
```sh
$ neuronum view-cell                                # output = Connected Cell: '<your_cell_id>'"
```

### Node
Initialize your Node:
```sh
$ neuronum init-node                                # initializes a node
```

Start your Node:
```sh
$ neuronum start-node                               # real-time data stream output = "Hello, Neuronum!"
```

Stop your Node:
```sh
$ neuronum stop-node                                # stops Node
```
