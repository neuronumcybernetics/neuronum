<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum Cell: Your Client to Connect and Interact with Neuronum</h4>

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

### **About Neuronum Cell**
Your Neuronum Cell is an unique Client to securely connect and interact with Neuronum

### **Set Cell Connection (Code-Based)**
```python
cell = neuronum.Cell(
    host="host",              # Cell host
    password="password",      # Cell password
    network="neuronum.net",   # Cell network -> neuronum.net
    synapse="synapse"         # Cell synapse (auth token)
)
```

### **Cell-CLI-Commands**
Create your Cell:
```sh
neuronum create-cell          # create Cell / Cell type / Cell network 
```

Connect your Cell:
```sh
neuronum connect-cell         # connect Cell
```

View your Cell:
```sh
neuronum view-cell            # view connected Cell
```

Disconnect your Cell:
```sh
neuronum disconnect-cell      # disconnect Cell
```

Delete your Cell:
```sh
neuronum delete-cell          # delete Cell
```