<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum Streams (STX): Stream, Synchronize, and Control Data in Real-Time</h4>

<p align="center">
  <a href="https://neuronum.net">
    <img src="https://img.shields.io/badge/Website-Neuronum-blue" alt="Website">
  </a>
  <a href="https://github.com/neuronumcybernetics/neuronum">
    <img src="https://img.shields.io/badge/Docs-Read%20now-green" alt="Documentation">
  </a>
  <a href="https://pypi.org/project/neuronum/">
    <img src="https://img.shields.io/pypi/v/neuronum.svg" alt="PyPI Version">
  </a><br>
  <img src="https://img.shields.io/badge/Python-3.8%2B-yellow" alt="Python Version">
  <a href="https://github.com/neuronumcybernetics/neuronum/blob/main/LICENSE.md">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  </a>
</p>

------------------

### **About Neuronum Streams (STX)**
Neuronum Streams (STX) are data gateways used to stream, synchronize and control data between Neuronum Nodes in real time. Neuronum Streams (STX) can be compared to radio channels. Nodes send data to a channel that can be synchronized by every Node of the Network. Streams (STX) can be created to be private, public or accessible for a defined list of partners

------------------

### **Create and Stream Data through a Public Stream (STX)**
```python
import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse (auth token)
)

async def main():

    descr = "Test Stream"                                                   # describe your Stream STX (max 25 characters)
    partners = ["public"]                                                   # A public Stream all Cells can synchronize
    stxID = await cell.create_stx(descr, partners)                          # create the Stream STX -> get stxID back
    print(f"Stream ID: {stxID}")                                            # print the Stream STX ID


    STX = stxID                                                             # select the Stream STX
    label = "label"                                                         # label your data
    data = {                                                                # data as key-value pairs
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    await cell.stream(label, data, STX)                                     # stream data to Stream STX - > get success message back

asyncio.run(main())
```

### **Synchronize a Public Stream (STX)**
```python
import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)


async def main():

    STX = "id::stx"                                                         # select the Stream STX
    async for operation in cell.sync(STX):                                  # get Stream operations
        label = operation.get("label")                                      # get Stream operation details
        data = operation.get("data")
        ts = operation.get("time")
        stxID = operation.get("stxID")
        operator = operation.get("operator")
        print(label, data, ts, stxID, operator)                             # print Stream operation details                                                 

asyncio.run(main())
```