### **weather_service**
 Set up a Neuronum Node (App) that provides real-time wheater data

## 1. **Start with initializing your Node (App)**
```sh
neuronum init-node --blank
```

This command will prompt you for a description (e.g. WeatherService) and will create a new directory named "WeatherService_<your_node_id>" with the following files

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
import python_weather                

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
    STX = "id::stx" #replace with your actual Stream ID (see section 2.)                                         
    async for operation in cell.sync(STX):       
        txID = operation.get("txID")
        client = operation.get("operator")   
        data = operation.get("data")                 
                            
        if txID == "id::tx":  #replace with your actual Transmitter ID (see section 2.)

            place = operation.get("data").get("place")

            async with python_weather.Client() as cc:
                weather = await cc.get(place)
                print(weather.temperature, weather.description)

            data = {
                "json": f"The Weather in {place} is {weather. temperature}°. {weather.description}"
            }

            await cell.tx_response(txID, client, data)

asyncio.run(main())
```


**Make sure to install the required dependencies before running your Node:**
```sh
pip install python_weather python-dotenv neuronum
```

NODE.md: Public documentation that provides instructions for interacting with your Node. You can ignore this file unless you want to publish your App

config.json: A configuration file that stores metadata about your app and enables Cellai to interact with your Node's data gateways. Replace the code with:

```json
{
    "app_metadata": {
        "name": "Weather Service",
        "version": "1.0.0",
        "author": "id::cell"
    },
    "data_gateways": [
        {
        "type": "transmitter",
        "id": "id::tx",
        "info": "Whats the Weather. Provide Place"
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
You need to create 2 data gateways. A Stream (STX) that allows your Node to receive data/requests and a Transmitter (TX) to match client requests

1. [Connect to Neuronum](https://neuronum.net/connect)
2. [Create A Stream](https://neuronum.net/createSTX)<br>
Description: Weather Service<br>
Partner Cell List: private<br>
-> publish STX
3. [Create A Transmitter](https://neuronum.net/createTX)<br>
Description: Get Weather Data<br>
Key: place / Example: city<br>
Select Stream: Select your created Stream ID<br>
Label: get:weather<br>
Partner Cell List: private<br>
-> publish TX

## 3. **Run your Node**
### **Change to Node folder**
```sh
cd WeatherService_<your_node_id>
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
**CELLai** is an AI tool for developers to test and interact with apps built on Neuronum using natural language.
[Launch in your browser](https://cellai.neuronum.net)

**Now available on Google Play**  
*(Supported Locations: Germany, Switzerland & Austria)*  
[Download on Google Play](https://play.google.com/store/apps/details?id=net.neuronum.cellai&utm_source=emea_Med)

Send this Command to Cellai: Whats the Weather in Augsburg