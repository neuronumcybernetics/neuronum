import asyncio
import neuronum

cell = neuronum.Cell(                                                       # set Cell connection
    host="host",                                                            # Cell host
    password="password",                                                    # Cell password
    network="neuronum.net",                                                 # Cell network -> neuronum.net
    synapse="synapse"                                                       # Cell synapse
)

async def main():

    descr = "Test Contract"                                                 # describe your Contract (max 25 characters)
    details = {                                                             # define token details (example creates a contract that distributes tokens with unlimited validity)
        "max_usage": False,                                                 # max number of uses (int or False) // False = unlimited usage
        "validity_in_min": False,                                           # token expiration time in min (int, float or False) // False = no expiration time
        "expiration_date": False                                            # expiration date  (DD-MM-YYYY or False) // False = no expiration date
        }          
    partners = ["partner::cell, partner::cell, partner::cell"]              # Cells defined in partners can sign the Contract
    contractID = await cell.create_contract(descr, details, partners)       # create the Contarct -> get contractID back
    print(f"Contract ID: {contractID}")                                     # print contractID

                                                   
    token = await cell.sign_contract(contractID)                            # sign contract - > get token back
    print(f"Token: {token}")                                                # print token
 

    cp = cell.host                                                          # select counterparty cell
    await cell.request_token(cp, contractID)                                # request token from counterparty cell - > get token request message back


    await cell.present_token(token, cp, contractID)                         # present token to counterparty cell - > get token present message back

    
    validity = await cell.validate_token(token, cp, contractID)             # validate token - > get validity back (True or False)
    print(f"Validity: {validity}")                                          # print validity

asyncio.run(main())