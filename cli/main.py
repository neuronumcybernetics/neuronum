import click
import questionary
from pathlib import Path
import requests
import subprocess
import os
import neuronum
import json

@click.group()
def cli():
    """Neuronum CLI Tool"""


@click.command()
def init_node():
    click.echo("Initialize Node")

    node_type = questionary.select(
        "Choose Node type:",
        choices=["public", "private"]
    ).ask()

    descr = click.prompt("Node description (max. 25 characters)")
    host = click.prompt("Enter your cell host")
    password = click.prompt("Enter your password", hide_input=True)
    network = click.prompt("Enter your network")
    synapse = click.prompt("Enter your synapse", hide_input=True)

    cell = neuronum.Cell(
    host=host,         
    password=password,                         
    network=network,                        
    synapse=synapse
    )

    tx = cell.list_tx()
    ctx = cell.list_ctx()
    stx = cell.list_stx()
    contracts = cell.list_contracts()

    url = f"https://{network}/api/init_node/{node_type}"

    node = {"descr": descr, "host": host, "password": password, "synapse": synapse}

    try:
        response = requests.post(url, json=node)
        response.raise_for_status()
        nodeID = response.json()["nodeID"]
    except requests.exceptions.RequestException as e:
        click.echo(f"Error sending request: {e}")
        return

    node_filename = "node"
    project_path = Path(node_filename)
    project_path.mkdir(exist_ok=True)

    env_path = project_path / ".env"
    env_path.write_text(f"NODE={nodeID}\nHOST={host}\nPASSWORD={password}\nNETWORK={network}\nSYNAPSE={synapse}\n")

    tx_path = project_path / "transmitters.json"
    tx_path.write_text(json.dumps(tx, indent=4))

    ctx_path = project_path / "circuits.json"
    ctx_path.write_text(json.dumps(ctx, indent=4))

    stx_path = project_path / "streams.json"
    stx_path.write_text(json.dumps(stx, indent=4))

    contracts_path = project_path / "contracts.json"
    contracts_path.write_text(json.dumps(contracts, indent=4))

    nodemd_path = project_path / "NODE.md"
    nodemd_path.write_text("""\
#some markdown                             
""")
        
    main_path = project_path / "main.py"
    main_path.write_text("""\
import neuronum
import os
from dotenv import load_dotenv

load_dotenv()
host = os.getenv("HOST")    
password = os.getenv("PASSWORD")
network = os.getenv("NETWORK")                                                                                            
synapse = os.getenv("SYNAPSE")                    

#set cell connection
cell = neuronum.Cell(
host=host,
password=password,
network=network,
synapse=synapse
)

STX = "n9gW3LxQcecI::stx"
stream = cell.sync(STX)
for operation in stream:
    label = operation.get("label")
    value = operation.get("data").get("message")
    ts = operation.get("time")
    stxID = operation.get("stxID")
    operator = operation.get("operator")
    print(label, value, ts, stxID, operator)                              
    """)

    click.echo(f"Neuronum Node '{nodeID}' initialized!")


@click.command()
def start_node():
    click.echo("Starting Node...")

    project_path = Path.cwd()
    main_file = project_path / "main.py"

    if not main_file.exists():
        click.echo("Error: main.py not found. Make sure the node is set up.")
        return

    process = subprocess.Popen(["python", str(main_file)], start_new_session=True)

    with open("node_pid.txt", "w") as f:
        f.write(str(process.pid))

    click.echo("Neuronum Node started successfully!")


@click.command()
def stop_node():
    """Stops the Neuronum node"""
    click.echo("Stopping Neuronum Node...")

    try:
        with open("node_pid.txt", "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, 9) 
        os.remove("node_pid.txt")
        click.echo("Neuronum Node stopped successfully!")
    except FileNotFoundError:
        click.echo("Error: No active node process found.")
    except Exception as e:
        click.echo(f"Error stopping node: {e}")


@click.command()
def register_node():
    click.echo("Register Node")

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

    url = f"https://{network}/api/register_node"

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

    click.echo(f"Neuronum Node '{nodeID}' registered! Visit: {node_url}")


@click.command()
def update_node():
    click.echo("Update Node")

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

    tx = cell.list_tx()
    ctx = cell.list_ctx()
    stx = cell.list_stx()
    contracts = cell.list_contracts()

    tx_path = Path("transmitters.json")
    ctx_path = Path("circuits.json")
    stx_path = Path("streams.json")
    contracts_path = Path("contracts.json")

    tx_path.write_text(json.dumps(tx, indent=4))
    ctx_path.write_text(json.dumps(ctx, indent=4))
    stx_path.write_text(json.dumps(stx, indent=4))
    contracts_path.write_text(json.dumps(contracts, indent=4))

    click.echo(f"Neuronum Node '{nodeID}' updated! Visit: {node_url}")


@click.command()
def delete_node():
    click.echo("Delete Node")

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


cli.add_command(init_node)
cli.add_command(start_node)
cli.add_command(stop_node)
cli.add_command(register_node)
cli.add_command(update_node)
cli.add_command(delete_node)


if __name__ == "__main__":
    cli()
