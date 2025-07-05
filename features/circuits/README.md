<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum Circuits (CTX): Cloud Key-Value-Label Databases</h4>

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

---

### **About Neuronum Circuits (CTX)**
Neuronum Circuits (CTX) are key-value-label databases in the cloud and used to store and share resources between Neuronum Nodes. Circuits (CTX) can be created to be private, public or accessible for a defined list of partners

------------------

### **Create, Store, and Load Data from a Public Circuit (CTX)**
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

    descr = "My Public Circuit"                                             # describe your Circuit CTX (max 25 characters)
    partners = ["public"]                                                   # a public Circuit CTX all Cells can store data in
    ctxID = await cell.create_ctx(descr, partners)                          # create the Circuit CTX -> get ctxID back
    print(f"Circuit ID: {ctxID}")                                           # print the Circuit CTX ID


    CTX = ctxID                                                             # select the Circuit (CTX
    label = "label"                                                         # label your data
    data = {                                                                # data as key-value pairs
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    await cell.store(label, data, CTX)                                      # store data - > get success message back


    data = await cell.load(label, CTX)                                      # load data by label and CTX
    key1 = data["key1"]                                                     # get data from key
    key2 = data["key2"]
    key3 = data["key3"]
    print(key1, key2, key3)                                                 # print data

    
    await cell.delete(label, CTX)                                           # delete data by label and CTX - > get success message back


    await cell.clear(CTX)                                                   # clear Circuit (CTX) - > get success message back

asyncio.run(main())
```

#### **CLI-based**
```sh
neuronum load --ctx id::ctx 'label'                                         # use '*' to fetch all data stored in the Circuit (CTX)
```