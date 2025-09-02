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
Neuronum Nodes refer to the software and hardware systems that host Neuronum data gateways. In practice, the Nodes can connect and exchange data with one another through these data gateways, forming a distributed yet highly interconnected network of applications, services, and devices.

**!NOTE!**: While the data flow between Nodes is fully serverless and managed by Neuronum, participating in the Network requires a physical or virtual Node capable of running Python 3.8, along with the ability to install and execute Neuronum dependencies.

### Node App
The simplest way to set up a Neuronum Node is to use the CLI:
```sh
neuronum init-node
```

This command generates a new folder in your working directory. A Neuronum Node App is designed to **receive**, **process**, and **respond to requests**—making it a powerful starting point for interacting with the Neuronum Network.

To dive deeper into Neuronum App development, visit & build with [Node Examples](https://github.com/neuronumcybernetics/neuronum/tree/main/features/nodes/examples)


### **.env File**
The `.env` file securely stores your Cell credentials, which are required to connect to and interact with the Neuronum Network.

### **app.py File**
The `app.py` file contains the core logic of your Node (App). It handles Cell requests, push notifications, database interactions, streaming data, and other backend operations.

### **ping.html File**
The `ping.html` file provides a basic HTML-based response

### **NODE.md File**
The `NODE.md` file serves as the public-facing documentation for your Node. It includes instructions for developers and users on how to interact with your Node effectively.

### **config.json File**
Neuronum Nodes are not hosted on traditional web servers (e.g., NGINX) and do not have static domain names (e.g., www.neuronum.net). To address this, the `config.json` file provides a lightweight, standardized way to inform the Network how to handle incoming data. It defines the Node’s data gateways and includes additional metadata such as the App Name, Terms of Use, and Privacy Policy.


### **Node-CLI-Commands**
Initialize a Node:
```sh
neuronum init-node
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