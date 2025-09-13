### **cpu_dashboard**
Set up a Neuronum Node (App) that provides a real-time dashboard showing its CPU resources

## 1. **Start with initializing your Node (App)**
```sh
neuronum init-node --blank
```

This command will prompt you for a description (e.g. CPU-Dashboard) and will create a new directory named "CPU-Dashboard_<your_node_id>" with the following files

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
import json
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
import psutil
import time


env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('dashboard.html')

with open('config.json', 'r') as f:
    data = json.load(f)
terms_url = data['legals']['terms']
privacy_url = data['legals']['privacy_policy']
last_update = data['legals']['last_update']

load_dotenv()
host = os.getenv("HOST")
password = os.getenv("PASSWORD")
network = os.getenv("NETWORK")
synapse = os.getenv("SYNAPSE")

sync_stream_id = "id::stx"  # replace with actual Stream ID 2. (see section 2.)

cell = neuronum.Cell(
    host=host,
    password=password,
    network=network,
    synapse=synapse
)

async def stream_data():
    label = "test"
    while True:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)
            uptime = time.time() - psutil.boot_time()

            data = {
                "cpu_percent": cpu_percent,
                "memory_percent": mem.percent,
                "load_average_1m": load_avg[0],
                "load_average_5m": load_avg[1],
                "load_average_15m": load_avg[2],
                "uptime_seconds": int(uptime),
            }

            await cell.stream(label, data, sync_stream_id)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Stream error: {e}")
            await asyncio.sleep(5)


async def sync_operations():
    STX = "id::stx"  # replace with actual Stream ID 1. (see section 2.)
    async for operation in cell.sync(STX):
        txID = operation.get("txID")
        client = operation.get("operator")
        data = operation.get("data")
        label = operation.get("label")

        def render_html_template(sync_stream_id, terms_url, privacy_url, last_update):
            return template.render(sync_stream_id=sync_stream_id, terms_url=terms_url, privacy_url=privacy_url, last_update=last_update)

        if txID == "id::tx":  # replace with actual Transmitter ID (see section 2.)
            html_content = render_html_template(sync_stream_id, terms_url, privacy_url, last_update)

            response_data = {
                "html": html_content
            }

            await cell.tx_response(txID, client, response_data)


async def main():
    await asyncio.gather(
        stream_data(),
        sync_operations()
    )
