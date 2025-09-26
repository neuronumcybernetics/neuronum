<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum: The E2E Web Engine</h4>

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

------------------

### **A Getting Started into the Neuronum Network**
In this brief getting started guide, you will:
- [Learn about Neuronum](#about-neuronum)
- [Connect to the Network](#connect-to-neuronum)
- [Build a Neuronum Node](#build-on-neuronum)
- [Interact with your Node](#interact-with-your-node)

------------------

### **About Neuronum**
Neuronum is a real-time web engine designed for developers to build E2E-native apps and services in minutes using high-level Python

### **Tools & Features**
- Cell: Account to interact with Neuronum
- Nodes: Apps & Services built on Neuronum
- Browser: Web Browser built on Neuronum -> [build from source](https://github.com/neuronumcybernetics/neuronum_browser)

### Requirements
- Python >= 3.8

------------------

### **Connect To Neuronum**
Installation (optional but recommended: create a virtual environment)
```sh
pip install neuronum
```

Create your Cell:
```sh
neuronum create-cell
```

or

Connect your Cell:
```sh
neuronum connect-cell
```

------------------


### **Build On Neuronum** 
To get started, initialize a new Node with the command below. 
```sh
neuronum init-node
```

This command will prompt you for a description (e.g. App) and will create a new directory named "App_<your_node_id>" with the necessary files to run your Node

Change into Node folder
```sh
cd  App_<your_node_id>
```

Start your Node:
```sh
neuronum start-node
```

------------------

### **Interact with your Node**

The **Neuronum Browser** is an open source E2E web browser that allows you to interact with your nodes -> [build from source](https://github.com/neuronumcybernetics/neuronum_browser)