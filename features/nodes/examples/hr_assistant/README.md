### **hr_assistant**
Set up a Neuronum Node (App) that helps with common tasks in the Human Resources department

## 1. **Start with initializing your Node (App)**
```sh
neuronum init-node --blank
```

This command will prompt you for a description (e.g. HR-Assistant) and will create a new directory named "HR-Assistant<your_node_id>" with the following files

.env: Stores your Node's credentials for connecting to the network.<br>
```env
NODE=id::node
HOST=id::cell
PASSWORD=cell_password
NETWORK=neuronum.net
SYNAPSE=cell_synapse
```

app.py: The main Python script that contains your Node's core logic. Replace the content of app.py with the following script:
```python
import asyncio
import neuronum
import os                   
from dotenv import load_dotenv
                                                              
                        
load_dotenv()
host = os.getenv("HOST")
password = os.getenv("PASSWORD")
network = os.getenv("NETWORK")
synapse = os.getenv("SYNAPSE")

cell = neuronum.Cell(
    host=host,
    password=password,
    network=network,
    synapse=synapse
)

async def main():      
    STX = "id::stx" #Replace with your actual Stream ID (see section 2.)                                           
    async for operation in cell.sync(STX):       
        txID = operation.get("txID")
        client = operation.get("operator")   
        data = operation.get("data")         
                            
        if txID == "id::tx": #Replace with your actual Transmitter ID (see section 2.)         

            def generate_employee_id(existing_labels):
                numeric_ids = []

                for label in existing_labels:
                    try:
                        numeric_ids.append(int(label))
                    except ValueError:
                        continue

                last_id = max(numeric_ids) if numeric_ids else 0
                return last_id + 1


            # Load existing employees
            employees = await cell.load("*", "ZcW5zVNSxEbw::ctx")
            existing_labels = list(employees.keys())

            # Generate the new numeric employee ID
            employee_id = generate_employee_id(existing_labels)

            # Store the new employee data
            await cell.store(employee_id, data, "ZcW5zVNSxEbw::ctx")

            # Notify the client
            await cell.notify(f"{client}", "Employee Stored", f"{data} stored as Employee")

            # Respond to the transaction
            response_data = {
                "json": f"{data} stored as Employee"
            }
            await cell.tx_response(txID, client, response_data)


        if txID == "id::tx":  #Replace with your actual Transmitter ID (see section 2.)  
            id = operation.get("data", {}).get("id")
            new_address = operation.get("data", {}).get("address")

            employee = await cell.load(id, "ZcW5zVNSxEbw::ctx")

            if not employee:
                await cell.tx_response(txID, client, {"error": f"Employee {id} not found."})
                return

            old_address = employee.get("address")  # Save old address here
            employee["address"] = new_address      # Update address

            await cell.store(id, employee, "ZcW5zVNSxEbw::ctx")

            response_data = {
                "json": f"Employee {id} address updated from '{old_address}' to '{new_address}'"
            }

            await cell.notify(f"{client}", "Employee Updated", response_data["json"])
            await cell.tx_response(txID, client, response_data)


        if txID == "id::tx": #Replace with your actual Transmitter ID (see section 2.)  
            id = operation.get("data", {}).get("id")

            employee = await cell.load(id, "ZcW5zVNSxEbw::ctx")
            await cell.delete(id, "ZcW5zVNSxEbw::ctx")


            response_data = {
                "json": f"Employee Deleted: ID: {id}. Data: {employee}"
            }

            await cell.notify(f"{client}", "Employee Deleted", response_data["json"])
            await cell.tx_response(txID, client, response_data)


asyncio.run(main())
```


NODE.md: Public documentation that provides instructions for interacting with your Node. You can ignore this file unless you want to publish your App

config.json: A configuration file that stores metadata about your app and enables Cellai to interact with your Node's data gateways. Replace the code with:

