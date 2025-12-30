<h1 align="center">
  <img src="https://neuronum.net/static/logo_new.png" alt="Neuronum" width="80">
</h1>
<h4 align="center">Neuronum SDK</h4>

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


### **About the Neuronum SDK**
The Neuronum SDK provides everything you need to setup your favorite AI model as self-hosted agentic backend. It includes the [Neuronum Server](#neuronum-server), an open source agent-wrapper that transforms your model into an executable assistant that can be managed and called with the [Neuronum Client API](#neuronum-client-api) and the [Neuronum Tools CLI](#neuronum-tools-cli) to develop and publish MCP-compliant Tools that can be installed locally on your [Neuronum Server](#neuronum-server)

> **Protocol Note:** The Neuronum SDK is powered by an end-to-end encrypted communication protocol based on public/private key pairs derived from a randomly generated 12-word mnemonic. All data is relayed through neuronum.net, providing secure communication without the need to set up public web servers or expose your infrastructure to the public internet.

> ⚠️ **Development Status:** The Neuronum SDK is currently in early stages of development and is **not production-ready**. It is intended for development, testing, and experimental purposes only. Do not use in production environments or for critical applications.

------------------

### **Requirements**
- Python >= 3.8
- CUDA-compatible GPU (for Neuronum Server)
- CUDA Toolkit (for Neuronum Server)

------------------

### **Table of Contents**
In this programmers guide, you will learn how to:
- [Connect to the Neuronum Network](#connect-to-neuronum)
- [Deploy a Model with Neuronum Server](#neuronum-server)
- [Call your Agent with the Neuronum Client API](#neuronum-client-api)
- [Create & Manage a Custom Tool with the Neuronum Tools CLI](#neuronum-tools-cli)

------------------

### **Connect To Neuronum**
**Installation**

Create and activate a virtual environment:
```sh
python3 -m venv ~/neuronum-venv
source ~/neuronum-venv/bin/activate
```

Install the Neuronum SDK:
```sh
pip install neuronum==2025.12.0.dev11
```

> **Note:** Always activate this virtual environment (`source ~/neuronum-venv/bin/activate`) before running any `neuronum` commands.

**Create a Neuronum Cell**
<br>The Neuronum Cell is your secure identity to interact with the Network
```sh
neuronum create-cell
```

**Connect your Cell**
```sh
neuronum connect-cell
```

------------------

### **Neuronum Server**
Neuronum Server is an agent-wrapper that transforms your model into an agentic backend server that can interact with the [Neuronum Client API](#neuronum-client-api) and installed tools

------------------

**Start the Server**

```sh
neuronum start-server
```

This command will:
- Clone the neuronum-server repository (if not already present)
- Create a Python virtual environment
- Install all dependencies (vLLM, PyTorch, etc.)
- Start the vLLM server in the background
- Launch the Neuronum Server

**Check Server Status**

```sh
neuronum status
```

This will show if the Neuronum Server and vLLM Server are currently running with their PIDs.

**Viewing Logs**

```sh
tail -f neuronum-server/server.log
tail -f neuronum-server/vllm_server.log
```

**Stopping the Server**

```sh
neuronum stop-server
```

**What the Server Does**

Once running, the server will:
- Connect to the Neuronum network using your Cell credentials
- Initialize a local SQLite database for conversation memory and knowledge storage
- Auto-discover and launch any MCP servers in the `tools/` directory
- Process messages from clients via the Neuronum network
- Execute scheduled tasks defined in the `tasks/` directory

**Server Configuration**

The server can be customized by editing the `neuronum-server/server.config` file. Here are the available options:

**File Paths:**
```python
LOG_FILE = "server.log"              # Server log file location
DB_PATH = "agent_memory.db"          # SQLite database for conversations and knowledge
TASKS_DIR = "./tasks"                # Directory for scheduled tasks
```

**Model Configuration:**
```python
MODEL_MAX_TOKENS = 512               # Maximum tokens in responses (higher = longer answers)
MODEL_TEMPERATURE = 0.3              # Creativity (0.0 = deterministic, 1.0 = creative)
MODEL_TOP_P = 0.85                   # Nucleus sampling (lower = more predictable)
```

**vLLM Server:**
```python
VLLM_MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"  # Model to load
                                               # Examples: "Qwen/Qwen2.5-1.5B-Instruct",
                                               #           "meta-llama/Llama-3.2-3B-Instruct"
VLLM_HOST = "127.0.0.1"              # Server host (127.0.0.1 = local only)
VLLM_PORT = 8000                     # Server port
VLLM_API_BASE = "http://127.0.0.1:8000/v1"  # Full API URL
```

**Conversation & Knowledge:**
```python
CONVERSATION_HISTORY_LIMIT = 10      # Recent messages to include in context
KNOWLEDGE_RETRIEVAL_LIMIT = 5        # Max knowledge chunks to retrieve
FTS5_STOPWORDS = {...}               # Words to exclude from knowledge search
```

After modifying the configuration, restart the server for changes to take effect:
```sh
neuronum stop-server
neuronum start-server
```

------------------


### **Neuronum Client API**
**Manage and call your Agent with the Neuronum Client API using different message types**

You can interact with your server using either the CLI chat client or the Python API:

**Quick Start - CLI Chat Client**
```sh
# Interactive chat mode
neuronum open-chat

# Single prompt mode
neuronum open-chat "What is the weather today?"
```

**Python API**
```python
import asyncio
from neuronum import Cell

async def main():

    async with Cell() as cell:

        # ============================================
        # Example 1: Send a prompt to your Agent
        # ============================================
        prompt_data = {
            "type": "prompt",
            "prompt": "Explain what a black hole is in one sentence"
        }
        tx_response = await cell.activate_tx(prompt_data)
        print(tx_response)

        # ============================================
        # Example 2: Call a Tool with natural language
        # ============================================
        tool_call_data = {
            "type": "call_tool",
            "tool_id": "your-tool-id",  # The tool you want to use
            "prompt": "Send an email to john@example.com with subject 'Meeting' and body 'See you at 3pm'"
        }
        tx_response = await cell.activate_tx(tool_call_data)
        print(tx_response)

        # ============================================
        # Example 3: Knowledge Management
        # ============================================

        # Add knowledge to agent's database
        add_knowledge_data = {
            "type": "add_knowledge",
            "knowledge_topic": "Company Policy",
            "knowledge_data": "Our company operates from 9 AM to 5 PM Monday through Friday."
        }
        tx_response = await cell.activate_tx(add_knowledge_data)

        # Update existing knowledge
        update_knowledge_data = {
            "type": "update_knowledge",
            "knowledge_id": "12345",  # ID from previous add
            "knowledge_data": "Updated: Company operates 8 AM to 6 PM Monday through Friday."
        }
        tx_response = await cell.activate_tx(update_knowledge_data)

        # Fetch all knowledge
        fetch_data = {"type": "fetch_all_knowledge"}
        knowledge_list = await cell.activate_tx(fetch_data)
        print(knowledge_list)

        # Delete knowledge
        delete_knowledge_data = {
            "type": "delete_knowledge",
            "knowledge_id": "12345"
        }
        tx_response = await cell.activate_tx(delete_knowledge_data)

        # ============================================
        # Example 4: Tool Management
        # ============================================

        # List all available tools on Neuronum network
        available_tools = await cell.list_tools()
        print(available_tools)
        # Returns list of tools with metadata: [{"tool_id": "...", "name": "...", "description": "..."}, ...]

        # Get all installed tools and tasks on your agent
        get_tools_data = {"type": "get_tools"}
        tools_info = await cell.activate_tx(get_tools_data)
        print(tools_info)

        # Add a tool (requires tool to be published)
        # Use stream() instead of activate_tx() to listen for agent restart
        add_tool_data = {
            "type": "add_tool",
            "tool_id": "019ac60e-cccc-7af5-b087-f6fcf1ba1299"
        }
        await cell.stream(add_tool_data)
        # Agent will restart and send "ping" when ready

        # Delete a tool
        delete_tool_data = {
            "type": "delete_tool",
            "tool_id": "019ac60e-cccc-7af5-b087-f6fcf1ba1299"
        }
        await cell.stream(delete_tool_data)

        # ============================================
        # Example 5: Task Scheduling (Automated Workflows)
        # ============================================

        # Add a scheduled task
        add_task_data = {
            "type": "add_task",
            "name": "Daily Report",
            "description": "Send daily summary email",
            "tool_id": "email-tool-id",
            "function_name": "send_email",
            "input_type": "prompt",  # or "static"
            "input_data": "Send daily summary to manager@company.com",
            "schedule": "weekdays@1704067200,1704153600"  # Days@Unix timestamps
        }
        await cell.stream(add_task_data)

        # Delete a task
        delete_task_data = {
            "type": "delete_task",
            "task_id": "task-uuid-here"
        }
        await cell.stream(delete_task_data)

        # ============================================
        # Example 6: Agent Status & Logs
        # ============================================

        # Check if agent is running
        status_data = {"type": "get_agent_status"}
        status = await cell.activate_tx(status_data)
        print(status)  # Returns: {"json": "agent running"}

        # Download agent logs
        log_data = {"type": "download_log"}
        logs = await cell.activate_tx(log_data)
        print(logs["json"]["log"])  # Full log content

if __name__ == '__main__':
    asyncio.run(main())
```

----------------------

### **Neuronum Tools CLI**
Neuronum Tools are MCP-compliant (Model Context Protocol) plugins that can be installed on the Neuronum Server and extend your Agent's functionality, enabling it to interact with external data sources and your system.

> **Tools Note:** Tools are not stored encrypted on neuronum.net. **Do not include credentials, API keys, secure tokens, passwords, or any sensitive data directly in your tool code.** Use environment variables or the `variables` configuration field (when available) to handle sensitive information securely. 

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
```

### **Tool Configuration Fields**

**audience**
- Controls who can install and use your tool
- Options:
  - `"private"` - Only you can use this tool
  - `"public"` - Anyone on the Neuronum network can install this tool
  - `"id::cell"` - Share with specific cells (comma-separated list)

Examples:
```json
"audience": "private"
```
```json
"audience": "public"
```
```json
"audience": "acme::cell, community::cell, business::cell"
```

**requirements**
- List of Python packages your tool needs
- Automatically installed by the Neuronum Server when the tool is added
- Use the same format as pip requirements (e.g., `"requests"`, `"pandas>=2.0.0"`)

Example:
```json
"requirements": [
  "requests",
  "pandas>=2.0.0",
  "openai==1.12.0"
]
```

**variables**
- List of variable names that users need to provide when installing your tool
- When installing the tool, users are prompted to manually set each variable one by one
- Values are sent encrypted to the server and automatically placed into your tool.py code
- **Important:** You don't need to add lines like `API_TOKEN = "value"` to your tool.py - the server automatically sets these variables based on user inputs

Example in tool.config:
```json
"variables": [
  "API_TOKEN",
  "DB_PASSWORD",
  "SERVICE_URL"
]
```

**How to use variables in your tool.py:**

❌ **Wrong - Don't hardcode sensitive values:**
```python
from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP("api-tool")

# DON'T DO THIS - Never hardcode credentials!
API_TOKEN = "sk-1234567890abcdef"  # This will be exposed in your tool code!

@mcp.tool()
def call_api(endpoint: str) -> str:
    """Call external API"""
    response = requests.get(f"https://api.example.com/{endpoint}",
                           headers={"Authorization": f"Bearer {API_TOKEN}"})
    return response.text
```

✅ **Correct - Use variables (server auto-injects values):**

First, declare the variable in your tool.config:
```json
{
  ...
  "requirements": ["requests"],
  "variables": ["API_TOKEN"]
}
```

Then use it in your tool.py without defining it:
```python
from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP("api-tool")

# The server automatically sets API_TOKEN based on user input during installation
# You just use it directly - no need to define it!

@mcp.tool()
def call_api(endpoint: str) -> str:
    """Call external API"""
    response = requests.get(f"https://api.example.com/{endpoint}",
                           headers={"Authorization": f"Bearer {API_TOKEN}"})
    return response.text
```

> **Note:** This feature is only available when using the official Neuronum client.

### **Update a Tool**
After modifying your `tool.config` or `tool.py` files, submit the updates using:
```sh
neuronum update-tool
```

### **Delete a Tool**
```sh
neuronum delete-tool
```


