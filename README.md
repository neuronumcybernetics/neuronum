![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)


## **Getting Started Goals**
- Learn about Neuronum
- Connect to Neuronum
- Build on Neuronum


### **About Neuronum**
Neuronum is a framework to build serverless connected data networks automating the processing and distribution of data transmission, storage, and streaming.


### **Use Cases**
- Build, deploy & automate data networks


### **Attributes**
**Cell & Nodes**
- Cell: Account to connect and interact with Neuronum
- Nodes: Soft- and Hardware components hosting data gateways

**Data Gateways**
- Transmitters (TX): Securely transmit and receive data packages
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


View connected Cell:
```sh
neuronum view-cell                      # view Cell / output = Connected Cell: 'cell_id'"
```


------------------


### **Build on Neuronum**
**Node Examples:**  
Visit: https://github.com/neuronumcybernetics/neuronum/tree/main/how_tos/nodes

Initialize Node (default template):
```sh
neuronum init-node                      # initialize a Node with default template
```

Start Node:
```sh
neuronum start-node                     # start Node
```

Stop Node:
```sh
neuronum stop-node                      # stop Node
```