### **node_simple_app**
Set up a Neuronum Node that can receive requests and send responses back


### **Create a private Stream Gateway**
1. Visit: https://neuronum.net/createSTX
2. Enter a short Stream Description (e.g. Test Stream)
3. Write "private" into the Partner Cell list
4. Click publish STX
5. Copy your Stream ID (id::stx)

### **Create a public Transmitter Gateway**
1. Visit: https://neuronum.net/createTX
2. Enter a short Transmitter Description (e.g. Test Transmitter)
3. Enter a key-value pair (e.g. key = say,; value = hello)
4. Select your new created Stream (STX)
5. Enter a label (e.g. example:label)
6. Write "public" into the Partner Cell list
7. Click publish STX
8. Copy your Transmitter ID (id::tx)

### **Connect your Neuronum Cell**
```sh
neuronum connect-cell
```

### **Initialize your Node with Stream template**
```sh
neuronum init-node --app
```

This command generates a Node template looking like:
```python
import asyncio
import neuronum
import os
from dotenv import load_dotenv

load_dotenv()
host = os.getenv("HOST")
password = os.getenv("PASSWORD")
network = os.getenv("NETWORK")
synapse = os.getenv("SYNAPSE")

cell = neuronum.Cell(
    host=host,
    password=password,
    network=network,
    synapse=synapse
)

async def main():
    STX = "id::stx"                        
    async for operation in cell.sync(STX):       
        txID = operation.get("txID")
        client = operation.get("operator")
                            
        if txID == "id::tx":       
            data = {
                "response": "TX activated!"
            }
            await cell.tx_response(txID, client, data)

        if txID == "id::tx":
            data = {
                "response": "TX activated!"
            }
            await cell.tx_response(txID, client, data)

        if txID == "id::tx":
            data = {
                "response": "TX activated!"
            }
            await cell.tx_response(txID, client, data)

asyncio.run(main())
```

Replace id::stx and id::tx with your actual Transmitter and Stream IDs. Add custom Transmitter logic to your code.

### **Change to Node folder**
```sh
cd node_node_id
```

### **Start your Node**
```sh
neuronum start-node
```

or

```sh
neuronum start-node --d                 # start Node in "detached" mode
```

### **Connect your Node to Neuronum**
```sh
neuronum connect-node
```

### **NODE.md File**
The `NODE.md` file provides guidelines for interacting with your Node's data gateways.  
Add markdown content (follow best practice and format key details in ```json) to structure your instructions, then update your Node with:

```sh
neuronum update-node
```