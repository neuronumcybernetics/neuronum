<h1 align="center">
  <img src="https://neuronum.net/static/logo_new.png" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum ceLL SDK</h4>

<p align="center">
  <a href="https://neuronum.net">
    <img src="https://img.shields.io/badge/Website-Neuronum-blue" alt="Website">
  </a>
  <a href="https://github.com/neuronumcybernetics/cell-sdk-python">
    <img src="https://img.shields.io/badge/Docs-Read%20now-green" alt="Documentation">
  </a>
  <a href="https://pypi.org/project/neuronum/">
    <img src="https://img.shields.io/pypi/v/neuronum.svg" alt="PyPI Version">
  </a><br>
  <img src="https://img.shields.io/badge/Python-3.8%2B-yellow" alt="Python Version">
  <a href="https://github.com/neuronumcybernetics/cell-sdk-python/blob/main/LICENSE.md">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  </a>
</p>

------------------

### **A Getting Started into the Neuronum ceLL SDK**
In this brief getting started guide, you will:
- [Learn about the Neuronum ceLL SDK](#about-cell-sdk)
- [Connect your ID to Neuronum](#connect-to-neuronum)
- [Create & Manage A custom ceLL Tool](#create-a-tool)
- [Integrate the ceLL API to call your Server](#integrate-cell-api)

------------------

### **About ceLL SDK**
The ceLL SDK is the official Python ecosystem to develop and publish custom Tools for the [Neuronum ceLL Server](https://neuronum.net/) and lets you integrate the ceLL API to interact with your Agent from existing projects

### Requirements
- Python >= 3.8
- [Neuronum ceLL Server (Hardware)](https://neuronum.net/) 

------------------

### **Connect To Neuronum**
**Installation**
```sh
pip install neuronum
```


**Connect an existing Cell (your secure identity)**
```sh
neuronum connect-cell
```

------------------

### **Create A Tool**
Neuronum ceLL Tools are MCP-compliant (Model Context Protocol ) plugins that extend your Agent's (Neuronum ceLL) functionality, enabling it to interact with external data sources and systems.

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
```sh
neuronum delete-tool
```



### **Integrate ceLL API** 
**Send a simple prompt to your ceLL Server using Neuronum Transmitters (TX)**
```python
import asyncio
from neuronum import Cell

async def main():
    
    async with Cell() as cell: 

        # Build the data payload
        data = {
          "type": "prompt",
          "prompt": "Explain what a black hole is in one sentence"
        }

        # Use activate_tx() if you expect a response from your ceLL Server
        tx_response = await cell.activate_tx(data)
        print(tx_response)

        # Stream data to your ceLL Server (no response expected)
        await cell.stream(data)

if __name__ == '__main__':
    asyncio.run(main())
```
