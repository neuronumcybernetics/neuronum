<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum Transmitters (TX): A Serverless HTTP alternative</h4>

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

### **About Neuronum Transmitters (TX)**
Neuronum Transmitters (TX) is a serverless HTTP alternative to send data from a client (Neuronum Cell) to a Neuronum Node, requesting a specific resource or action.


### **Comparison: HTTP vs. Neuronum Transmitters (TX)**
| Protocol         | Encryption         | Response Time    | Payload Format     | Schema Validation           | Transport Layer  | Auth & Session Handling       | Routing Model                    |
|------------------|--------------------|------------------|--------------------|-----------------------------|------------------|-------------------------------|----------------------------------|
| **HTTP**         | HTTPS (TLS)        | 100–2000 ms      | Optional body      | Backend-defined (custom)    | TCP              | Manual via cookies/tokens     | Domain-based routing             |
| **TX (Neuronum)**| Built-in Encryption| 1000–3000 ms     | JSON key–value     | Native schema engine        | HTTPS-based      | Built-in authentication logic | Serverless (send to data stream) |

------------------

### **Activate a Neuronum Transmitter (TX)**
#### **Web-based**
1. [Visit Neuronum](https://neuronum.net)
2. [Connect your Cell](https://neuronum.net/connect)
3. [Explore Transmitters](https://neuronum.net/explore)
4. Activate Transmitters

#### **Code-based**
```python
import asyncio
import neuronum

cell = neuronum.Cell(                                   # set Cell connection
    host="host",                                        # Cell host
    password="password",                                # Cell password
    network="neuronum.net",                             # Cell network -> neuronum.net
    synapse="synapse"                                   # Cell synapse
)

async def main():
                                                            
    TX = "id::tx"                                       # select the Transmitter TX
    data = {"say": "hello"}
    tx_response = await cell.activate_tx(TX, data)      # activate TX - > get response back
    print(tx_response)                                  # print tx response
                                      
asyncio.run(main())
```

#### **CLI-based**
```sh
neuronum activate --tx id::tx say:hello
```

