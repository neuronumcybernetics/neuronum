### **node_private_stream**
Set up a Neuronum Node that privately streams data

### **Create a private Stream Gateway**
1. Visit: https://neuronum.net/createSTX
2. Enter a short Stream Description (e.g. Test Stream)
3. Write "private" into the Partner Cell list
4. Click publish STX
5. Copy your Stream ID (id::stx)

### **Connect your Neuronum Cell**
```sh
neuronum connect-cell
```

### **Initialize your Node with Stream template**
```sh
neuronum init-node --stream id::stx     # place your copied Stream ID here
```

or

```sh
neuronum init-node                      # to use your default private stream data gateway
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
neuronum start-node --d                 # start Node in "detached" mode
```

### **NODE.md File**
The `NODE.md` file provides guidelines for interacting with your Node's data gateways.  
Add markdown content (follow best practice and format key details in ```json) to structure your instructions, then update your Node with:

```sh
neuronum update-node
```