import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():

    descr = "Test Transmitter"                                              # describe your Transmitter TX (max 25 characters)
    key_values = {                                                          # define keys and example values
        "key1": "valueX",
        "key2": "valueY",
    }
    STX = "id::stx"                                                         # select the Stream (STX) you want the data to be sent to                             
    label = "labelroot:key1:key2"                                           # label the Transmitter TX data
                                                                            # Labels are dynamically created for each activated Transmitter TX
                                                                            # This Transmitter TX will have the Label: labelroot:valueX:valueY
    partners = ["private"]                                                  # a private Transmitter TX only the creator can execute
    txID = await cell.create_tx(descr, key_values, STX, label, partners)    # create the Transmitter TX -> get txID back
    print(f"Transmitter ID: {txID}")                                        # print the Transmitter TX ID


    TX = txID                                                               # select the Transmitter TX
    data = {                                                                # enter value data you want to transmit with predefined keys 
        "key1": "valueX",
        "key2": "valueY",
    }
    tx_response = await cell.activate_tx(TX, data)                          # activate TX - > get response back
    print(tx_response)

asyncio.run(main())