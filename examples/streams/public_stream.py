import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():

    descr = "Test Stream"                                                   # describe your Stream STX (max 25 characters)
    partners = ["public"]                                                   # A public Stream all Cells can synchronize
    stxID = await cell.create_stx(descr, partners)                          # create the Stream STX -> get stxID back
    print(f"Stream ID: {stxID}")                                            # print the Stream STX ID


    STX = stxID                                                             # select the Stream STX
    label = "label"                                                         # label your data
    data = {                                                                # data as key-value pairs
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    await cell.stream(label, data, STX)                                     # stream data to Stream STX - > get success message back

asyncio.run(main())