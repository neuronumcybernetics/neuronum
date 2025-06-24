import asyncio
from rapidfuzz import process
import neuronum
import datetime
from pathlib import Path


def log_interaction(user_input, output, log_path=Path("cellai.log")):
    log_path = Path(log_path)

    timestamp = datetime.datetime.now().isoformat()
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}]\n")
        log_file.write(f"USER: {user_input}")
        log_file.write(f"{output}\n\n")


async def main(host, password, network, synapse):
    cell = neuronum.Cell(
        host=host,
        password=password,
        network=network,
        synapse=synapse
    )

    tx = await cell.list_tx()
    nodes = await cell.list_nodes()

    transmitters = tx
    transmitters_by_id = {t["txID"]: t for t in transmitters}

    info_to_gateway = []
    for node in nodes:
        for g in node["Node.md"]["gateways"]:
            info_to_gateway.append({
                "nodeID": node["nodeID"],
                "gateway": g,
                "info": g["info"],
                "descr": node["descr"]
            })

    print("Cellai: Ready for your instruction!")
    loop = asyncio.get_event_loop()

    while True:
        try:
            user_input = await loop.run_in_executor(None, input, ">> ")
            user_input = user_input.strip()
            if user_input.lower() in {"exit", "quit"}:
                log_interaction(user_input, "Session ended by user.")
                break

            match, score, idx = process.extractOne(user_input, [x["info"] for x in info_to_gateway])
            best = info_to_gateway[idx]

            output_log = (
                f"\nMatched: {match} ({score:.1f}%)\n"
                f"Node: {best['descr']} [{best['nodeID']}]\n"
                f"Gateway: {best['gateway']['id']} ({best['gateway']['type']})"
            )
            print(output_log)

            if best['gateway']['type'] == "transmitter":
                tx_id = best['gateway']['id']
                tx_data = transmitters_by_id.get(tx_id)
                if tx_data:
                    print(f"Executing transmitter: {tx_data['descr']}")
                    
                    dynamic_payload = {}
                    for key in tx_data["data"].keys():
                        prompt = f"Enter value for '{key}': "
                        value = await loop.run_in_executor(None, input, prompt)
                        dynamic_payload[key] = value

                    print(f"Payload: {dynamic_payload}")
                    TX = tx_id
                    tx_response = await cell.activate_tx(TX, dynamic_payload)
                    print(tx_response["json"])
                    output_log += f"\nTransmitter executed: {tx_data['descr']}\nPayload: {dynamic_payload}\nResponse: {tx_response['json']}"
                else:
                    warning = "Transmitter not found."
                    print(warning)
                    output_log += f"{warning}"

            elif best['gateway']['type'] == "stream":
                STX = best['gateway']['id']
                print(f"Starting stream sync for STX: {STX}")
                async for operation in cell.sync(STX):
                    label = operation.get("label")
                    data = operation.get("data")
                    ts = operation.get("time")
                    stxID = operation.get("stxID")
                    operator = operation.get("operator")
                    line = f"[{ts}] {label} | Operator: {operator} | STX: {stxID}\nData: {data}"
                    print(line)
                    output_log += f"\n{line}"
            elif best['gateway']['type'] == "circuit":
                CTX = best['gateway']['id']
                label = await loop.run_in_executor(None, input, "Enter label to load from circuit: ")
                label = label.strip()
                data = await cell.load(label, CTX)
                print(data)
                output_log += f"\nCircuit loaded from CTX: {CTX} with label '{label}'\nData: {data}"
            else:
                msg = "Unknown gateway type."
                print(msg)
                output_log += f"{msg}"

            log_interaction(user_input, output_log)

        except KeyboardInterrupt:
            print("\nExiting.")
            log_interaction("KeyboardInterrupt", "Session exited with Ctrl+C")
            break


if __name__ == "__main__":
    asyncio.run(main(host, password, network, synapse))