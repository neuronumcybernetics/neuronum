import subprocess
import os
import neuronum
import platform
import glob
import asyncio
import aiohttp
import click
import questionary
from pathlib import Path
import requests
import psutil
from datetime import datetime
import sys


@click.group()
def cli():
    """Neuronum CLI Tool"""


@click.command()
def create_cell():
    cell_type = questionary.select(
        "Choose Cell type:",
        choices=["business", "community"]
    ).ask()

    network = questionary.select(
        "Choose Network:",
        choices=["neuronum.net"]
    ).ask()

    if cell_type == "business":
        click.echo("Visit https://neuronum.net/createcell to create your Neuronum Business Cell")

    if cell_type == "community":

        email = click.prompt("Enter email")
        password = click.prompt("Enter password", hide_input=True)
        repeat_password = click.prompt("Repeat password", hide_input=True)

        if password != repeat_password:
            click.echo("Passwords do not match!")
            return

        url = f"https://{network}/api/create_cell/{cell_type}"

        create_cell = {"email": email, "password": password}

        try:
            response = requests.post(url, json=create_cell)
            response.raise_for_status()
            status = response.json()["status"]

        except requests.exceptions.RequestException as e:
            click.echo(f"Error sending request: {e}")
            return
        
        if status == True:
            host = response.json()["host"]
            cellkey = click.prompt(f"Please verify your email address with the Cell Key send to {email}")

            url = f"https://{network}/api/verify_email"

            verify_email = {"host": host, "email": email, "cellkey": cellkey}

            try:
                response = requests.post(url, json=verify_email)
                response.raise_for_status()
                status = response.json()["status"]

            except requests.exceptions.RequestException as e:
                click.echo(f"Error sending request: {e}")
                return
        
            if status == True:
                synapse = response.json()["synapse"]
                credentials_folder_path = Path.home() / ".neuronum"
                credentials_folder_path.mkdir(parents=True, exist_ok=True)

                env_path = credentials_folder_path / ".env"
                env_path.write_text(f"HOST={host}\nPASSWORD={password}\nNETWORK={network}\nSYNAPSE={synapse}\n")

                click.echo(f"Welcome to Neuronum! Community Cell '{host}' created and connected!")

        if status == False:
            click.echo(f"Error:'{email}' already assigned!")


@click.command()
def connect_cell():
    email = click.prompt("Enter your Email")
    password = click.prompt("Enter password", hide_input=True)

    network = questionary.select(
        "Choose Network:",
        choices=["neuronum.net"]
    ).ask()

    url = f"https://{network}/api/connect_cell"
    payload = {"email": email, "password": password}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        status = response.json()["status"]
        host = response.json()["host"]
    except requests.exceptions.RequestException as e:
        click.echo(f"Error connecting: {e}")
        return
    
    if status == True:
        cellkey = click.prompt(f"Please verify your email address with the Cell Key send to {email}")
        url = f"https://{network}/api/verify_email"
        verify_email = {"host": host, "email": email, "cellkey": cellkey}

        try:
            response = requests.post(url, json=verify_email)
            response.raise_for_status()
            status = response.json()["status"]
            synapse = response.json()["synapse"]

        except requests.exceptions.RequestException as e:
            click.echo(f"Error sending request: {e}")
            return

        if status == True:
            credentials_folder_path = Path.home() / ".neuronum"
            credentials_folder_path.mkdir(parents=True, exist_ok=True)

            env_path = credentials_folder_path / f".env"
            env_path.write_text(f"HOST={host}\nPASSWORD={password}\nNETWORK={network}\nSYNAPSE={synapse}\n")

            click.echo(f"Cell '{host}' connected!")
    else:
        click.echo(f"Connection failed!")


