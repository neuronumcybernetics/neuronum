import subprocess
import os
import neuronum
import json
import platform
import glob
import asyncio
import aiohttp
import click
import questionary
from pathlib import Path
import requests


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
@click.option('--sync', multiple=True, default=None, help="Optional stream IDs for sync.")
@click.option('--stream', multiple=True, default=None, help="Optional stream ID for stream.")
@click.option('--app', is_flag=True, help="Generate a Node with app template")
def init_node(sync, stream, app):
    asyncio.run(async_init_node(sync, stream, app))

async def async_init_node(sync, stream, app):
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
    node_payload = {"host": host, "password": password, "synapse": synapse}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=node_payload) as response:
                response.raise_for_status()
                data = await response.json()
                nodeID = data["nodeID"]
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")
            return

    node_filename = "node_" + nodeID.replace("::node", "")
    project_path = Path(node_filename)
    project_path.mkdir(exist_ok=True)

    cell = neuronum.Cell(
        host=host,         
        password=password,                         
        network=network,                        
        synapse=synapse
    )

    cells = await cell.list_cells()
    tx = await cell.list_tx()
    ctx = await cell.list_ctx()
    stx = await cell.list_stx()
    nodes = await cell.list_nodes()

    await asyncio.to_thread((project_path / "cells.json").write_text, json.dumps(cells, indent=4))
    await asyncio.to_thread((project_path / "transmitters.json").write_text, json.dumps(tx, indent=4))
    await asyncio.to_thread((project_path / "circuits.json").write_text, json.dumps(ctx, indent=4))
    await asyncio.to_thread((project_path / "streams.json").write_text, json.dumps(stx, indent=4))
    await asyncio.to_thread((project_path / "nodes.json").write_text, json.dumps(nodes, indent=4))

    env_path = project_path / ".env"
    await asyncio.to_thread(env_path.write_text, f"NODE={nodeID}\nHOST={host}\nPASSWORD={password}\nNETWORK={network}\nSYNAPSE={synapse}\n")

    gitignore_path = project_path / ".gitignore"
    await asyncio.to_thread(gitignore_path.write_text, ".env\n")

    nodemd_path = project_path / "NODE.md"
    await asyncio.to_thread(nodemd_path.write_text, """### NODE.md: How to interact with this Node

```json
{
    "info": {
        "use_case": "This Node...",
        "github": "https://github.com/user"
    },
    "gateways": [
        {
            "type": "stream",
            "id": "id::stx",
            "link": "https://neuronum.net/stream/id::stx"
        },
        {
            "type": "transmitter",
            "id": "id::tx",
            "link": "https://neuronum.net/tx/id::tx", 
        }
        {
            "type": "circuit",
            "id": "id::ctx",
            "link": "https://neuronum.net/circuit/id::ctx", 
        }
    ],
    "initialization": {
        "command": "neuronum init-node --sync id::stx"
    },
    "requirements": [
        {
            "name": "Python",
            "version": ">= 3.8",
            "link": "https://www.python.org/downloads/"
        },
        {
            "name": "neuronum",
            "version": ">= 5.1.0",
            "link": "https://pypi.org/project/neuronum/"
        }
    ]
}
```"""
)

    stx = sync[0] if sync else (stream[0] if stream else host.replace("::cell", "::stx"))

    if sync:
        for stx in sync:
            sync_path = project_path / f"sync_{stx.replace('::stx', '')}.py"
            sync_path.write_text(f"""\
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
    STX = "{stx}"
    async for operation in cell.sync(STX):
        label = operation.get("label")
        data = operation.get("data")
        ts = operation.get("time")
        stxID = operation.get("stxID")
        operator = operation.get("operator")
        print(label, data, ts, stxID, operator)

asyncio.run(main())
""")


    if stream:
        for stx in stream:
            stream_path = project_path / f"stream_{stx.replace('::stx', '')}.py"
            stream_path.write_text(f"""\
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
    STX = "{stx}"
    label = "your_label"
    
    while True:
        data = {{
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }}
        await cell.stream(label, data, STX)

asyncio.run(main())
""")
    
    if not sync and not stream and not app:
        sync_path = project_path / f"sync_{stx.replace('::stx', '')}.py"
        sync_path.write_text(f"""\
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
    async for operation in cell.sync():
        message = operation.get("data").get("message")
        print(message)

asyncio.run(main())
""")
        
        stream_path = project_path / f"stream_{stx.replace('::stx', '')}.py"
        stream_path.write_text(f"""\
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
    label = "Welcome to Neuronum"
    
    while True:
        data = {{
            "message": "Hello, Neuronum!"
        }}
        await cell.stream(label, data)

asyncio.run(main())
""")
        
    if app and nodeID:

        descr = f"{nodeID} App"                                                  
        partners = ["public"]                                      
        stxID = await cell.create_stx(descr, partners)  


        descr = f"Greet {nodeID}"                                           
        key_values = {                                                          
            "say": "hello",
        }
        STX = stxID                                                     
        label = "say:hello"                                                                                                                                                         
        partners = ["public"]                                                   
        txID = await cell.create_tx(descr, key_values, STX, label, partners)


        app_path = project_path / "app.py"
        app_path.write_text(f"""\
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
    STX = "{stxID}"                                          
    async for operation in cell.sync(STX):       
        txID = operation.get("txID")
        client = operation.get("operator")                    
                            
        if txID == "{txID}":             
            data = {{
                "json": f"Hello {{client}} from {nodeID}",
                "html": f\"\"\"
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>Greeting Node</title>
  </head>
  <body>
    <div class="card">
      <h1>Hello, {{client}}</h1>
      <p>Greetings from <span class="node">{nodeID}</span></p>
    </div>
  </body>
</html>
\"\"\"

            }}
            await cell.tx_response(txID, client, data)

asyncio.run(main())
""")
        
    click.echo(f"Neuronum Node '{nodeID}' initialized!")