asyncio.run(main())
```


**Make sure to install the required dependencies before running your Node:**
```sh
pip install psutil jinja2 python-dotenv neuronum
```

NODE.md: Public documentation that provides instructions for interacting with your Node. You can ignore this file unless you want to publish your App

config.json: A configuration file that stores metadata about your app and enables Cellai to interact with your Node's data gateways. Replace the code with:

```json
{
    "app_metadata": {
        "name": "CPU-Dashboard",
        "version": "1.0.0",
        "author": "id::cell"
    },
    "data_gateways": [
        {
        "type": "transmitter",
        "id": "id::tx",
        "info": "Open CPU Stream"
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

dashboard.html: A static HTML file used to render web-based responses. 
```html
<!DOCTYPE html>
<html>
  <head>
    <style>
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: #121212;
        color: #e0e0e0;
        margin: 0;
        padding: 0;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
      }

      .container {
        background-color: #1e1e1e;
        border-radius: 12px;
        padding: 40px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        width: 100%;
        max-width: 600px;
        text-align: center;
        box-sizing: border-box;
      }

      .logo {
        width: 80px;
        margin-bottom: 25px;
        filter: drop-shadow(0 0 5px rgba(255, 255, 255, 0.1));
      }

      h1 {
        font-size: 1.5em;
        font-weight: 600;
        margin-bottom: 5px;
        color: #f5f5f5;
      }

      .subtitle {
        font-size: 0.9em;
        color: #a0a0a0;
        margin-bottom: 20px;
      }

      #message-log {
        background-color: #2a2a2a;
        border-radius: 8px;
        padding: 15px;
        max-height: 300px;
        overflow-y: auto;
        text-align: left;
        font-family: monospace;
        font-size: 13px;
        color: #c5f3ff;
        margin-bottom: 20px;
      }

      .log-entry {
        margin-bottom: 10px;
        word-break: break-word;
      }

      .api-button {
        background: #01c07d 100%;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 16px;
        font-weight: bold;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        cursor: pointer;
      }
    </style>
  </head>

  <body>
    <div class="container">
      <img class="logo" src="https://neuronum.net/static/logo.png" alt="Neuronum Logo">
      <h1>Stream {{sync_stream_id}}</h1>
      <p class="subtitle" id="status">Stream connected.</p>

      <div id="metrics">
        <p><strong>CPU:</strong> <span id="cpu">--</span>%</p>
        <p><strong>Memory:</strong> <span id="memory">--</span>%</p>
        <p><strong>Load Avg:</strong>
          <span id="load1">--</span>,
          <span id="load5">--</span>,
          <span id="load15">--</span>
        </p>
        <p><strong>Machine Uptime:</strong> <span id="uptime">--</span></p>
      </div>

      <div id="message-log"></div>

      <button id="ping-button" class="api-button">Disconnect WebSocket</button>
    </div>

    <script>
      let socket = null;
      let connected = false;

      const btn = document.getElementById("ping-button");
      const statusText = document.getElementById("status");
      const log = document.getElementById("message-log");

      function appendToLog(message) {
        const div = document.createElement("div");
        div.classList.add("log-entry");
        div.textContent = message;
        log.prepend(div);
      }

      function formatUptime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        return `${h}h ${m}m ${s}s`;
      }

      function updateMetrics(metrics) {
        if ("cpu_percent" in metrics) {
          document.getElementById("cpu").textContent = metrics.cpu_percent.toFixed(1);
        }
        if ("memory_percent" in metrics) {
          document.getElementById("memory").textContent = metrics.memory_percent.toFixed(1);
        }
        if ("load_average_1m" in metrics) {
          document.getElementById("load1").textContent = metrics.load_average_1m.toFixed(2);
          document.getElementById("load5").textContent = metrics.load_average_5m.toFixed(2);
          document.getElementById("load15").textContent = metrics.load_average_15m.toFixed(2);
        }
        if ("uptime_seconds" in metrics) {
          document.getElementById("uptime").textContent = formatUptime(metrics.uptime_seconds);
        }
      }

      function connectWebSocket() {
        socket = new WebSocket(`wss://neuronum.net/ws/{{sync_stream_id}}`);

        socket.onopen = () => {
          connected = true;
          btn.textContent = "Disconnect Stream";
          statusText.textContent = "Stream connected.";

          const payload = {
            session: CLIENT_SESSION,
            cellHost: CLIENT_CELL,
          };
          socket.send(JSON.stringify(payload));
          appendToLog(">> Sent: " + JSON.stringify(payload));
        };

        socket.onmessage = (event) => {
          appendToLog("<< " + event.data);

          try {
            const data = JSON.parse(event.data);
            console.log("Parsed data:", data);

            const metrics = data.data || data.message || data;

            updateMetrics(metrics);
          } catch (e) {
            console.error("Invalid JSON in message:", e);
          }
        };

        socket.onclose = () => {
          connected = false;
          btn.textContent = "Connect Stream";
          statusText.textContent = "Stream disconnected.";
          socket = null;
          appendToLog("!! Stream closed");
        };

        socket.onerror = (err) => {
          console.error("WebSocket error:", err);
          appendToLog("!! WebSocket error");
          socket.close();
        };
      }

      function disconnectWebSocket() {
        if (socket) {
          socket.close();
        }
      }

      btn.addEventListener("click", () => {
        if (!connected) {
          connectWebSocket();
        } else {
          disconnectWebSocket();
        }
      });

      connectWebSocket();
    </script>
  </body>
</html>
```

## 2. **Create Data Gateways**
You need to create 3 data gateways. A Streams (STX) that allows your Node to receive data/requests, a Stream (STX) to stream real-time CPU data and a Transmitter (TX) to match client requests

1. [Connect to Neuronum](https://neuronum.net/connect)
2. [Create 1. Stream](https://neuronum.net/createSTX)<br>
Description: CPU App<br>
Partner Cell List: private<br>
-> publish STX
2. [Create 2. Stream](https://neuronum.net/createSTX)<br>
Description: CPU Stream<br>
Partner Cell List: private<br>
-> publish STX
3. [Create A Transmitter](https://neuronum.net/createTX)<br>
Description: Send Transaction<br>
Key: open / Example: stream<br>
Select Stream: Select your created Stream ID 1.<br>
Label: open:stream<br>
Partner Cell List: private<br>
-> publish TX

## 3. **Run your Node**
### **Change to Node folder**
```sh
cd CPU-Dashboard_<your_node_id>
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

Send this Command to Cellai: Open CPU Stream