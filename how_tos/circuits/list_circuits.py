import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
                                                            
    ctxList = await cell.list_ctx()                                         # list of all accessable Circuits CTX - > get list back
    print(ctxList)                                                          # print Circuits CTX list
                                      
asyncio.run(main())