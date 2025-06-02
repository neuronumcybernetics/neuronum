import click
import questionary
from pathlib import Path
import requests
import subprocess
import os
import neuronum
import json
import platform
import glob

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
def init_node(sync, stream):

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
    node = {"host": host, "password": password, "synapse": synapse}

    try:
        response = requests.post(url, json=node)
        response.raise_for_status()
        nodeID = response.json()["nodeID"]
    except requests.exceptions.RequestException as e:
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

    cells = cell.list_cells()
    tx = cell.list_tx()
    ctx = cell.list_ctx()
    stx = cell.list_stx()
    contracts = cell.list_contracts()
    nodes = cell.list_nodes()

    cells_path = project_path / "cells.json"
    tx_path = project_path / "transmitters.json"
    ctx_path = project_path / "circuits.json"
    stx_path = project_path / "streams.json"
    contracts_path = project_path / "contracts.json"
    nodes_path = project_path / "nodes.json"

    cells_path.write_text(json.dumps(cells, indent=4))
    tx_path.write_text(json.dumps(tx, indent=4))
    ctx_path.write_text(json.dumps(ctx, indent=4))
    stx_path.write_text(json.dumps(stx, indent=4))
    contracts_path.write_text(json.dumps(contracts, indent=4))
    nodes_path.write_text(json.dumps(nodes, indent=4))

    env_path = project_path / ".env"
    env_path.write_text(f"NODE={nodeID}\nHOST={host}\nPASSWORD={password}\nNETWORK={network}\nSYNAPSE={synapse}\n")

    gitignore_path = project_path / ".gitignore"
    gitignore_path.write_text(".env\n")

    nodemd_path = project_path / "NODE.md"
    nodemd_path.write_text("## Use this NODE.md file to add instructions on how to interact with your node\n")

    stx = sync[0] if sync else (stream[0] if stream else host.replace("::cell", "::stx"))

    if sync:
        for stx in sync:
            sync_path = project_path / f"sync_{stx.replace('::stx', '')}.py"
            sync_path.write_text(f"""\
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

STX = "{stx}"
stream = cell.sync(STX)
for operation in stream:
    label = operation.get("label")
    data = operation.get("data")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
    print(label, data, ts, stxID, operator)
""")


    if stream:
        for stx in stream:
            stream_path = project_path / f"stream_{stx.replace('::stx', '')}.py"
            stream_path.write_text(f"""\
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

STX = "{stx}"
label = "your_label"
while True:
    data = {{
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }}
    cell.stream(label, data, STX)
""")
    
    if not sync and not stream:
        sync_path = project_path / f"sync_{stx.replace('::stx', '')}.py"
        sync_path.write_text(f"""\
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
                             
STX = "{stx}"
stream = cell.sync(STX)
for operation in stream:
    message = operation.get("data").get("message")
    print(message)
""")
        
        stream_path = project_path / f"stream_{stx.replace('::stx', '')}.py"
        stream_path.write_text(f"""\
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
                             
STX = "{stx}"
label = "Welcome to Neuronum"
while True:
    data = {{
        "message": "Hello, Neuronum!"
    }}
    cell.stream(label, data, STX)
""")

    click.echo(f"Neuronum Node '{nodeID}' initialized!")



@click.command()
def start_node():
    click.echo("Starting Node...")

    project_path = Path.cwd()

    script_files = glob.glob("sync_*.py") + glob.glob("stream_*.py")

    processes = []

    for script in script_files:
        script_path = project_path / script
        if script_path.exists():
            process = subprocess.Popen(["python", str(script_path)], start_new_session=True)
            processes.append(process.pid)

    if not processes:
        click.echo("Error: No valid node script found. Ensure the node is set up correctly.")
        return

    with open("node_pid.txt", "w") as f:
        f.write("\n".join(map(str, processes)))

    click.echo(f"Node started successfully!")


