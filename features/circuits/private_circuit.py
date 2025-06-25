import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():
                                                        
    label = "label"                                                         # label your data
    data = {                                                                # data as key-value pairs
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    await cell.store(label, data)                                           # store data in your private Circuit - > get success message back

    
    data = await cell.load(label)                                           # load data by label
    key1 = data["key1"]                                                     # get data from key
    key2 = data["key2"]
    key3 = data["key3"]
    print(key1, key2, key3)                                                 # print data


    await cell.delete(label)                                                # delete data by label - > get success message back


    await cell.clear()                                                      # clear Circuit (CTX) - > get success message back

asyncio.run(main())