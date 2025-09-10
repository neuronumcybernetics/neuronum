### **virtual_traffic_light**
Set up a Neuronum Node (App) streaming real-time data about its light state

## 1. **Start with initializing your Node (App)**
```sh
neuronum init-node --blank
```

This command will prompt you for a description (e.g. vTrafficLight) and will create a new directory named "vTrafficLight_<your_node_id>" with the following files

.env: Stores your Node's credentials for connecting to the network.<br>
```env
NODE=id::node
HOST=id::cell
PASSWORD=cell_password
NETWORK=neuronum.net
SYNAPSE=cell_synapse
```

app.py: The main Python script that contains your Node's core logic. Replace the content of app.py with the following script:
```python
import asyncio
import neuronum
import os
from dotenv import load_dotenv
import time
import random

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

durations = {
    "red": lambda: random.randint(10, 20),
    "red-yellow": lambda: 2,
    "green": lambda: random.randint(15, 30),
    "yellow": lambda: 3
}

location = {
    "latitude": 48.3705,
    "longitude": 10.8978
}

STX = "id::stx" #replace with your actual Stream ID (see section 2.)
label = "traffic_light"

async def send_light_status(light_status, duration):
    start_time = time.time()
    while time.time() - start_time < duration:
        data = {
            "light_status": light_status,
            "location": location
        }
        await cell.stream(label, data, STX)
        await asyncio.sleep(0.3)

async def main():
    while True:
        await send_light_status("red", durations["red"]())

        await send_light_status("red-yellow", durations["red-yellow"]())

        await send_light_status("green", durations["green"]())

        await send_light_status("yellow", durations["yellow"]())

asyncio.run(main())
```


**Make sure to install the required dependencies before running your Node:**
```sh
pip install time python-dotenv neuronum random
```

NODE.md: Public documentation that provides instructions for interacting with your Node. You can ignore this file unless you want to publish your App

config.json: A configuration file that stores metadata about your app and enables Cellai to interact with your Node's data gateways. Replace the code with:

```json
{
    "app_metadata": {
        "name": "vTrafficLight",
        "version": "1.0.0",
        "author": "id::cell"
    },
    "data_gateways": [
        {
        "type": "stream",
        "id": "id::stx",
        "info": "Get Traffic Light State"
        }
    ],
    "legals": {
        "terms": "https://url_to_your/terms",
        "privacy_policy": "https://url_to_your/privacy_policy",
        "last_update" : "DD/MM/YYYY"
    }
}
```

**make sure to replace "id::tx" with your actual Transmitter ID (see section 2.)**

ping.html: A static HTML file used to render web-based responses. You can delete this file, as we're building a headless application

## 2. **Create Data Gateways**
You need to create 1 data gateways. A Stream (STX) that allows your Node to stream real-time data

1. [Connect to Neuronum](https://neuronum.net/connect)
2. [Create A Stream](https://neuronum.net/createSTX)<br>
Description: Traffic Light State<br>
Partner Cell List: private<br>
-> publish STX

## 3. **Run your Node**
### **Change to Node folder**
```sh
cd vTrafficLight_<your_node_id>
```

### **Simply start your App with**
```sh
neuronum start-node
```

or

```sh
neuronum start-node --d   # start your Node in "detached" mode
```

These commands will prompt you to choose who can view and interact with your Node.  
(Note: Community Cells can only select `private`)
```sh
Update your Node
? Who can view your Node?: (Use arrow keys)
 » public
   private
   partners
```

Next, you’ll be asked if you want to change your Node description, which is currently set to "Test App"
```sh
Update Node description: Type up to 25 characters, or press Enter to leave it unchanged: 
```

After that, the terminal should print something like:
```sh
Neuronum Node 'SW07fDQ4yL4y::node' updated!
Starting Node...
Node started successfully with PIDs: 2104
```

### **Stop your Node using the CLI command**
```sh
neuronum stop-node
```

## 4. **Interact with your Node**
[**car**](https://github.com/neuronumcybernetics/neuronum/tree/main/features/nodes/examples/smart_city/car): Set up a Neuronum Node (App) enabling cars to proccess real time traffic light data

or

**CELLai** is an AI tool for developers to test and interact with apps built on Neuronum using natural language.
[Launch in your browser](https://cellai.neuronum.net)

**Now available on Google Play**  
*(Supported Locations: Germany, Switzerland & Austria)*  
[Download on Google Play](https://play.google.com/store/apps/details?id=net.neuronum.cellai&utm_source=emea_Med)

Send this Command to Cellai: Get Traffic Light State