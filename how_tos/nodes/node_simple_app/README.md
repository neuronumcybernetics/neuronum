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
                "json": f"Hello {client} from Node",
                "html": f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Transmitter Greeting</title>
  <style>
    body {{
      background: #f0f2f5;
      font-family: 'Segoe UI', sans-serif;
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0;
    }}
    .card {{
      background: #ffffff;
      border-radius: 12px;
      padding: 2rem 3rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
      text-align: center;
      max-width: 400px;
    }}
    .card h1 {{
      margin: 0 0 1rem;
      color: #333;
      font-size: 1.8rem;
    }}
    .card p {{
      font-size: 1.1rem;
      color: #666;
    }}
    .node {{
      font-weight: bold;
      color: #0066cc;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Hello, {client} 👋</h1>
    <p>Greetings from <span class="node">Node</span></p>
  </div>
</body>
</html>
"""
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

Update your Transitter logic:
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
                "json": f"Hello {client} from Node",
                "html": f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Transmitter Greeting</title>
  <style>
    body {{
      background: #f0f2f5;
      font-family: 'Segoe UI', sans-serif;
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0;
    }}
    .card {{
      background: #ffffff;
      border-radius: 12px;
      padding: 2rem 3rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
      text-align: center;
      max-width: 400px;
    }}
    .card h1 {{
      margin: 0 0 1rem;
      color: #333;
      font-size: 1.8rem;
    }}
    .card p {{
      font-size: 1.1rem;
      color: #666;
    }}
    .node {{
      font-weight: bold;
      color: #0066cc;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Hello, {client} 👋</h1>
    <p>Greetings from <span class="node">Node</span></p>
  </div>
</body>
</html>
"""
            }
            await cell.tx_response(txID, client, data)

asyncio.run(main())
```

Replace id::stx and id::tx with your actual Transmitter and Stream IDs. When a client activates your Transmitter from their Node, they’ll receive the JSON response. If executed through a browser, the HTML version will be rendered instead.

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