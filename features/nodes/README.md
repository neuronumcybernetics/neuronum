<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum Nodes: Soft- and Hardware Components hosting Neuronum Data Gateways</h4>

<p align="center">
  <a href="https://neuronum.net">
    <img src="https://img.shields.io/badge/Website-Neuronum-blue" alt="Website">
  </a>
  <a href="https://github.com/neuronumcybernetics/neuronum">
    <img src="https://img.shields.io/badge/Docs-Read%20now-green" alt="Documentation">
  </a>
  <a href="https://pypi.org/project/neuronum/">
    <img src="https://img.shields.io/pypi/v/neuronum.svg" alt="PyPI Version">
  </a><br>
  <img src="https://img.shields.io/badge/Python-3.8%2B-yellow" alt="Python Version">
  <a href="https://github.com/neuronumcybernetics/neuronum/blob/main/LICENSE.md">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  </a>
</p>

---

### **About Neuronum Nodes**
Neuronum Nodes refer to the software and hardware systems that host Neuronum data gateways. In practice, these Nodes can connect and exchange data with one another, forming a distributed yet highly interconnected network of applications, services, and devices.

**!NOTE!**: While the data flow between Nodes is fully serverless and managed by Neuronum, participating in the Network requires a physical or virtual Node capable of running Python 3.8, along with the ability to install and execute Neuronum dependencies.


### **Node-CLI-Commands**
Initialize a Node (default template):
```sh
neuronum init-node                      # create a Node with default template
```

Initialize a Node (app template):
```sh
neuronum init-node --app                # create a Node with app template
```

Initialize a Node (sync template):
```sh
neuronum init-node --sync id::stx       # create a Node with sync template
```

Initialize a Node (stream template):
```sh
neuronum init-node --stream id::stx     # create a Node with stream template
```

Start your Node:
```sh
neuronum start-node                     # start your Node
```
or

```sh
neuronum start-node --d                 # start your Node in "detached" mode
```

Restart your Node:
```sh
neuronum restart-node                   # restart your Node
```
or

```sh
neuronum restart-node --d               # restart your Node in "detached" mode
```

Stop your Node:
```sh
neuronum stop-node                      # stop your Node
```

Check Node status:
```sh
neuronum check-node                     # check Node status
```

Update your Node:
```sh
neuronum update-node                    # update your Node
```

Delete your Node:
```sh
neuronum delete-node                    # delete your Node
```

### **The NODE.md File**
Because most Neuronum Nodes aren't hosted via traditional web servers (e.g., NGINX) and lack static domain addresses (e.g., www.neuronum.net), they require a lightweight, standardized method to communicate how their data gateways can be interacted with. The NODE.md file serves this purpose by providing structured information about the Node’s available services

#### NODE.md Example:
```markdown
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

### **Neuronum Node Examples**
- node_public_stream: Set up a Neuronum Node that publicly streams data
- node_sync_stream: Set up a Neuronum Node that synchronizes stream data in real time
- node_private_stream: Set up a Neuronum Node that privately streams data
- node_simple_app: Set up a Neuronum Node app to receive requests and send responses


These Examples assume you've already installed the latest version of Neuronum and created your Neuronum Cell.