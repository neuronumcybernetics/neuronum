### **node_simple_app**
Set up a Neuronum Node app to receive requests and send responses


### **Connect your Neuronum Cell**
```sh
neuronum connect-cell
```

### **Initialize your Node with App template**
```sh
neuronum init-node --app
```

### **Change to Node folder**
```sh
cd node_node_id
```

### **Start your Node**
```sh
neuronum start-node
```

or

```sh
neuronum start-node --d   # start your Node in "detached" mode
```


### **Send a Request to your Node**
1. Connect to Neuronum at https://neuronum.net/connect
2. Open: https://neuronum.net/explore and enter your Transmitter ID (look in the app.py file of your Node folder)
3. Activate your Transmitter -> response loads in your Browser


### **Connect your Node to Neuronum**
```sh
neuronum connect-node
```

### **NODE.md File**
The `NODE.md` file provides guidelines for interacting with your Node's data gateways.  
Add markdown content (follow best practice and format key details in ```json) to structure your instructions:


NODE.md Example:
```markdown
[![Website](https://img.shields.io/badge/Stream-gy3w11qAEibN::stx-blue)](https://neuronum.net/stream/gy3w11qAEibN::stx)  [![Website](https://img.shields.io/badge/Transmitter-ICfyWjdExPBh::tx-green)](https://neuronum.net/tx/ICfyWjdExPBh::tx)  [![Website](https://img.shields.io/badge/Circuit-bPjx22Hr4Qf7::ctx-red)](https://neuronum.net/circuit/bPjx22Hr4Qf7::ctx)

```json
{
    "gateways": [
        {
            "type": "stream",
            "id": "gy3w11qAEibN::stx",
            "info": "synchronize this Node streaming: Hello, Neuronum!"
        },
        {
            "type": "transmitter",
            "id": "ICfyWjdExPBh::tx",
            "info": "greet this Node"
        },
        {
            "type": "circuit",
            "id": "bPjx22Hr4Qf7::ctx",
            "info": "view request log of this Node"
        }
    ]
}
```
```

Update your Node to publish your NODE.md
```sh
neuronum update-node
```