### **node_sync_stream**
Set up a Neuronum Node that synchronizes stream data in real time

### **Explore Neuronum Stream Gateways**
1. Visit: https://neuronum.net/streams
2. Copy a Stream ID (id::stx)

### **Connect your Neuronum Cell**
```sh
neuronum connect-cell
```

### **Initialize your Node with Stream template**
```sh
neuronum init-node --sync id::stx       # place your copied Stream ID here
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