### **Neuronum Node Examples**
node_public_stream: Set up a Neuronum Node that publicly streams data

### **Create a public Stream Gateway**
1. Visit: https://neuronum.net/createSTX
2. Enter a short Stream Description (e.g. Test Stream)
3. Write "public" into the Partner Cell list
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

### **Connect your Node to Neuronum**
```sh
neuronum connect-node
```

### **NODE.md File**
The `NODE.md` file provides guidelines for interacting with your Node's data gateways.  
Add markdown content to structure your instructions, then update your Node with:

```sh
neuronum update-node
```