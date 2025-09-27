import subprocess
import os
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
import json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

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
    os.remove(env_path)
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
                node_id = data["nodeID"]
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")
            return

    node_filename = descr + "_" + node_id.replace("::node", "")
    project_path = Path(node_filename)
    project_path.mkdir(exist_ok=True)

    try:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        pem_public = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        public_key_pem_file = project_path / "public_key.pem"
        with open(public_key_pem_file, "wb") as key_file:
            key_file.write(pem_public) 

        private_key_pem_file = project_path / "private_key.pem"
        with open(private_key_pem_file, "wb") as key_file:
            key_file.write(pem_private) 

        pem_public_str = pem_public.decode('utf-8')
        pem_public_oneline = "".join(pem_public_str.split())

        current_directory = os.getcwd()
        private_key_file = os.path.join(current_directory / project_path, "private_key.pem")
        public_key_file = os.path.join(current_directory / project_path, "public_key.pem")
    except:
        print("Error creating Private/Public Key Pair")
                                                                                                           
    app_path = project_path / "app.py"
    app_path.write_text(f"""\
import asyncio
from neuronum import Node                     
from jinja2 import Environment, FileSystemLoader   
          
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('ping.html')    
                                          
node = Node(
    id="{node_id}",
    private_key="{private_key_file}",
    public_key="{public_key_file}"                   
)
    
async def main():    
                                             
    async for transmitter in node.sync():   
        ts = transmitter.get("time")
        data = transmitter.get("data")
        transmitter_id = transmitter.get("transmitter_id")   
        client = transmitter.get("operator")
        client_public_key = data.get("publicKey")  
        action = data.get("action")

        response_data = {{}}
              
        if action == "ping_node":
        
            html_content = template.render(client=client, ts=ts, data=action, transmitter_id=transmitter_id)

            response_data = {{
                "json": f"{{transmitter_id}} - Reply from {node_id}: Pinged by {{client}} at {{ts}} with action: {{action}}",
                "html": html_content
            }}
            
            await node.tx_response(transmitter_id, response_data, client_public_key)

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
      .data-value.transmitter-id {{
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
      
      <h1>Reply from {node_id}</h1>
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
        <p class="data-label">Transmitter ID</p>
        <p class="data-value transmitter-id truncated">{{{{transmitter_id}}}}</p>
      </div>

      <button id="send-request-btn" class="api-button">Ping again</button>
    </div>

    <script>
        document.getElementById('send-request-btn').addEventListener('click', () => {{
            const messagePayload = {{
                type: 'iframe_request',
                endpoint: 'https://neuronum.net/browser/api/activate_tx/{node_id}',
                data: {{ "action": "ping_node" }},
                nodePublicKey: '{pem_public_oneline}',
            }};

            if (window.parent) {{
                window.parent.postMessage(messagePayload, '*');
            }}
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
    "author": "{host}",
    "audience": "private",
    "logo": "https://neuronum.net/static/logo.png"
  }},
  "data_gateways": [
    {{
      "node_id": "{node_id}",
      "actions": [
        {{
          "action": "ping_node",
          "info": "Ping Node"
        }}
      ]
    }}
  ],
  "legals": {{
    "terms": "https://url_to_your/terms",
    "privacy_policy": "https://url_to_your/privacy_policy"
  }},
  "public_key": "{pem_public_oneline}"
}}"""

)
    click.echo(f"Neuronum Node '{node_id}' initialized!")


@click.command()
@click.option('--d', is_flag=True, help="Start node in detached mode")
def start_node(d):
    update_node_at_start()
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
    script_files = glob.glob("app.py")
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

    try:
        with open('config.json', 'r') as f:
            data = json.load(f)

        nodeID = data['data_gateways'][0]['node_id']

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
    update_node_at_start()
    pid_file = Path.cwd() / "status.txt"
    system_name = platform.system()

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open('config.json', 'r') as f:
            data = json.load(f)

        nodeID = data['data_gateways'][0]['node_id']

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
    script_files = glob.glob("app.py")
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

    try:
        with open('config.json', 'r') as f:
            data = json.load(f)

        nodeID = data['data_gateways'][0]['node_id']

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


