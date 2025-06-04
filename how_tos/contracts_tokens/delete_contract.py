import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
    
    contractID = "id::contract"                                             # select Contract
    await cell.delete_contract(contractID)                                  # delete Contract - > get success message back
                                      
asyncio.run(main())