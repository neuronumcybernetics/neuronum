import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
                                                            
    txList = await cell.list_tx()                                           # list of all executable Transmitters TX - > get list back
    print(txList)                                                           # print Transmitters TX list
                                      
asyncio.run(main())