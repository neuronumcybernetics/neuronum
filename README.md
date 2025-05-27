![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net) [![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)

Build, deploy and automate IoT connectivity with `Neuronum`

## Features
- **Cells/Cell-CLI**: Create and manage Neuronum Cells from the command line
- **Nodes/Node-CLI**: Setup and manage Neuronum Nodes from the command line
- **Transmitters (TX)**: Automate economic data transfer
- **Circuits (CTX)**: Store data in Key-Value-Label databases
- **Streams (STX)**: Stream, synchronize and control data in real time
- **Contracts/Tokens**: Automate services exchange and authorization between Cells and Nodes

### Installation
Install the Neuronum library using pip:
```sh
$ pip install neuronum
```

### Cells/Cell-CLI
To interact with the Neuronum Network, you must first create a Neuronum Cell

Create Cell:
```sh
$ neuronum create-cell  
```

Connect Cell:
```sh
$ neuronum connect-cell  
```

View connected Cell:
```sh
$ neuronum view-cell   
```

Disconnect Cell:
```sh
$ neuronum disconnect-cell  
```

Delete Cell:
```sh
$ neuronum delete-cell  
```

### Nodes/Node-CLI
Neuronum Nodes are soft- and hardware components that power the Neuronum Network, enabling seamless communication between Nodes and Cells

Initialize a Node:
```sh
$ neuronum init-node                                              # neuronum init-node --sync id::stx (optional)  
```

Start a Node:
```sh
$ neuronum start-node   
```

Stop a Node:
```sh
$ neuronum stop-node   
```

Register a Node on the Neuronum Network:
```sh
$ neuronum register-node   
```

Update a Node:
```sh
$ neuronum update-node   
```

Delete a Node:
```sh
$ neuronum delete-node   
```

### Transmitters (TX)
Transmitters (TX) are used to create predefined templates to receive and send data in a standardized format

Create Transmitter (TX):
```python
descr = "Test Transmitter"                                        # description (max 25 characters)
key_values = {                                                    # defined keys and example values
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
stx = "id::stx"                                                   # select Stream (STX)
label = "key1:key2"                                               # label TX data
partners = ["id::cell", "id::cell"]                               # authorized Cells
txID = cell.create_tx(descr, key_values, stx, label, partners)    # create TX
```

Activate Transmitter (TX):
```python
TX = "id::tx"                                                     # select Transmitter (TX)
data = {                                                          # enter key-values
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.activate_tx(TX, data)                                        # activate TX
```

Delete Transmitter (TX):
```python
TX = "id::tx"                                                     # select Transmitter (TX)
cell.delete_tx(TX)                                                # delete TX
```

List Transmitter (TX) your Cell can activate:
```python                                            
txList = cell.list_tx()                                           # list Transmitters (TX)
```

### Circuits (CTX)
Circuits (CTX) store and organize data using a Key-Value-Label system

Create Circuit (CTX):
```python
descr = "Test Circuit"                                            # description (max 25 characters) 
partners = ["id::cell", "id::cell"]                               # authorized Cells
ctxID = cell.create_ctx(descr, partners)                          # create Circuit (CTX)
```

Store data on your private Circuit (CTX):
```python
label = "your_label"                                              # data label (should be unique)
data = {                                                          # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data)                                           # store data
```

Store data on a public Circuit (CTX):
```python
CTX = "id::ctx"                                                   # select Circuit (CTX
label = "your_label"                                              # data label (should be unique)
data = {                                                          # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data, CTX)                                      # store data
```

Load data from your private Circuit (CTX):
```python
label = "your_label"                                              # select label
data = cell.load(label)                                           # load data by label
key1 = data["key1"]                                               # get data from key
key2 = data["key2"]
key3 = data["key3"]
print(key1, key2, key3)                                           # print data
```

Load data from a public Circuit (CTX):
```python
CTX = "id::ctx"                                                   # select Circuit (CTX)
label = "your_label"                                              # select label
data = cell.load(label, CTX)                                      # load data by label
key1 = data["key1"]                                               # get data from key
key2 = data["key2"]
key3 = data["key3"]
print(key1, key2, key3)                                           # print data
```

Delete data from your private Circuit (CTX):
```python
label = "your_label"                                              # select label
cell.delete(label)                                                # delete data by label
```

Delete data from a public Circuit (CTX):
```python
CTX = "id::ctx"                                                   # select Circuits (CTX)
label = "your_label"                                              # select label
cell.delete(label, CTX)                                           # delete data by label
```

Clear your private Circuit (CTX):
```python
cell.clear()                                                      # clear Circuit (CTX)
```

Clear Circuit (CTX):
```python
CTX = "id::ctx"                                                   # select Circuit (CTX)
cell.clear(CTX)                                                   # clear CTX
```

Delete Circuit (CTX):
```python
CTX = "id::ctx"                                                   # select Circuit (CTX)
cell.delete_ctx(CTX)                                              # delete CTX
```

List Circuits (CTX) your Cell can interact with:
```python                                            
ctxList = cell.list_ctx()                                         # list Circuits (CTX)
```

### Streams (STX)
Streams (STX) facilitate real-time data synchronization and interaction, ensuring real-time connectivity between Nodes in the Neuronum network

Create Stream (STX):
```python
descr = "Test Stream"                                             # description (max 25 characters) 
partners = ["id::cell", "id::cell"]                               # authorized Cells
stxID = cell.create_stx(descr, partners)                          # create Stream (STX)
```

Stream data to your private Stream (STX):
```python
label = "your_label"                                              # data label
data = {                                                          # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data)                                          # stream data
```

Stream data to a public Stream (STX):
```python
STX = "id::stx"                                                   # select Stream (STX)
label = "your_label"                                              # data label
data = {                                                          # data as key-value pairs
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data, STX)                                     # stream data
```

Sync data from your private Stream (STX):
```python
stream = cell.sync()                                              # synchronize Stream (STX)
for operation in stream:                                          # load stream operations
    label = operation.get("label")                                # get the operation details by key
    key1 = operation.get("data").get("key1")
    key2 = operation.get("data").get("key2")
    key3 = operation.get("data").get("key3")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

Sync data from a public Stream (STX):
```python
STX = "id::stx"                                                   # select Stream (STX)  
stream = cell.sync(STX)                                           # synchronize Stream (STX)
for operation in stream:                                          # load stream operations
    label = operation.get("label")                                # get the operation details by key
    key1 = operation.get("data").get("key1")
    key2 = operation.get("data").get("key2")
    key3 = operation.get("data").get("key3")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

List Streams (STX) your Cell can interact with:
```python                                            
stxList = cell.list_stx()                                         # list Streams (STX)
```

### Contracts/Tokens
Contracts are predefined token-based rules to automate service exchange and authorization between Cells and Nodes

Create a Contract:
```python
descr = "Test Contract"                                           # short description (max 25 characters)
details = {                                                       # define token details
    "price_in_eur": False,                                        # token price in EUR (int, float or False)
    "max_usage": False,                                           # max number of uses (int or False)
    "validity_in_min": False                                      # token expiration time in min (int, float or False)
    }          
partners = ["id::cell", "id::cell"]           
contractID = cell.create_contract(descr, details, partners)
```

Sign a Contract:
```python         
contractID = "id::contract"                                       # select contract        
token = cell.sign_contract(contractID)
```

Request a Token from another Cell to authorize a service:
```python         
cp = "id::cell"                                                   # select counterparty cell
contractID = "id::contract"                                       # select contract  
cell.request_token(cp, contractID)
```

Present a Token to another Cell to authorize a service:
```python   
token = "token"                                                   # select token
cp = "id::cell"                                                   # select counterparty cell
contractID = "id::contract"                                       # select the contract  
cell.present_token(token, cp, contractID)
```

Validate a Token to authorize a service:
```python   
token = "token"                                                   # select token
cp = "id::cell"                                                   # select counterparty cell
contractID = "id::contract"                                       # select contract  
cell.validate_token(token, cp, contractID)
```

List Contracts your Cell can interact with:
```python                                                     
contractList = cell.list_contracts()  
```