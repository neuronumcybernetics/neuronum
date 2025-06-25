import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():

    TX = "id::tx"                                                           # select the Transmitter TX
    client = "id::cell"                                                     # select the Client Cell 
    data = {                                                                # enter response key value data 
        "key": "value"
    }
    await cell.tx_response(TX, client, data)                                # respond TX - > get success message back

asyncio.run(main())