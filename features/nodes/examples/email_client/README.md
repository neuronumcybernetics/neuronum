### **email_client**
Set up the Neuronum Node (App) that lets you send Emails. ⚠️ Important:
Many email providers (such as Gmail, Outlook, or Yahoo) may restrict access to their SMTP/IMAP servers by default.

## 1. **Start with initializing your Node (App)**
```sh
neuronum init-node --blank
```

This command will prompt you for a description (e.g. EmailClient) and will create a new directory named "EmailClient_<your_node_id>" with the following files

.env: Stores your Node's credentials for connecting to the network.<br>
Add EMAIL_PW to this file like:
```env
NODE=id::node
HOST=id::cell
PASSWORD=cell_password
NETWORK=neuronum.net
SYNAPSE=cell_synapse
EMAIL_PW=email_password
```

app.py: The main Python script that contains your Node's core logic. Replace the content of app.py with the following script:
```python
import asyncio
import neuronum
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import aiosmtplib
import aioimaplib

load_dotenv()
host = os.getenv("HOST")
password = os.getenv("PASSWORD")
network = os.getenv("NETWORK")
synapse = os.getenv("SYNAPSE")
email_pw = os.getenv('EMAIL_PW')

smtp_server = 'smtp.strato.de'
imap_server = 'imap.strato.de'
smtp_port = 587
email_user = 'your@email.de'

cell = neuronum.Cell(
    host=host,
    password=password,
    network=network,
    synapse=synapse
)

async def main():

    async def fetch_unread_emails():
        client = aioimaplib.IMAP4_SSL(host=imap_server)
        await client.wait_hello_from_server()

        await client.login(email_user, email_pw)
        print("Logged in")

        await client.select('INBOX')
        search_resp = await client.search('UNSEEN')

        email_ids = []
        if search_resp.lines:
            email_ids = search_resp.lines[0].decode().split()

        print(f"{len(email_ids)} unread mails")
        print(email_ids)

        await client.logout()
        return len(email_ids)



    async def send_email(subject: str, body: str, to_email: str):
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        try:
            async with aiosmtplib.SMTP(hostname=smtp_server, port=smtp_port) as server:
                await server.login(email_user, email_pw)
                await server.send_message(msg)
                print("Email sent successfully!")
        except Exception as e:
            print(f"Error occurred while sending email: {e}")
            raise


    STX = "id::stx" #replace with your actual Stream ID (see section 2.)
    async for operation in cell.sync(STX):
        txID = operation.get("txID")
        operator_id = operation.get("operator")
        data = operation.get("data")

        subject = data.get("subject")
        body = data.get("body")
        receiver = data.get("receiver")

        if txID == "id::tx":  #replace with your actual Transmitter ID (see section 2.)
            await send_email(subject, body, receiver)
            unread_emails = await fetch_unread_emails()

            response_data = {
                "json": f"Email Sent with {data}, Unread Emails: {unread_emails}"
            }

            await cell.tx_response(txID, operator_id, response_data)

asyncio.run(main())
```


**Make sure to install the required dependencies before running your Node:**
```sh
pip install aiosmtplib aioimaplib python-dotenv neuronum
```

NODE.md: Public documentation that provides instructions for interacting with your Node. You can ignore this file unless you want to publish your App

config.json: A configuration file that stores metadata about your app and enables Cellai to interact with your Node's data gateways. Replace the code with:

```json
{
    "app_metadata": {
        "name": "EmailClient",
        "version": "1.0.0",
        "author": "id::cell"
    },
    "data_gateways": [
        {
        "type": "transmitter",
        "id": "id::tx",
        "info": "Send an Email. Provide Subject, Body & Receiver"
        }
    ],
    "legals": {
        "terms": "https://url_to_your/terms",
        "privacy_policy": "https://url_to_your/privacy_policy",
        "last_update" : "DD/MM/YYYY"
    }
}
```

**make sure to replace "id::tx" with your actual Transmitter ID (see section 2.)**

ping.html: A static HTML file used to render web-based responses. You can delete this file, as we're building a headless application

## 2. **Create Data Gateways**
You need to create 2 data gateways. A Stream (STX) that allows your Node to receive data/requests and a Transmitter (TX) to match client requests

1. [Connect to Neuronum](https://neuronum.net/connect)
2. [Create A Stream](https://neuronum.net/createSTX)<br>
Description: Email Client<br>
Partner Cell List: private<br>
-> publish STX
3. [Create A Transmitter](https://neuronum.net/createTX)<br>
Description: Send Email<br>
Key: subject / Example: Email subject<br>
Key: body / Example: Email body<br>
Key: receiver / Example: Email address<br>
Select Stream: Select your created Stream ID<br>
Label: send:email<br>
Partner Cell List: private<br>
-> publish TX

## 3. **Run your Node**
### **Change to Node folder**
```sh
cd EmailClient_<your_node_id>
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

Send this Command to Cellai: Send an Email. Subject: Test Mail, Body: This is a Test Mail. Receiver: address@email.com