import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():

    descr = "Test Circuit"                                                  # describe your Circuit CTX (max 25 characters)
    partners = ["public"]                                                   # a public Transmitter TX all Cells can execute
    ctxID = await cell.create_ctx(descr, partners)                          # create the Circuit CTX -> get ctxID back
    print(f"Circuit ID: {ctxID}")                                           # print the Circuit CTX ID


    CTX = ctxID                                                             # select the Circuit (CTX
    label = "label"                                                         # label your data
    data = {                                                                # data as key-value pairs
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    await cell.store(label, data, CTX)                                      # store data - > get success message back


    data = await cell.load(label, CTX)                                      # load data by label and CTX
    key1 = data["key1"]                                                     # get data from key
    key2 = data["key2"]
    key3 = data["key3"]
    print(key1, key2, key3)                                                 # print data

    
    await cell.delete(label, CTX)                                           # delete data by label and CTX - > get success message back


    await cell.clear(CTX)                                                   # clear Circuit (CTX) - > get success message back

asyncio.run(main())