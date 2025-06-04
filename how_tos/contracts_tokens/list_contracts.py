import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
                                                            
    contractList = await cell.list_contracts()                              # list of all signable Contracts - > get list back
    print(contractList)                                                     # print Contract list
                                      
asyncio.run(main())