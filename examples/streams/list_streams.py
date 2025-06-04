import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
                                                            
    stxList = await cell.list_stx()                                          # list of all synchronizable Streams STX - > get list back
    print(stxList)                                                           # print Streams STX list
                                      
asyncio.run(main())