@click.command()
def stop_node():
    click.echo("Stopping Node...")

    try:
        with open("node_pid.txt", "r") as f:
            pids = [int(pid.strip()) for pid in f.readlines()]

        system_name = platform.system()

        for pid in pids:
            try:
                if system_name == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    os.kill(pid, 9)
            except ProcessLookupError:
                click.echo(f"Warning: Process {pid} already stopped or does not exist.")

        os.remove("node_pid.txt")
        click.echo(f"Node stopped successfully!")

    except FileNotFoundError:
        click.echo("Error: No active node process found.")
    except subprocess.CalledProcessError:
        click.echo("Error: Unable to stop some node processes.")


@click.command()
def register_node():
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
    
    node_type = questionary.select(
        "Choose Node type:",
        choices=["public", "private"]
    ).ask()

    descr = click.prompt("Node description (max. 25 characters)")

    try:
        with open("NODE.md", "r") as f: 
            nodemd_file = f.read() 

    except FileNotFoundError:
        print("Error: NODE.md file not found")
        return
    except Exception as e:
        print(f"Error reading NODE.md file: {e}")
        return

    url = f"https://{network}/api/register_node/{node_type}"

    node = {
        "nodeID": nodeID,
        "descr": descr,
        "host": host,
        "password": password,
        "synapse": synapse,
        "nodemd_file": nodemd_file
    }

    try:
        response = requests.post(url, json=node)
        response.raise_for_status()
        nodeID = response.json()["nodeID"]
        node_url = response.json()["node_url"]
    except requests.exceptions.RequestException as e:
        click.echo(f"Error sending request: {e}")
        return

    click.echo(f"Neuronum Node '{nodeID}' registered! Visit: {node_url}")


@click.command()
def update_node():
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

    url = f"https://{network}/api/update_node"

    node = {
        "nodeID": nodeID,
        "host": host,
        "password": password,
        "synapse": synapse,
        "nodemd_file": nodemd_file
    }

    try:
        response = requests.post(url, json=node)
        response.raise_for_status()
        nodeID = response.json()["nodeID"]
        node_url = response.json()["node_url"]
    except requests.exceptions.RequestException as e:
        click.echo(f"Error sending request: {e}")
        return
    

    cell = neuronum.Cell(
    host=host,         
    password=password,                         
    network=network,                        
    synapse=synapse
    )

    cells = cell.list_cells()
    tx = cell.list_tx()
    ctx = cell.list_ctx()
    stx = cell.list_stx()
    contracts = cell.list_contracts()
    nodes = cell.list_nodes()

    cells_path = Path("cells.json")
    tx_path = Path("transmitters.json")
    ctx_path = Path("circuits.json")
    stx_path = Path("streams.json")
    contracts_path = Path("contracts.json")
    nodes_path = Path("nodes.json")

    cells_path.write_text(json.dumps(cells, indent=4))
    tx_path.write_text(json.dumps(tx, indent=4))
    ctx_path.write_text(json.dumps(ctx, indent=4))
    stx_path.write_text(json.dumps(stx, indent=4))
    contracts_path.write_text(json.dumps(contracts, indent=4))
    nodes_path.write_text(json.dumps(nodes, indent=4))

    click.echo(f"Neuronum Node '{nodeID}' updated! Visit: {node_url}")


@click.command()
def delete_node():
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

    url = f"https://{network}/api/delete_node"

    node = {
        "nodeID": nodeID,
        "host": host,
        "password": password,
        "synapse": synapse
    }

    try:
        response = requests.post(url, json=node)
        response.raise_for_status()
        nodeID = response.json()["nodeID"]
    except requests.exceptions.RequestException as e:
        click.echo(f"Error sending request: {e}")
        return

    click.echo(f"Neuronum Node '{nodeID}' deleted!")


@click.command()
def call_cellai():
    try:
        from cellai import cellai
        cellai.main()
    except ImportError:
        click.echo("Cellai not found. Please check the necessary dependencies.")

cli.add_command(create_cell)
cli.add_command(connect_cell)
cli.add_command(view_cell)
cli.add_command(disconnect_cell)
cli.add_command(delete_cell)
cli.add_command(init_node)
cli.add_command(start_node)
cli.add_command(stop_node)
cli.add_command(register_node)
cli.add_command(update_node)
cli.add_command(delete_node)
cli.add_command(call_cellai)


if __name__ == "__main__":
    cli()