@click.command()
@click.option('--d', is_flag=True, help="Start node in detached mode")
def start_node(d):
    click.echo("Starting Node...")

    project_path = Path.cwd()
    script_files = glob.glob("sync_*.py") + glob.glob("stream_*.py") + glob.glob("app.py")

    processes = []
    system_name = platform.system()

    for script in script_files:
        script_path = project_path / script
        if script_path.exists():
            python_cmd = "pythonw" if system_name == "Windows" else "python"

            if d:
                process = subprocess.Popen(
                    ["nohup", python_cmd, str(script_path), "&"] if system_name != "Windows"
                    else [python_cmd, str(script_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            else:
                process = subprocess.Popen(["python", str(script_path)], start_new_session=True)

            processes.append(process.pid)

    if not processes:
        click.echo("Error: No valid node script found. Ensure the node is set up correctly.")
        return

    with open("node_pid.txt", "w") as f:
        f.write("\n".join(map(str, processes)))

    click.echo("Node started successfully!")


@click.command()
def stop_node():
    asyncio.run(async_stop_node())

async def async_stop_node():
    click.echo("Stopping Node...")

    node_pid_path = Path("node_pid.txt")

    try:
        with open("node_pid.txt", "r") as f:
            pids = [int(pid.strip()) for pid in f.readlines()]

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
        click.echo("Node stopped successfully!")

    except FileNotFoundError:
        click.echo("Error: No active node process found.")
    except subprocess.CalledProcessError:
        click.echo("Error: Unable to stop some node processes.")


@click.command()
def connect_node():
    node_type = questionary.select(
        "Choose Node type:",
        choices=["public", "private"]
    ).ask()
    descr = click.prompt("Node description (max. 25 characters)")
    asyncio.run(async_connect_node(descr, node_type))

async def async_connect_node(descr, node_type):
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
        print("Error: .env with credentials not found")
        return
    except Exception as e:
        print(f"Error reading .env file: {e}")
        return

    try:
        with open("NODE.md", "r") as f: 
            nodemd_file = f.read() 

    except FileNotFoundError:
        print("Error: NODE.md file not found")
        return
    except Exception as e:
        print(f"Error reading NODE.md file: {e}")
        return

    url = f"https://{network}/api/connect_node/{node_type}"

    node = {
        "nodeID": nodeID,
        "descr": descr,
        "host": host,
        "password": password,
        "synapse": synapse,
        "nodemd_file": nodemd_file
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
        
    if nodeID == "Node does not exist":
        click.echo(f"Neuronum Node not found! Make sure you initialized your Node correctly")
    else:
        if node_type == "public":
            click.echo(f"Public Neuronum Node '{nodeID}' connected! Visit: {node_url}")
        else:   
            click.echo(f"Private Neuronum Node '{nodeID}' connected!")


@click.command()
def update_node():
    asyncio.run(async_update_node())

async def async_update_node():
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

    except FileNotFoundError:
        click.echo("Error: NODE.md file not found")
        return
    except Exception as e:
        click.echo(f"Error reading NODE.md file: {e}")
        return

    url = f"https://{network}/api/update_node"
    node_payload = {
        "nodeID": nodeID,
        "host": host,
        "password": password,
        "synapse": synapse,
        "nodemd_file": nodemd_file
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=node_payload) as response:
                response.raise_for_status()
                data = await response.json()
                nodeID = data["nodeID"]
                node_url = data["node_url"]
        except aiohttp.ClientError as e:
            click.echo(f"Error sending request: {e}")
            return

    cell = neuronum.Cell(
        host=host,
        password=password,
        network=network,
        synapse=synapse
    )

    cells = await cell.list_cells()
    tx = await cell.list_tx()
    ctx = await cell.list_ctx()
    stx = await cell.list_stx()
    nodes = await cell.list_nodes()

    await asyncio.to_thread(Path("cells.json").write_text, json.dumps(cells, indent=4))
    await asyncio.to_thread(Path("transmitters.json").write_text, json.dumps(tx, indent=4))
    await asyncio.to_thread(Path("circuits.json").write_text, json.dumps(ctx, indent=4))
    await asyncio.to_thread(Path("streams.json").write_text, json.dumps(stx, indent=4))
    await asyncio.to_thread(Path("nodes.json").write_text, json.dumps(nodes, indent=4))

    click.echo(f"Neuronum Node '{nodeID}' updated! Visit: {node_url}")


@click.command()
def disconnect_node():
    asyncio.run(async_disconnect_node())

async def async_disconnect_node():
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

    url = f"https://{network}/api/disconnect_node"
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

    click.echo(f"Neuronum Node '{nodeID}' disconnected!")


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


cli.add_command(create_cell)
cli.add_command(connect_cell)
cli.add_command(view_cell)
cli.add_command(disconnect_cell)
cli.add_command(delete_cell)
cli.add_command(init_node)
cli.add_command(start_node)
cli.add_command(stop_node)
cli.add_command(connect_node)
cli.add_command(update_node)
cli.add_command(disconnect_node)
cli.add_command(delete_node)


if __name__ == "__main__":
    cli()
