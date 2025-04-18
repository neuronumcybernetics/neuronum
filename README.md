![Neuronum Logo](https://neuronum.net/static/logo_pip.png "Neuronum")

[![Website](https://img.shields.io/badge/Website-Neuronum-blue)](https://neuronum.net)
[![Documentation](https://img.shields.io/badge/Docs-Read%20now-green)](https://github.com/neuronumcybernetics/neuronum)
[![Tutorials](https://img.shields.io/badge/Tutorials-Watch%20now-red)](https://www.youtube.com/@neuronumnet)

Interact with the `Neuronum Network` to build, connect & automate economic data streams.

## Cell Features
- **Transmitters (TX)**: Automate economic data transfer + Circuits Integration
- **Circuits (CTX)**: A simple Key-Value-Label database to store economic data
- **Streams (STX)**: Stream, synchronize and control data in real time

## Getting Started
Create your Neuronum Cell: [Create Cell](https://neuronum.net/createcell)

Install the Neuronum library using pip:
```bash
pip install neuronum
```

Set and test Cell connection:
```bash
import neuronum

cell = neuronum.Cell(
host="host::cell",
password="your_password",
network="neuronum.net",
synapse="your_synapse"
)
cell.test_connection()
```

### Transmitters (TX)
Activate Transmitter (TX):
```bash
TX = "id::tx"
data = {
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.activate(TX, data)
```

### Circuits (CTX)
Store data on your private Circuit (CTX):
```bash
label = "your_label"
data = {
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data)
```

Store data on a public Circuit (CTX):
```bash
CTX = "id::ctx"
label = "your_label"
data = {
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.store(label, data, CTX)
```

Load data from your private Circuit (CTX):
```bash
label = "your_label"
data = cell.load(label)
key1 = data["key1"]
key2 = data["key2"]
key3 = data["key3"]
```

Load data from a public Circuit (CTX):
```bash
CTX = "id::ctx"
label = "your_label"
data = cell.load(label, CTX)
key1 = data["key1"]
key2 = data["key2"]
key3 = data["key3"]
```

Delete data from your private Circuit (CTX):
```bash
label = "your_label"
data = cell.delete(label)
```

Delete data from a public Circuit (CTX):
```bash
CTX = "id::ctx"
label = "your_label"
data = cell.delete(label, CTX)
```

Empty your private Circuit (CTX):
```bash
cell.clear()
```

Empty a public Circuit (CTX):
```bash
CTX = "id::ctx"
cell.clear(CTX)
```

### Streams (STX)
Stream data to your private Stream (STX):
```bash
label = "your_label"
data = {
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data)
```

Stream data to a public Stream (STX):
```bash
STX = "id::stx"
label = "your_label"
data = {
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}
cell.stream(label, data, STX)
```

Sync data from your private Stream (STX):
```bash
stream = cell.sync()
for operation in stream:
    label = operation.get("label")
    value = operation.get("data").get("key1")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

Sync data from a public Stream (STX):
```bash
STX = "id::stx"
stream = cell.sync(STX)
for operation in stream:
    label = operation.get("label")
    value = operation.get("data").get("key1")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
```

