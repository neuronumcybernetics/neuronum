![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net)
[![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)
[![Tutorials](https://img.shields.io/badge/Tutorials-Watch%20now-red)](https://www.youtube.com/@neuronumnet)

`Neuronum` is a cybernetic framework enabling businesses to build interconnected networks of Hardware and Software components

## Features
- **Cell**: Identity to connect and interact with the Neuronum Network
- **Transmitters (TX)**: Automate economic data transfer and storage
- **Circuits (CTX)**: Store data in a Key-Value-Label database
- **Streams (STX)**: Stream, synchronize and control data in real time
- **Nodes**: Hard-/Software components participating in the Network ecosystem
- **Contracts/Tokens**: Automate Contract-based authorization between Nodes

## Getting Started
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
host="host::cell",                              # specify your cell host 
password="your_password",                       # enter your cell password 
network="neuronum.net",                         # choose network 
synapse="your_synapse"                          # provide the synapse (token)
)
cell.connect()
```

### Transmitters (TX)
Transmitters (TX) are used to create predefined templates to receive and send data in a standardized format. Data send with TX is always and automatically stored in a predefined Circuit (CTX)

Create Transmitter (TX):
```python
descr = "Test Transmitter"                      # short description (max 25 characters)
key_values = {                                  # predefined keys with example values
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
ctx = "id::ctx"                                 # target Circuit (CTX)
label = "key1:key2"                             # label data sent with the TX
partners = ["id::cell", "id::cell"]             # authorized cells
txID = cell.create_tx(decr, key_values, ctx, label, partners) 
```

Activate Transmitter (TX):
```python
TX = "id::tx"                                   # specify the Transmitter (TX)
data = {                                        # enter key values
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.activate_tx(TX, data)  
```

Delete Transmitter (TX):
```python
TX = "id::tx"                                   # specify the Transmitter (TX)
cell.delete_tx(TX)  
```

List Transmitter (TX) from cell:
```python
cell = "id::cell"                               # specify cell
txList = cell.list_tx(cell)  
```

### Circuits (CTX)
Circuits (CTX) store and organize data sent via Transmitters (TX) using a Key-Value-Label system, ensuring efficient retrieval and management within the Neuronum network

Create Circuit (CTX):
```python
descr = "Test Circuit"                          # short description of the circuit (max 25 characters) 
partners = ["id::cell", "id::cell"]             # authorized cells
ctxID = cell.create_ctx(decr, partners)   
```

Store data on your private Circuit (CTX):
```python
label = "your_label"                            # define a unique label (tag)
data = {                                        # store data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data)
```

Store data on a public Circuit (CTX):
```python
CTX = "id::ctx"                                 # specify the Circuit (CTX
label = "your_label"                            # define a unique label (tag)
data = {                                        # store data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data, CTX)
```

Load data from your private Circuit (CTX):
```python
label = "your_label"                            # load data by label
data = cell.load(label)  
key1 = data["key1"]                             # get the data from the keys
key2 = data["key2"]
key3 = data["key3"]
```

Load data from a public Circuit (CTX):
```python
CTX = "id::ctx"                                 # specify the CTX
label = "your_label"                            # load data by label
data = cell.load(label, CTX)    
key1 = data["key1"]                             # get the data from the keys
key2 = data["key2"]
key3 = data["key3"]
```

Delete data from your private Circuit (CTX):
```python
label = "your_label"                            # delete data by label
cell.delete(label)      
```

Delete data from a public Circuit (CTX):
```python
CTX = "id::ctx"                                 # specify the CTX
label = "your_label"                            # delete data by label
cell.delete(label, CTX)
```

Empty your private Circuit (CTX):
```python
cell.clear()
```

Empty a Circuit (CTX):
```python
CTX = "id::ctx"                                 # specify the CTX
cell.clear(CTX)
```

Delete Circuit (CTX):
```python
CTX = "id::ctx"                                 # specify the Circuit (CTX)
cell.delete_ctx(CTX)   
```

List Circuits (CTX) from cell:
```python
cell = "id::cell"                               # specify cell
ctxList = cell.list_ctx(cell)  
```

### Streams (STX)
Streams (STX) facilitate real-time data synchronization and interaction, ensuring seamless connectivity between all Nodes in the Neuronum network

Create Stream (CTX):
```python
descr = "Test Stream"                           # short description (max 25 characters) 
partners = ["id::cell", "id::cell"]             # authorized cells
stxID = cell.create_stx(decr, partners)  
```

Stream data to your private Stream (STX):
```python
label = "your_label"                            # label your data
data = {                                        # define data package (key-values)
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data)
```

Stream data to a public Stream (STX):
```python
STX = "id::stx"                                 # specify the STX
label = "your_label"                            # label your data
data = {                                        # define data package (key-values)
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data, STX)
```

Sync data from your private Stream (STX):
```python
stream = cell.sync()                            # retrieve stream data
for operation in stream:                        # iterate through each operation
    label = operation.get("label")              # get the operation details
    key1 = operation.get("data").get("key1")
    key2 = operation.get("data").get("key2")
    key3 = operation.get("data").get("key3")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

Sync data from a public Stream (STX):
```python
STX = "id::stx"                                 # specify the STX  
stream = cell.sync(STX)                         # retrieve stream data
for operation in stream:                        # iterate through each operation
    label = operation.get("label")              # get the operation details
    key1 = operation.get("data").get("key1")
    key2 = operation.get("data").get("key2")
    key3 = operation.get("data").get("key3")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

List Streams (STX) from cell:
```python
cell = "id::cell"                               # specify cell
stxList = cell.list_stx(cell)  
```

### Nodes
Neuronum Nodes are computing hardware running the Neuronum Client Library, enabling seamless data transmission, synchronization, and facilitating public Stream (STX) access

Register a Node with its associated Stream (STX):
```python
descr = "node_name"                             # short description (max 25 characters) 
mode = "public"                                 # set to "public or "private
STX = "id::stx"                                 # specify the STX
nodeID = cell.register_node(descr, mode, STX)  
```

Remove a Node:
```python
nodeID = "id::node"                             # get Node by ID
cell.delete_node(nodeID)  
```


### Contracts/Tokens
Contracts define rules for authorization, allowing users to sign and generate unique tokens for secure access

Create a Contract:
```python
descr = "Test Contract"                         # short description (max 25 characters)
details = {                                     # define token details
    "price_in_eur": 10,                         # token price in EUR
    "max_usage": 10,                            # max number of uses
    "validity_in_min": 10                       # token expiration time (minutes)
    }          
partners = ["id::cell", "id::cell"]           
contractID = cell.create_contract(descr, details, partners)
```

Sign a Contract:
```python         
contractID = "id::contract"                     # specify the contract        
token = cell.sign_contract(contractID)
```

Request a Token from another Cell to authorize a service:
```python         
cp = "id::cell"                                 # specify the counterparty cell
contractID = "id::contract"                     # specify the contract  
cell.request_token(cp, contractID)
```

Present a Token to another Cell to authorize a service:
```python   
token = "token"                                 # specify the token
cp = "id::cell"                                 # specify the counterparty cell
contractID = "id::contract"                     # specify the contract  
cell.present_token(token, cp, contractID)
```

Validate a Token to authorize a service:
```python   
token = "token"                                 # specify the token
cp = "id::cell"                                 # specify the counterparty cell
contractID = "id::contract"                     # specify the contract  
cell.validate_token(token, cp, contractID)
```

List Contracts from cell:
```python
cell = "id::cell"                               # specify cell
contractList = cell.list_contracts(cell)  
```
