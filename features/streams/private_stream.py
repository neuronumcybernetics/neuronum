import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():

    label = "label"                                                         # label your data
    data = {                                                                # data as key-value pairs
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    await cell.stream(label, data)                                          # stream data to your private Stream STX - > get success message back

asyncio.run(main())