## **ping_node**
Set up the default Neuronum Node (App) template and ping your Node


### **Start with initializing your Node (App)**
```sh
neuronum init-node
```

This command will prompt you for a description (e.g., PingNode) and will create

1. A Stream (STX) so your App can receive requests, and a Transmitter (TX) to match those requests
2. A new directory named "PingNode_<your_node_id>" with the following files

.env: Stores your Node's credentials for connecting to the network.

app.py: The main Python script that contains your Node's core logic.

NODE.md: Public documentation that provides instructions for interacting with your Node.

config.json: A configuration file that stores metadata about your app and enables Cellai to interact with your Node's data gateways.

ping.html: A static HTML file used to render web-based responses.

### **Change to Node folder**
```sh
cd PingNode_<your_node_id>
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

## **Interact with your Node**
**CELLai** is an AI tool for developers to test and interact with apps built on Neuronum using natural language.
[Launch in your browser](https://cellai.neuronum.net)

**Now available on Google Play**  
*(Supported Locations: Germany, Switzerland & Austria)*  
[Download on Google Play](https://play.google.com/store/apps/details?id=net.neuronum.cellai&utm_source=emea_Med)

Send this Commands to Cellai: Ping My Node


