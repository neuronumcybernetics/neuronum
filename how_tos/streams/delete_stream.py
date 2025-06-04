import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
    
    STX = "id::stx"                                                         # select Stream STX
    await cell.delete_stx(STX)                                              # delete STX - > get success message back
                                      
asyncio.run(main())