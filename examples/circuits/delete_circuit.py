import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
    
    CTX = "id::ctx"                                                         # select Circuit CTX
    await cell.delete_ctx(CTX)                                              # delete CTX - > get success message back
                                      
asyncio.run(main())