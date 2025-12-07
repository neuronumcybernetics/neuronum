<h1 align="center">
  <img src="https://neuronum.net/static/neuronum.svg" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum Tools Library</h4>

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

### **Getting Started**
In this brief getting started guide, you will:
- [Learn about Neuronum Tools](#about-neuronum-tools)
- [Connect to Neuronum](#connect-to-neuronum)
- [Initialize a Tool](#initialize-a-tool)
- [Update a Tool](#update-a-tool)
- [Delete a Tool](#delete-a-tool)

------------------

### **About Neuronum Tools**
Neuronum Tools serve as plug and play Servers/Applications that allow ceLLai to connect to external data sources and systems. Neuronum Tools follow standardized MCP (Model Context Protocol) guidelines. 

### Requirements
- Python >= 3.8

------------------

### **Connect To Neuronum**
**Installation** (optional but recommended: create a virtual environment)
```sh
pip install neuronum
```

Create your Cell (your secure identity):
```sh
neuronum create-cell
```

or

Connect an existing Cell (your secure identity):
```sh
neuronum connect-cell
```

------------------


### **Initialize a Tool** 
```sh
neuronum init-tool
```
You will be prompted to enter a tool name and description (e.g., "Test Tool" and "A simple test tool"). This will create a new folder named using the format: `Tool Name_ToolID` (e.g., `Test Tool_019ac60e-cccc-7af5-b087-f6fcf1ba1299`)

This folder will contain 2 files:
1. **tool.config** - Configuration and metadata for your tool
2. **tool.py** - Your Tool/MCP server implementation

**Example tool.config:**
```config
{
  "tool_meta": {
    "tool_id": "019ac60e-cccc-7af5-b087-f6fcf1ba1299",
    "version": "1.0.0",
    "name": "Test Tool",
    "description": "A simple test tool",
    "audience": "private",
    "logo": "https://neuronum.net/static/logo_new.png"
  },
  "legals": {
    "terms": "https://url_to_your/terms",
    "privacy_policy": "https://url_to_your/privacy_policy"
  },
  "requirements": [],
  "variables": []
}
```

**Example tool.py:**
```python
from mcp.server.fastmcp import FastMCP

# Create server instance
mcp = FastMCP("simple-example")

@mcp.tool()
def echo(message: str) -> str:
    """Echo back a message"""
    return f"Echo: {message}"

if __name__ == "__main__":
    mcp.run()
    asyncio.run(main())
```


### **Update a Tool**
After modifying your `tool.config` or `tool.py` files, submit the updates using:
```sh
neuronum update-tool
```

### **Delete a Tool**
To remove a tool from Neuronum:
```sh
neuronum delete-tool
```