@click.command()
def update_node():
    click.echo("Update your Node")
    try:
        env_path = Path.home() / ".neuronum" / ".env"
        env_data = {}
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    env_data[key] = value

        host = env_data.get("HOST", "")

        with open("config.json", "r") as f:
            config_data = json.load(f)

        audience = config_data.get("app_metadata", {}).get("audience", "")
        descr = config_data.get("app_metadata", {}).get("name", "")

        if host.startswith("CMTY_") and audience != "private":
            raise click.ClickException(
                'Community Cells can only create private Nodes. Set audience to "private".'
            )
        if descr and len(descr) > 25:
            raise click.ClickException(
                'Description too long. Max 25 characters allowed.'
            )

    except FileNotFoundError as e:
        click.echo(f"Error: File not found - {e.filename}")
        return
    except click.ClickException as e:
        click.echo(e.format_message())
        return
    except Exception as e:
        click.echo(f"Error reading files: {e}")
        return

    asyncio.run(async_update_node(env_data, config_data, audience, descr))


async def async_update_node(env_data, config_data, audience: str, descr: str):
    try:
        host = env_data.get("HOST", "")
        password = env_data.get("PASSWORD", "")
        network = env_data.get("NETWORK", "")
        synapse = env_data.get("SYNAPSE", "")

        node_id = config_data.get("data_gateways", [{}])[0].get("node_id", "")

        with open("config.json", "r") as f:
            config_file_content = f.read()

    except FileNotFoundError:
        click.echo("Error: config.json or .env not found")
        return
    except Exception as e:
        click.echo(f"Error reading files: {e}")
        return

    url = f"https://{network}/api/update_node"
    node = {
        "nodeID": node_id,
        "host": host,
        "password": password,
        "synapse": synapse,
        "node_type": audience,
        "config_file": config_file_content,
        "descr": descr,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=node) as response:
                response.raise_for_status()
                data = await response.json()
                updated_node_id = data.get("nodeID", node_id)
                click.echo(f"Neuronum Node '{updated_node_id}' updated!")
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")



def update_node_at_start():
    click.echo("Update your Node")
    try:
        env_path = Path.home() / ".neuronum" / ".env"
        env_data = {}
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    env_data[key] = value

        with open("config.json", "r") as f:
            config_data = json.load(f)

        host = env_data.get("HOST", "")
        audience = config_data.get("app_metadata", {}).get("audience", "")
        descr = config_data.get("app_metadata", {}).get("name", "")

        if host.startswith("CMTY_") and audience != "private":
            raise click.ClickException(
                'Community Cells can only start private Nodes. Node starting "privately".'
            )
        if descr and len(descr) > 25:
            raise click.ClickException(
                'Description too long. Max 25 characters allowed.'
            )

        asyncio.run(_async_update_node_at_start(env_data, config_data, audience, descr))

    except FileNotFoundError as e:
        click.echo(f"Error: File not found - {e.filename}")
    except click.ClickException as e:
        click.echo(e.format_message())
    except Exception as e:
        click.echo(f"Unexpected error: {e}")


async def _async_update_node_at_start(env_data, config_data, audience, descr):
    host = env_data.get("HOST", "")
    password = env_data.get("PASSWORD", "")
    network = env_data.get("NETWORK", "")
    synapse = env_data.get("SYNAPSE", "")

    node_id = config_data.get("data_gateways", [{}])[0].get("node_id", "")

    try:
        with open("config.json", "r") as f:
            config_file_content = f.read()
    except Exception as e:
        click.echo(f"Error reading config.json content: {e}")
        return

    url = f"https://{network}/api/update_node"
    node = {
        "nodeID": node_id,
        "host": host,
        "password": password,
        "synapse": synapse,
        "node_type": audience,
        "config_file": config_file_content,
        "descr": descr,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=node) as response:
                response.raise_for_status()
                data = await response.json()
                updated_node_id = data.get("nodeID", node_id)
                click.echo(f"Neuronum Node '{updated_node_id}' updated!")
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")


@click.command()
def delete_node():
    asyncio.run(async_delete_node())

async def async_delete_node():
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

        with open('config.json', 'r') as f:
            data = json.load(f)

        nodeID = data['data_gateways'][0]['node_id']

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


cli.add_command(create_cell)
cli.add_command(connect_cell)
cli.add_command(view_cell)
cli.add_command(disconnect_cell)
cli.add_command(delete_cell)
cli.add_command(init_node)
cli.add_command(update_node)
cli.add_command(start_node)
cli.add_command(restart_node)
cli.add_command(stop_node)
cli.add_command(check_node)
cli.add_command(delete_node)


if __name__ == "__main__":
    cli()
