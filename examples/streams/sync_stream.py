import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)


async def main():

    STX = "id::stx"                                                         # select the Stream STX
    async for operation in cell.sync(STX):                                  # get Stream operations
        label = operation.get("label")                                      # get Stream operation details
        data = operation.get("data")
        ts = operation.get("time")
        stxID = operation.get("stxID")
        operator = operation.get("operator")
        print(label, data, ts, stxID, operator)                             # print Stream operation details

                                                        
    async for operation in cell.sync():                                     # get private Stream operations
        label = operation.get("label")                                      # get Stream operation details
        data = operation.get("data")
        ts = operation.get("time")
        stxID = operation.get("stxID")
        operator = operation.get("operator")
        print(label, data, ts, stxID, operator)                             # print Stream operation details

asyncio.run(main())