@click.command()
def view_cell():
    credentials_folder_path = Path.home() / ".neuronum"
    env_path = credentials_folder_path / ".env"

    env_data = {}

    try:
        with open(env_path, "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        host = env_data.get("HOST", "")

    except FileNotFoundError:
        click.echo("Error: No credentials found. Please connect to a cell first.")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return

    if host:
        click.echo(f"Connected Cell: '{host}'")
    else:
        click.echo("No active cell connection found.")


@click.command()
def disconnect_cell():
    credentials_folder_path = Path.home() / ".neuronum"
    env_path = credentials_folder_path / ".env"

    env_data = {}

    try:
        with open(env_path, "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        host = env_data.get("HOST", "")

    except FileNotFoundError:
        click.echo("Error: .env with credentials not found")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return

    if env_path.exists():
        if click.confirm(f"Are you sure you want to disconnect Cell '{host}'?", default=True):
            os.remove(env_path)
            click.echo(f"'{host}' disconnected!")
        else:
            click.echo("Disconnect canceled.")
    else:
        click.echo(f"No Neuronum Cell connected!")


@click.command()
def delete_cell():
    credentials_folder_path = Path.home() / ".neuronum"
    env_path = credentials_folder_path / ".env"

    env_data = {}

    try:
        with open(env_path, "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        host = env_data.get("HOST", "")
        password = env_data.get("PASSWORD", "")
        network = env_data.get("NETWORK", "")
        synapse = env_data.get("SYNAPSE", "")

    except FileNotFoundError:
        click.echo("Error: No cell connected. Connect Cell first to delete")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return

    confirm = click.confirm(f" Are you sure you want to delete '{host}'?", default=True)
    if not confirm:
        click.echo("Deletion canceled.")
        return

    url = f"https://{network}/api/delete_cell"
    payload = {"host": host, "password": password, "synapse": synapse}

    try:
        response = requests.delete(url, json=payload)
        response.raise_for_status()
        status = response.json()["status"]
    except requests.exceptions.RequestException as e:
        click.echo(f"Error deleting cell: {e}")
        return
    
    if status == True:
        env_path = credentials_folder_path / f"{host}.env"
        if env_path.exists():
            os.remove(env_path)
            click.echo("Credentials deleted successfully!")
        click.echo(f"Neuronum Cell '{host}' has been deleted!")
    else: 
        click.echo(f"Neuronum Cell '{host}' deletion failed!")


@click.command()
def init_node():
    descr = click.prompt("Node description: Type up to 25 characters").strip()
    if descr and len(descr) > 25:
        click.echo("Description too long. Max 25 characters allowed.")
        return
    asyncio.run(async_init_node(descr))

async def async_init_node(descr):
    credentials_folder_path = Path.home() / ".neuronum"
    env_path = credentials_folder_path / ".env"

    env_data = {}  

    try:
        with open(env_path, "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        host = env_data.get("HOST", "")
        password = env_data.get("PASSWORD", "")
        network = env_data.get("NETWORK", "")
        synapse = env_data.get("SYNAPSE", "")

        cell = neuronum.Cell(
        host=host,         
        password=password,                         
        network=network,                        
        synapse=synapse
        )

    except FileNotFoundError:
        click.echo("No cell connected. Connect your cell with command neuronum connect-cell")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return

    url = f"https://{network}/api/init_node"
    node = {
        "host": host, 
        "password": password, 
        "synapse": synapse, 
        "descr": descr,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=node) as response:
                response.raise_for_status()
                data = await response.json()
                nodeID = data["nodeID"]
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")
            return

    node_filename = descr + "_" + nodeID.replace("::node", "")
    project_path = Path(node_filename)
    project_path.mkdir(exist_ok=True)

    env_path = project_path / ".env"
    await asyncio.to_thread(env_path.write_text, f"NODE={nodeID}\nHOST={host}\nPASSWORD={password}\nNETWORK={network}\nSYNAPSE={synapse}\n")

    stx_descr = f"{nodeID} App"                                                  
    partners = ["private"]                                      
    stxID = await cell.create_stx(stx_descr, partners)  

    tx_descr = f"Greet {nodeID}"                                           
    key_values = {                                                          
        "ping": "pong",
    }
    STX = stxID                                                     
    label = "ping:pong"                                                                                                                                                         
    partners = ["private"]                                                   
    txID = await cell.create_tx(tx_descr, key_values, STX, label, partners)

    app_path = project_path / "app.py"
    app_path.write_text(f"""\
import asyncio
import neuronum
import os
import json                        
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader                        

env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('ping.html')    

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

cell = neuronum.Cell(
    host=host,
    password=password,
    network=network,
    synapse=synapse
)

async def main():      
    STX = "{stxID}"                                          
    async for operation in cell.sync(STX):       
        txID = operation.get("txID")
        client = operation.get("operator")   
        ts = operation.get("time")  
        data = operation.get("data") 
        operation_id = operation.get("operationID")                
                            
        if txID == "{txID}":  
        
            def render_html_template(client, ts, data, operation_id, terms_url, privacy_url, last_update):
                return template.render(client=client, ts=ts, data=data, operation_id=operation_id, terms_url=terms_url, privacy_url=privacy_url, last_update=last_update)

            html_content = render_html_template(client, ts, data, operation_id, terms_url, privacy_url, last_update)        

            data = {{
                "json": f"{{operation_id}} - Reply from {nodeID}: Pinged by {{client}} at {{ts}} with data: {{data}}",
                "html": html_content
            }}

            await cell.notify(f"{{client}}", "{nodeID} Ping","Pinged successfully")

            await cell.tx_response(txID, client, data)

asyncio.run(main())
""")
    
    html_path = project_path / "ping.html"
    html_content = f"""\
<!DOCTYPE html>
<html>
  <head>
    <style>
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: #121212;
        color: #e0e0e0;
        margin: 0;
        padding: 0;
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
      }}

      .container {{
        background-color: #1e1e1e;
        border-radius: 12px;
        padding: 40px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        width: 100%;
        max-width: 500px;
        text-align: center;
        box-sizing: border-box;
      }}

      .logo {{
        width: 80px;
        margin-bottom: 25px;
        filter: drop-shadow(0 0 5px rgba(255, 255, 255, 0.1));
      }}

      h1 {{
        font-size: 1.5em;
        font-weight: 600;
        margin-bottom: 5px;
        color: #f5f5f5;
      }}

      .subtitle {{
        font-size: 0.9em;
        color: #a0a0a0;
        margin-bottom: 30px;
      }}

      .data-row {{
        background-color: #2a2a2a;
        padding: 12px 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }}

      .data-label {{
        font-weight: 400;
        color: #a0a0a0;
        margin: 0;
      }}

      .data-value {{
        font-weight: 500;
        color: #e0e0e0;
        margin: 0;
      }}

      .data-value.truncated {{
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 60%;
      }}

      .data-value.client {{
          color: #8cafff;
      }}
      .data-value.timestamp {{
          color: #a1e8a1;
      }}
      .data-value.operation-id {{
          color: #f7a2a2;
      }}
      .api-button {{
        background: #01c07d 100%;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 16px;
        font-weight: bold;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        cursor: pointer;
        margin-top: 10px;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <img class="logo" src="https://neuronum.net/static/logo.png" alt="Neuronum Logo">
      
      <h1>Reply from {nodeID}</h1>
      <p class="subtitle">Pinged successfully.</p>
      
      <div class="data-row">
        <p class="data-label">Client</p>
        <p class="data-value client">{{{{client}}}}</p>
      </div>
      
      <div class="data-row">
        <p class="data-label">Timestamp</p>
        <p class="data-value timestamp">{{{{ts}}}}</p>
      </div>
      
      <div class="data-row">
        <p class="data-label">Data</p>
        <p class="data-value">{{{{data}}}}</p>
      </div>
      
      <div class="data-row">
        <p class="data-label">Operation ID</p>
        <p class="data-value operation-id truncated">{{{{operation_id}}}}</p>
      </div>

      <button id="send-request-btn" class="api-button">Ping again</button>
    </div>

    <script>
    document.getElementById('send-request-btn').addEventListener('click', () => {{
        const apiEndpoint = 'https://neuronum.net/api/activate/{txID}';

        const dataToSend = {{
            "data": {{"ping": "node"}},
            "cell": {{
                "host": CLIENT_CELL,
                "session": CLIENT_SESSION, 
            }}
        }};

        fetch(apiEndpoint, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }},
            body: JSON.stringify(dataToSend)
        }})
        .then(response => {{
            if (!response.ok) {{
                throw new Error(`HTTP error! status: ${{response.status}}`);
            }}
            return response.json();
        }})
        .then(data => {{
            if (data.success && data.response && data.response.html) {{
                document.open();
                document.write(data.response.html);
                document.close();
                console.log('API Response: Page replaced with new HTML.');
            }} else {{
                console.error('API Response does not contain HTML to replace the page:', data);
                alert('API response error: Expected HTML content to replace the page.');
            }}
        }})
        .catch(error => {{
            console.error('API request failed:', error);
            alert('API request failed. See the console for details.');
        }});
    }});
    </script>

    <div id="legal-banner" style="border-radius: 10px;  margin: 15px; position: fixed; bottom: 0; left: 0; right: 0; background-color: #2a2a2a; color: #e0e0e0; padding: 16px; text-align: center; font-size: 14px; z-index: 9999; box-shadow: 0 -2px 10px rgba(0,0,0,0.5);">
      By continuing, you agree to our 
      Terms (<span style="color: #8cafff;">{{{{terms_url}}}}</span>) & 
      Privacy Policy (<span style="color: #8cafff;">{{{{privacy_url}}}}</span>)
      <br>
      <button id="accept-legal" style="margin-top: 15px; margin-bottom: 15px; background: #01c07d; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer;">Accept</button>
      <br>
      Last Update: {{{{last_update}}}}
    </div>

    <script>
      const banner = document.getElementById('legal-banner');
      const acceptBtn = document.getElementById('accept-legal');
      acceptBtn.addEventListener('click', () => {{
        banner.remove();
      }});
    </script>

  </body>
</html>
"""
    html_path.write_text(html_content)
    
    config_path = project_path / "config.json"
    await asyncio.to_thread(
    config_path.write_text,
f"""{{
    "app_metadata": {{
        "name": "{descr}",
        "version": "1.0.0",
        "author": "{host}"
    }},
    "data_gateways": [
        {{
        "type": "transmitter",
        "id": "{txID}",
        "info": "Ping Your Node"
        }}
    ],
    "legals": {{
        "terms": "https://url_to_your/terms",
        "privacy_policy": "https://url_to_your/privacy_policy",
        "last_update" : "DD/MM/YYYY"
    }}
}}"""
)

    nodemd_path = project_path / "NODE.md"
    await asyncio.to_thread(nodemd_path.write_text, f"""### NODE.md of {nodeID}

Welcome to your Node's documentation! This guide provides several ways for users to interact with your application.

***

### 💻 Using the CLI

To ping this Node via the command-line interface, use the following command:

`neuronum activate --tx {txID} 'ping:node'`

***

### 🐍 With Python

For programmatic access, use the following Python code snippet. This script utilizes the `neuronum` library to activate the transaction and receive a response.

```python
import asyncio
import neuronum

# Set up Cell connection parameters
cell = neuronum.Cell(
    host="host",                                  # Cell host
    password="password",                          # Cell password
    network="neuronum.net",                       # Cell network
    synapse="synapse"                             # Cell synapse
)

async def main():
    # Define the transaction ID and data payload
    TX = "{txID}"
    data = {{"ping": "node"}}
    
    # Activate the transaction and get the response
    tx_response = await cell.activate_tx(TX, data)
    
    # Print the response from the Node
    print(tx_response)
                                      
# Run the main asynchronous function
if __name__ == "__main__":
    asyncio.run(main())
```

🤖 Via Cellai (Android App - Currently in Testing)
Download the app from the Google Play Store.
Send the command "Ping Node" to Cellai
""")
        
    click.echo(f"Neuronum Node '{nodeID}' initialized!")


@click.command()
@click.option('--d', is_flag=True, help="Start node in detached mode")
def start_node(d):
    update_node()
    pid_file = Path.cwd() / "status.txt"
    system_name = platform.system()
    active_pids = []

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                pids = [int(line.strip()) for line in f if line.strip().isdigit()]
            for pid in pids:
                if system_name == "Windows":
                    if psutil.pid_exists(pid):
                        active_pids.append(pid)
                else:
                    try:
                        os.kill(pid, 0)
                        active_pids.append(pid)
                    except OSError:
                        continue
        except Exception as e:
            click.echo(f"Failed to read PID file: {e}")

    if active_pids:
        click.echo(f"Node is already running. Active PIDs: {', '.join(map(str, active_pids))}")
        return

    click.echo("Starting Node...")

    project_path = Path.cwd()
    script_files = glob.glob("stream.py") + glob.glob("app.py")
    processes = []

    for script in script_files:
        script_path = project_path / script
        if script_path.exists():

            if d:
                process = subprocess.Popen(
                    ["nohup", sys.executable, str(script_path), "&"] if system_name != "Windows"
                    else ["pythonw", str(script_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            else:
                process = subprocess.Popen(
                    [sys.executable, str(script_path)]
                )

            processes.append(process.pid)

    if not processes:
        click.echo("Error: No valid node script found. Ensure the node is set up correctly.")
        return

    with open(pid_file, "w") as f:
        f.write(f"Started at: {start_time}\n")
        f.write("\n".join(map(str, processes)))

    click.echo(f"Node started successfully with PIDs: {', '.join(map(str, processes))}")


@click.command()
def check_node():
    click.echo("Checking Node status...")

    env_data = {}
    try:
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    env_data[key] = value
        nodeID = env_data.get("NODE", "")
    except FileNotFoundError:
        click.echo("Error: .env with credentials not found")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return

    pid_file = Path.cwd() / "status.txt"

    if not pid_file.exists():
        click.echo(f"Node {nodeID} is not running. Status file missing.")
        return

    try:
        with open(pid_file, "r") as f:
            lines = f.readlines()
            timestamp_line = next((line for line in lines if line.startswith("Started at:")), None)
            pids = [int(line.strip()) for line in lines if line.strip().isdigit()]

        if timestamp_line:
            click.echo(timestamp_line.strip())
            start_time = datetime.strptime(timestamp_line.split(":", 1)[1].strip(), "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            uptime = now - start_time
            click.echo(f"Uptime: {str(uptime).split('.')[0]}")
    except Exception as e:
        click.echo(f"Failed to read PID file: {e}")
        return

    system_name = platform.system()
    running_pids = []

    for pid in pids:
        if system_name == "Windows":
            if psutil.pid_exists(pid):
                running_pids.append(pid)
        else:
            try:
                os.kill(pid, 0)
                running_pids.append(pid)
            except OSError:
                continue

    if running_pids:
        click.echo(f"Node {nodeID} is running. Active PIDs: {', '.join(map(str, running_pids))}")
    else:
        click.echo(f"Node {nodeID} is not running.")

    
@click.command()
@click.option('--d', is_flag=True, help="Restart node in detached mode")
def restart_node(d):
    update_node()
    pid_file = Path.cwd() / "status.txt"
    system_name = platform.system()

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    env_data = {}
    try:
        with open(".env", "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        nodeID = env_data.get("NODE", "")

    except FileNotFoundError:
        print("Error: .env with credentials not found")
        return
    except Exception as e:
        print(f"Error reading .env file: {e}")
        return

    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                pids = [int(line.strip()) for line in f if line.strip().isdigit()]

            for pid in pids:
                if system_name == "Windows":
                    if psutil.pid_exists(pid):
                        proc = psutil.Process(pid)
                        proc.terminate()
                else:
                    try:
                        os.kill(pid, 15)
                    except OSError:
                        continue

            pid_file.unlink()

            click.echo(f"Terminated existing {nodeID} processes: {', '.join(map(str, pids))}")

        except Exception as e:
            click.echo(f"Failed to terminate processes: {e}")
            return
    else:
        click.echo(f"Node {nodeID} is not running")

    click.echo(f"Starting Node {nodeID}...")
    project_path = Path.cwd()
    script_files = glob.glob("stream.py") + glob.glob("app.py")
    processes = []

    for script in script_files:
        script_path = project_path / script
        if script_path.exists():
            if d:
                process = subprocess.Popen(
                    ["nohup", sys.executable, str(script_path), "&"] if system_name != "Windows"
                    else ["pythonw", str(script_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            else:
                process = subprocess.Popen(
                    [sys.executable, str(script_path)]
                )

            processes.append(process.pid)

    if not processes:
        click.echo("Error: No valid node script found.")
        return

    with open(pid_file, "w") as f:
        f.write(f"Started at: {start_time}\n")
        f.write("\n".join(map(str, processes)))

    click.echo(f"Node {nodeID} started with new PIDs: {', '.join(map(str, processes))}")


@click.command()
def stop_node():
    asyncio.run(async_stop_node())

async def async_stop_node():
    click.echo("Stopping Node...")

    node_pid_path = Path("status.txt")

    env_data = {}
    try:
        with open(".env", "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        nodeID = env_data.get("NODE", "")

    except FileNotFoundError:
        print("Error: .env with credentials not found")
        return
    except Exception as e:
        print(f"Error reading .env file: {e}")
        return

    try:
        with open("status.txt", "r") as f:
            pids = [int(line.strip()) for line in f if line.strip().isdigit()]

        system_name = platform.system()

        for pid in pids:
            try:
                if system_name == "Windows":
                    await asyncio.to_thread(subprocess.run, ["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    await asyncio.to_thread(os.kill, pid, 9)
            except ProcessLookupError:
                click.echo(f"Warning: Process {pid} already stopped or does not exist.")

        await asyncio.to_thread(os.remove, node_pid_path)
        click.echo(f"Node {nodeID} stopped successfully!")

    except FileNotFoundError:
        click.echo("Error: No active node process found.")
    except subprocess.CalledProcessError:
        click.echo("Error: Unable to stop some node processes.")


def update_node():
    click.echo("Update your Node")
    env_data = {}

    try:
        with open(".env", "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        host = env_data.get("HOST", "")

    except FileNotFoundError:
        click.echo("Error: .env with credentials not found")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return
    
    if host.startswith("CMTY_"):
        node_type = questionary.select(
            "Community Cells can only create private Nodes",
            choices=["private"]
        ).ask()
    else:
        node_type = questionary.select(
            "Who can view your Node?:",
            choices=["public", "private", "partners"]
        ).ask()
    partners = "None"
    if node_type == "partners":
        prompt_msg = (
            "Enter the list of partners who can view this Node.\n"
            "Format: partner::cell, partner::cell, partner::cell\n"
            "Press Enter to leave the list unchanged"
        )
        partners = click.prompt(
            prompt_msg,
            default="None",
            show_default=False
        ).strip()
    descr = click.prompt(
        "Update Node description: Type up to 25 characters, or press Enter to leave it unchanged",
        default="None",
        show_default=False
    ).strip()
    if descr and len(descr) > 25:
        click.echo("Description too long. Max 25 characters allowed.")
        return
    asyncio.run(async_update_node(node_type, descr, partners))

async def async_update_node(node_type: str, descr: str, partners:str) -> None:
    env_data = {}

    try:
        with open(".env", "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        nodeID = env_data.get("NODE", "")
        host = env_data.get("HOST", "")
        password = env_data.get("PASSWORD", "")
        network = env_data.get("NETWORK", "")
        synapse = env_data.get("SYNAPSE", "")

    except FileNotFoundError:
        click.echo("Error: .env with credentials not found")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return

    try:
        with open("NODE.md", "r") as f:
            nodemd_file = f.read()

        with open("config.json", "r") as f:
            config_file = f.read()

    except FileNotFoundError:
        click.echo("Error: NODE.md file not found")
        return
    except Exception as e:
        click.echo(f"Error reading NODE.md file: {e}")
        return
    
    if node_type == "partners":
        node_type = partners

    url = f"https://{network}/api/update_node"
    node = {
        "nodeID": nodeID,
        "host": host,
        "password": password,
        "synapse": synapse,
        "node_type": node_type,
        "nodemd_file": nodemd_file,
        "config_file": config_file,
        "descr": descr,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=node) as response:
                response.raise_for_status()
                data = await response.json()
                nodeID = data["nodeID"]
                node_url = data["node_url"]
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")
            return

    if node_type == "public":
        click.echo(f"Neuronum Node '{nodeID}' updated! Visit: {node_url}")
    else:
        click.echo(f"Neuronum Node '{nodeID}' updated!")


@click.command()
def delete_node():
    asyncio.run(async_delete_node())

async def async_delete_node():
    env_data = {}

    try:
        with open(".env", "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value

        nodeID = env_data.get("NODE", "")
        host = env_data.get("HOST", "")
        password = env_data.get("PASSWORD", "")
        network = env_data.get("NETWORK", "")
        synapse = env_data.get("SYNAPSE", "")

    except FileNotFoundError:
        click.echo("Error: .env with credentials not found")
        return
    except Exception as e:
        click.echo(f"Error reading .env file: {e}")
        return

    url = f"https://{network}/api/delete_node"
    node_payload = {
        "nodeID": nodeID,
        "host": host,
        "password": password,
        "synapse": synapse
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=node_payload) as response:
                response.raise_for_status()
                data = await response.json()
                nodeID = data["nodeID"]
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")
            return

    click.echo(f"Neuronum Node '{nodeID}' deleted!")


@click.command()
@click.option('--tx', required=True, help="Transmitter ID")
@click.argument('kvpairs', nargs=-1)
def activate(tx, kvpairs):
    try:
        data = dict(pair.split(':', 1) for pair in kvpairs)
    except ValueError:
        click.echo("Invalid input. Use key:value pairs.")
        return

    asyncio.run(async_activate(tx, data))

async def async_activate(tx, data):
    credentials_folder_path = Path.home() / ".neuronum"
    env_path = credentials_folder_path / ".env"
    env_data = {}

    try:
        with open(env_path, "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value
    except FileNotFoundError:
        click.echo("No cell connected. Try: neuronum connect-cell")
        return
    except Exception as e:
        click.echo(f"Error reading .env: {e}")
        return

    cell = neuronum.Cell(
        host=env_data.get("HOST", ""),
        password=env_data.get("PASSWORD", ""),
        network=env_data.get("NETWORK", ""),
        synapse=env_data.get("SYNAPSE", "")
    )

    tx_response = await cell.activate_tx(tx, data)
    click.echo(tx_response)


@click.command()
@click.option('--ctx', required=True, help="Circuit ID")
@click.argument('label', nargs=-1)
def load(ctx, label):
    if len(label) > 1 and all(Path(x).exists() for x in label):
        label = "*"
    else:
        label = " ".join(label)

    asyncio.run(async_load(ctx, label))


async def async_load(ctx, label):
    credentials_folder_path = Path.home() / ".neuronum"
    env_path = credentials_folder_path / ".env"
    env_data = {}

    try:
        with open(env_path, "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value
    except FileNotFoundError:
        click.echo("No cell connected. Try: neuronum connect-cell")
        return
    except Exception as e:
        click.echo(f"Error reading .env: {e}")
        return

    cell = neuronum.Cell(
        host=env_data.get("HOST", ""),
        password=env_data.get("PASSWORD", ""),
        network=env_data.get("NETWORK", ""),
        synapse=env_data.get("SYNAPSE", "")
    )

    data = await cell.load(label, ctx)
    click.echo(data)


@click.command()
@click.option('--stx', default=None, help="Stream ID (optional)")
def sync(stx):
    asyncio.run(async_sync(stx))


async def async_sync(stx):
    credentials_folder_path = Path.home() / ".neuronum"
    env_path = credentials_folder_path / ".env"
    env_data = {}

    try:
        with open(env_path, "r") as f:
            for line in f:
                key, value = line.strip().split("=")
                env_data[key] = value
    except FileNotFoundError:
        click.echo("No cell connected. Try: neuronum connect-cell")
        return
    except Exception as e:
        click.echo(f"Error reading .env: {e}")
        return

    cell = neuronum.Cell(
        host=env_data.get("HOST", ""),
        password=env_data.get("PASSWORD", ""),
        network=env_data.get("NETWORK", ""),
        synapse=env_data.get("SYNAPSE", "")
    )

    if stx:
        print(f"Listening to Stream '{stx}'! Close connection with CTRL+C")
    else:
        print(f"Listening to '{cell.host}' private Stream! Close connection with CTRL+C")
    async for operation in cell.sync() if stx is None else cell.sync(stx):
        label = operation.get("label")                            
        data = operation.get("data")
        ts = operation.get("time")
        stxID = operation.get("stxID")
        operator = operation.get("operator")
        txID = operation.get("txID")
        print(label, data, ts, operator, txID, stxID)


cli.add_command(create_cell)
cli.add_command(connect_cell)
cli.add_command(view_cell)
cli.add_command(disconnect_cell)
cli.add_command(delete_cell)
cli.add_command(init_node)
cli.add_command(start_node)
cli.add_command(restart_node)
cli.add_command(stop_node)
cli.add_command(check_node)
cli.add_command(delete_node)
cli.add_command(activate)
cli.add_command(load)
cli.add_command(sync)


if __name__ == "__main__":
    cli()
