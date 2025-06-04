import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
    
    TX = "id::tx"                                                           # select Transmitter TX
    await cell.delete_tx(TX)                                                # delete TX - > get success message back
                                      
asyncio.run(main())