```json
{
    "app_metadata": {
        "name": "HR - Assistant",
        "version": "1.0.0",
        "author": "id::cell"
    },
    "data_gateways": [
        {
        "type": "transmitter",
        "id": "id::tx",
        "info": "Create a new Employee Entry. Provide Name, Address, Birthday and Department of the new Employee"
        },
        {
        "type": "transmitter",
        "id": "id::tx",
        "info": "Update Employee Entry. Provide ID, New Address:"
        },
        {
        "type": "transmitter",
        "id": "id::tx",
        "info": "Delete Employee Entry. Provide ID"
        },
        {
        "type": "circuit",
        "id": "id::ctx",
        "info": "Fetch Employee Data. Provide a Name or ID"
        },
        {
        "type": "circuit",
        "id": "id::ctx",
        "info": "Fetch all Employee Entries."
        }
    ],
    "legals": {
        "terms": "https://url_to_your/terms",
        "privacy_policy": "https://url_to_your/privacy_policy",
        "last_update" : "DD/MM/YYYY"
    }
}
```

**make sure to replace "id::tx" and "id::ctx" with your actual Transmitter/Circuit ID (see section 2.)**

ping.html: A static HTML file used to render web-based responses. You can delete this file, as we're building a headless application

## 2. **Create Data Gateways**
You need to create 5 data gateways. A Stream (STX) that allows your Node to receive data/requests, 3 Transmitter (TX) to match client requests and 1 Circuit (CTX) to store the employee data

1. [Connect to Neuronum](https://neuronum.net/connect)
2. [Create A Stream](https://neuronum.net/createSTX)<br>
Description: HR Assistant<br>
Partner Cell List: private<br>
-> publish STX
3. [Create A Circuit](https://neuronum.net/createCTX)<br>
Description: Employee Data<br>
Partner Cell List: private<br>
-> publish CTX
4. [Create 1. Transmitter](https://neuronum.net/createTX)<br>
Description: New Employee<br>
Key: name / Example: first & last name<br>
Key: address / Example: street & city<br>
Key: birthday / Example: date<br>
Key: department / Example: sales<br>
Select Stream: Select your created Stream ID<br>
Label: new:employee<br>
Partner Cell List: private<br>
-> publish TX
5. [Create 2. Transmitter](https://neuronum.net/createTX)<br>
Description: Update Address<br>
Key: id / Example: number<br>
Key: address / Example: street & city<br>
Select Stream: Select your created Stream ID<br>
Label: update:address<br>
Partner Cell List: private<br>
-> publish TX
6. [Create 2. Transmitter](https://neuronum.net/createTX)<br>
Description: Delete Employee<br>
Key: id / Example: number<br>
Select Stream: Select your created Stream ID<br>
Label: delete:employee<br>
Partner Cell List: private<br>
-> publish TX

## 3. **Run your Node**
### **Change to Node folder**
```sh
cd HR-Assistant_<your_node_id>
```

### **Simply start your App with**
```sh
neuronum start-node
```

or

```sh
neuronum start-node --d   # start your Node in "detached" mode
```

These commands will prompt you to choose who can view and interact with your Node.  
(Note: Community Cells can only select `private`)
```sh
Update your Node
? Who can view your Node?: (Use arrow keys)
 » public
   private
   partners
```

Next, you’ll be asked if you want to change your Node description, which is currently set to "Test App"
```sh
Update Node description: Type up to 25 characters, or press Enter to leave it unchanged: 
```

After that, the terminal should print something like:
```sh
Neuronum Node 'SW07fDQ4yL4y::node' updated!
Starting Node...
Node started successfully with PIDs: 2104
```

### **Stop your Node using the CLI command**
```sh
neuronum stop-node
```

## 4. **Interact with your Node**
**CELLai** is an AI tool for developers to test and interact with apps built on Neuronum using natural language.
[Launch in your browser](https://cellai.neuronum.net)

**Now available on Google Play**  
*(Supported Locations: Germany, Switzerland & Austria)*  
[Download on Google Play](https://play.google.com/store/apps/details?id=net.neuronum.cellai&utm_source=emea_Med)

Send these Commands to Cellai: <br>
Create a new Employee Entry. Name: Bob, Address: Fuggerstraße 1 Augsburg, Birthday: 01.01.2000, Department: Sales<br>
Fetch Employee Data. ID: 1<br>
Fetch Employee Data. Name: Bob<br>
Fetch all Employee Entries.
Update Employee Entry. ID: 1, New Address: Maximilianstraße 1 Augsburg<br>
Delete Employee Entry. ID: 1