import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
                                                            
    nodeList = await cell.list_nodes()                                      # list of all public Neuronum Nodes - > get list back
    print(nodeList)                                                         # print Nodes list
                                      
asyncio.run(main())