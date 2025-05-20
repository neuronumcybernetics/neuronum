![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net)
[![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)
[![Tutorials](https://img.shields.io/badge/Tutorials-Watch%20now-red)](https://www.youtube.com/@neuronumnet)

`Neuronum` is a cybernetic framework enabling businesses to build & automate interconnected networks of soft- and hardware components

## Features
- **Cell**: Identity to connect and interact with the Neuronum Network
- **Transmitters (TX)**: Automate economic data transfer and storage
- **Circuits (CTX)**: Store data in a Key-Value-Label database
- **Streams (STX)**: Stream, synchronize and control data in real time
- **Nodes**: Soft-/Hardware components participating in the Network ecosystem

To interact with the Network you will need to create a Neuronum Cell. 
Create your Cell: [Create Cell](https://neuronum.net/createcell)

Start with installing the Neuronum library using pip:
```python
pip install neuronum
```

Configure and test Cell connection:
```python
import neuronum

cell = neuronum.Cell(
host="host::cell",                                                      # cell host 
password="your_password",                                               # cell password 
network="neuronum.net",                                                 # cell network 
synapse="your_synapse"                                                  # cell synapse
)           
cell.connect()                                                          # connect to network
```

### Transmitters (TX)
Transmitters (TX) are used to create predefined templates to receive and send data in a standardized format. Data sent with TX is always and automatically stored in a predefined Circuit (CTX)

Create Transmitter (TX):
```python
descr = "Test Transmitter"                                              # description (max 25 characters)
key_values = {                                                          # defined keys and example values
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
ctx = "id::ctx"                                                         # select Circuit (CTX)
label = "key1:key2"                                                     # label TX data
partners = ["id::cell", "id::cell"]                                     # authorized Cells
txID = cell.create_tx(descr, key_values, ctx, label, partners) 
```

Activate Transmitter (TX):
```python
TX = "id::tx"                                                           # select Transmitter (TX)
data = {                                                                # enter key-values
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.activate_tx(TX, data)                                              # activate TX
```

Delete Transmitter (TX):
```python
TX = "id::tx"                                                           # select Transmitter (TX)
cell.delete_tx(TX)                                                      # delete TX
```

List Transmitter (TX) from Cell:
```python
cellID = "id::cell"                                                       # select Cell
txList = cell.list_tx(cellID)                                             # list Transmitters (TX)
```

### Circuits (CTX)
Circuits (CTX) store and organize data sent via Transmitters (TX) using a Key-Value-Label system

Create Circuit (CTX):
```python
descr = "Test Circuit"                                                  # description (max 25 characters) 
partners = ["id::cell", "id::cell"]                                     # authorized Cells
ctxID = cell.create_ctx(descr, partners)                                # create Circuit (CTX)
```

Store data on your private Circuit (CTX):
```python
label = "your_label"                                                    # data label (should be unique)
data = {                                                                # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data)                                                 # store data
```

Store data on a public Circuit (CTX):
```python
CTX = "id::ctx"                                                         # select Circuit (CTX
label = "your_label"                                                    # data label (should be unique)
data = {                                                                # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data, CTX)                                            # store data
```

Load data from your private Circuit (CTX):
```python
label = "your_label"                                                    # select label
data = cell.load(label)                                                 # load data by label
key1 = data["key1"]                                                     # get data from key
key2 = data["key2"]
key3 = data["key3"]
print(key1, key2, key3)                                                 # print data
```

Load data from a public Circuit (CTX):
```python
CTX = "id::ctx"                                                         # select Circuit (CTX)
label = "your_label"                                                    # select label
data = cell.load(label, CTX)                                            # load data by label
key1 = data["key1"]                                                     # get data from key
key2 = data["key2"]
key3 = data["key3"]
print(key1, key2, key3)                                                 # print data
```

Delete data from your private Circuit (CTX):
```python
label = "your_label"                                                    # select label
cell.delete(label)                                                      # delete data by label
```

Delete data from a public Circuit (CTX):
```python
CTX = "id::ctx"                                                         # select Circuits (CTX)
label = "your_label"                                                    # select label
cell.delete(label, CTX)                                                 # delete data by label
```

Clear your private Circuit (CTX):
```python
cell.clear()                                                            # clear Circuit (CTX)
```

Clear Circuit (CTX):
```python
CTX = "id::ctx"                                                         # select Circuit (CTX)
cell.clear(CTX)                                                         # clear CTX
```

Delete Circuit (CTX):
```python
CTX = "id::ctx"                                                         # select Circuit (CTX)
cell.delete_ctx(CTX)                                                    # delete CTX
```

List Circuits (CTX) from Cell:
```python
cellID = "id::cell"                                                       # select Cell
ctxList = cell.list_ctx(cellID)                                           # list Circuits (CTX)
```

### Streams (STX)
Streams (STX) facilitate real-time data synchronization and interaction, ensuring real-time connectivity between Nodes in the Neuronum network

Create Stream (STX):
```python
descr = "Test Stream"                                                   # description (max 25 characters) 
partners = ["id::cell", "id::cell"]                                     # authorized Cells
stxID = cell.create_stx(descr, partners)                                # create Stream (STX)
```

Stream data to your private Stream (STX):
```python
label = "your_label"                                                    # data label
data = {                                                                # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data)                                                # stream data
```

Stream data to a public Stream (STX):
```python
STX = "id::stx"                                                         # select Stream (STX)
label = "your_label"                                                    # data label
data = {                                                                # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data, STX)                                           # stream data
```

Sync data from your private Stream (STX):
```python
stream = cell.sync()                                                    # synchronize Stream (STX)
for operation in stream:                                                # load stream operations
    label = operation.get("label")                                      # get the operation details by key
    key1 = operation.get("data").get("key1")
    key2 = operation.get("data").get("key2")
    key3 = operation.get("data").get("key3")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

Sync data from a public Stream (STX):
```python
STX = "id::stx"                                                         # select Stream (STX)  
stream = cell.sync(STX)                                                 # synchronize Stream (STX)
for operation in stream:                                                # load stream operations
    label = operation.get("label")                                      # get the operation details by key
    key1 = operation.get("data").get("key1")
    key2 = operation.get("data").get("key2")
    key3 = operation.get("data").get("key3")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

List Streams (STX) from Cell:
```python
cellID = "id::cell"                                                       # select Cell
stxList = cell.list_stx(cellID)                                           # list Streams (STX)
```

### Nodes
Neuronum Nodes are computing hardware running the Neuronum Client Library, enabling seamless data transmission, synchronization, and facilitating public Stream (STX) access

Register a Node with its associated Stream (STX):
```python
descr = "node_name"                                                     # description (max 25 characters) 
mode = "public"                                                         # "public" or "private" Node
STX = "id::stx"                                                         # select Stream (STX)
nodeID = cell.register_node(descr, mode, STX)                           # register Node
```

Delete Node:
```python
nodeID = "id::node"                                                     # select Node
cell.delete_node(nodeID)                                                # delete Node
```
