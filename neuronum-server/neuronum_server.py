import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import sys
import textwrap
from openai import OpenAI
import aiosqlite
from typing import List, Tuple
import re
from neuronum import Cell
import hashlib
import logging
import subprocess
import json

import tool_registry
import task_executor
from config import (
    HOST,
    PRIVATE_KEY,
    PUBLIC_KEY,
    LOG_FILE,
    DB_PATH,
    TASKS_DIR,
    MODEL_MAX_TOKENS,
    MODEL_TEMPERATURE,
    MODEL_TOP_P,
    VLLM_MODEL_NAME,
    VLLM_HOST,
    VLLM_PORT,
    VLLM_API_BASE,
    CONVERSATION_HISTORY_LIMIT,
    KNOWLEDGE_RETRIEVAL_LIMIT,
    FTS5_STOPWORDS
)

active_tasks = {}

# Logging Setup

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# System Prompts

RAG_PROMPT_TEMPLATE = textwrap.dedent("""
    You are a helpful assistant. When context is provided in the user's message, you MUST use it as the source of truth.
    The provided context is always correct and up-to-date. Trust it completely.
    Never question or contradict the context - simply use it to answer the question directly.
    Do not add disclaimers or mention your own knowledge when context is provided.
    If no context is provided, answer based on your knowledge.
    Be concise and clear.
""")

FILE_RAG_PROMPT_TEMPLATE = textwrap.dedent("""
    Answer the following prompt with the given context:

    **Prompt:**
    {prompt}

    **CONTEXT:**
    {context}
    ---
""")

# Database Functions

async def enable_wal(db_path=DB_PATH):
    """Enable WAL mode for better database concurrency"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.commit()
        logging.info("WAL mode enabled.")

async def init_db(db_path=DB_PATH):
    """Initialize memory and FTS5 knowledge tables"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                role TEXT,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge USING fts5(
                knowledge_id,
                topic,
                content,
                tokenize='porter unicode61'
            )
        ''')
        await db.commit()
        logging.info("Database initialized with FTS5 knowledge table.")

async def store_message(user, role, message, db_path=DB_PATH):
    """Store message to memory table for conversation history"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO memory (user, role, message) VALUES (?, ?, ?)",
            (user, role, message)
        )
        await db.commit()

async def store_action(user, action_type: str, action_details: str, db_path=DB_PATH):
    """Store user action as a system message for conversation context"""
    action_message = f"[Action: {action_type}] {action_details}"
    await store_message(user, "system", action_message, db_path)

async def fetch_latest_messages(user, limit=CONVERSATION_HISTORY_LIMIT, db_path=DB_PATH) -> List[Tuple[str, str]]:
    """Fetch latest N messages for conversation history"""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT role, message FROM memory WHERE user = ? ORDER BY id DESC LIMIT ?",
            (user, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return list(reversed(rows))

def validate_tool_parameters(parameters: dict, input_schema: dict) -> tuple[bool, str]:
    """Validate parameters against JSON schema and return (is_valid, error_message) tuple"""
    if not input_schema:
        return True, ""

    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    for req_param in required:
        if req_param not in parameters:
            return False, f"Missing required parameter: '{req_param}'"

    for param_name, param_value in parameters.items():
        if param_name not in properties:
            continue

        param_schema = properties[param_name]
        expected_type = param_schema.get("type", "string")

        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type and not isinstance(param_value, expected_python_type):
            return False, (
                f"Parameter '{param_name}' has wrong type. "
                f"Expected {expected_type}, got {type(param_value).__name__}"
            )

        if "enum" in param_schema:
            if param_value not in param_schema["enum"]:
                return False, (
                    f"Parameter '{param_name}' value '{param_value}' not in allowed values: "
                    f"{param_schema['enum']}"
                )

        if expected_type == "array" and "items" in param_schema:
            item_type = param_schema["items"].get("type")
            if item_type and item_type in type_map:
                item_python_type = type_map[item_type]
                for idx, item in enumerate(param_value):
                    if not isinstance(item, item_python_type):
                        return False, (
                            f"Parameter '{param_name}' array item at index {idx} has wrong type. "
                            f"Expected {item_type}, got {type(item).__name__}"
                        )

    return True, ""


async def add_knowledge_entry(topic: str, data: str, db_path=DB_PATH):
    """Add knowledge entry to FTS5 table with generated ID"""
    combined = f"{topic}:{data}"
    knowledge_id = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO knowledge (knowledge_id, topic, content) VALUES (?, ?, ?)",
            (knowledge_id, topic, data)
        )
        await db.commit()

async def delete_knowledge_entry(knowledge_id: str, db_path=DB_PATH):
    """Delete knowledge entry from FTS5 table using knowledge_id"""
    if not knowledge_id:
        logging.warning("Attempted to delete knowledge with a missing knowledge_id.")
        return False
        
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "DELETE FROM knowledge WHERE knowledge_id = ?",
            (knowledge_id,)
        )
        await db.commit()
        
        deleted_count = db.total_changes
        
        if deleted_count > 0:
            logging.info(f"Knowledge entry with ID '{knowledge_id}' deleted successfully.")
            return True
        else:
            logging.warning(f"Knowledge entry with ID '{knowledge_id}' not found or not deleted.")
            return False

async def update_knowledge_entry(knowledge_id: str, new_data: str, db_path=DB_PATH) -> bool:
    """Update content of existing FTS5 entry"""
    if not knowledge_id or not new_data:
        logging.warning("Attempted to update knowledge with a missing knowledge_id or new_data.")
        return False
        
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE knowledge SET content = ? WHERE knowledge_id = ?",
            (new_data, knowledge_id)
        )
        await db.commit()
        
        updated_count = db.total_changes
        
        if updated_count > 0:
            logging.info(f"Knowledge entry with ID '{knowledge_id}' updated successfully.")
            return True
        else:
            logging.warning(f"Knowledge entry with ID '{knowledge_id}' not found or not updated.")
            return False

async def retrieve_knowledge(user_query: str, db_path=DB_PATH) -> str:
    """Retrieve relevant knowledge using FTS5 keyword search"""
    tokens = re.findall(r"\b\w+\b", user_query.lower())

    ENHANCED_STOPWORDS = FTS5_STOPWORDS | {"or", "and", "not", "near"}
    keywords = [t for t in tokens if t not in ENHANCED_STOPWORDS]

    if not keywords:
        return "No specific business knowledge found in the database."

    keywords = keywords[:10]
    quoted_keywords = [f'"{keyword}"' for keyword in keywords]
    search_expr = " OR ".join(quoted_keywords)

    async with aiosqlite.connect(db_path) as db:
        try:
            query = """
                SELECT content, bm25(knowledge) as score
                FROM knowledge
                WHERE knowledge MATCH ?
                ORDER BY score
                LIMIT ?
            """
            async with db.execute(query, (search_expr, KNOWLEDGE_RETRIEVAL_LIMIT)) as cursor:
                rows = await cursor.fetchall()

                if rows:
                    knowledge_chunks = [row[0] for row in rows]
                    return "\n---\n".join(knowledge_chunks)
                else:
                    return "No specific business knowledge found in the database."
        except Exception as e:
            logging.warning(f"Knowledge retrieval error: {str(e)[:100]}")
            return "Knowledge retrieval temporarily unavailable."

# OpenAI Client Configuration
try:
    logging.info(f"Connecting to vLLM API server at {VLLM_API_BASE}")

    client = OpenAI(
        base_url=VLLM_API_BASE,
        api_key="EMPTY"
    )

    logging.info(f"OpenAI client initialized for vLLM server")

except Exception as e:
    logging.error(f"Error initializing OpenAI client: {e}")
    logging.error("Make sure vLLM is running: python -m vllm.entrypoints.openai.api_server --model <model-name>")
    sys.exit(1)

def create_chat_completion(messages, max_tokens=MODEL_MAX_TOKENS, temperature=MODEL_TEMPERATURE):
    """Generate chat completion using OpenAI-compatible API"""
    try:
        response = client.chat.completions.create(
            model=VLLM_MODEL_NAME,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=MODEL_TOP_P,
        )

        return {
            'choices': [
                {
                    'message': {
                        'content': response.choices[0].message.content
                    }
                }
            ]
        }

    except Exception as e:
        logging.error(f"Error in create_chat_completion: {e}")
        logging.error("Make sure vLLM is running at http://127.0.0.1:8000")
        raise

async def fetch_all_knowledge(db_path=DB_PATH) -> List[dict]:
    """Fetch all knowledge entries from FTS5 table"""
    async with aiosqlite.connect(db_path) as db:
        query = "SELECT knowledge_id, topic, content FROM knowledge ORDER BY knowledge_id ASC"
        
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            
            knowledge_list = []
            for row in rows:
                knowledge_list.append({
                    "knowledge_id": row[0],
                    "topic": row[1],
                    "content": row[2]
                })
            
            return knowledge_list
        
async def erase_data(db_path=DB_PATH):
    """Erase all data from database and clear log file"""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("DELETE FROM memory")
            logging.info("All conversation history deleted from memory table.")

            await db.execute("DELETE FROM knowledge")
            logging.info("All knowledge entries deleted from knowledge table.")

            await db.commit()

        with open(LOG_FILE, 'w') as f:
            f.write('')
        logging.info("Log file cleared.")

        logging.info("All data erased successfully.")
        return True

    except Exception as e:
        logging.error(f"Error during data erasure: {e}")
        return False


async def get_model_answer(user_id: str, user_query: str, file: bool = False, file_content: str = "") -> str:
    """Core RAG function for generating answers with context"""
    loop = asyncio.get_running_loop()

    if file:
        augmented_system_prompt = FILE_RAG_PROMPT_TEMPLATE.format(prompt=user_query,context=file_content)

        messages = [
            {"role": "user", "content": augmented_system_prompt},
        ]

        logging.info(f"[Messages for Agent]: {messages}")

        def generate_text():
            response = create_chat_completion(
                messages=messages,
                max_tokens=MODEL_MAX_TOKENS,
                temperature=MODEL_TEMPERATURE
            )
            content = response['choices'][0]['message']['content']
            return content.strip()

        answer = await loop.run_in_executor(None, generate_text)

        full_prompt = user_query + file_content

        if answer:
            await store_message(user_id, "user", full_prompt)
            await store_message(user_id, "assistant", answer)
        else:
            logging.warning("Warning: Model returned empty response, not storing in conversation history")

        return answer
    else:
        context = await retrieve_knowledge(user_query)
        augmented_system_prompt = RAG_PROMPT_TEMPLATE
        history = await fetch_latest_messages(user_id, limit=5)

        messages = [
            {"role": "system", "content": augmented_system_prompt},
        ]

        for role, message in history:
            messages.append({"role": role, "content": message})

        if context != "No specific business knowledge found in the database.":
            augmented_user_query = f"""{augmented_system_prompt}

Based on the following context, answer the question:

CONTEXT:
{context}

QUESTION:
{user_query}"""
        else:
            augmented_user_query = f"""{augmented_system_prompt}

{user_query}"""

        messages.append({"role": "user", "content": augmented_user_query})

        logging.info(f"[Messages for Agent]: {messages}")

        def generate_text():
            response = create_chat_completion(
                messages=messages,
                max_tokens=MODEL_MAX_TOKENS,
                temperature=MODEL_TEMPERATURE
            )
            logging.info(f"[Raw LLM Response]: {response}")
            content = response['choices'][0]['message']['content']
            return content.strip()

        answer = await loop.run_in_executor(None, generate_text)

        if answer:
            await store_message(user_id, "user", user_query)
            await store_message(user_id, "assistant", answer)
        else:
            logging.warning("Warning: Model returned empty response, not storing in conversation history")

        return answer


async def convert_tool_result_to_natural_language(
    operator: str,
    user_prompt: str,
    tool_name: str,
    tool_result: dict
) -> str:
    """Convert structured tool result to natural language response"""
    loop = asyncio.get_running_loop()

    conversion_prompt = f"""You are a helpful assistant. A user asked: "{user_prompt}"

The system executed the tool "{tool_name}" and received this result:

{json.dumps(tool_result, indent=2)}

Convert this technical result into a natural, conversational response that directly answers the user's question.
Be concise and friendly. Focus on the key information the user needs.
If the result indicates an error, explain it clearly to the user.
Do not mention technical details like "tool execution" or "the system did X" or using phrases like "Here is a natural, conversational response" - just answer naturally as if you performed the action yourself."""

    messages = [
        {"role": "user", "content": conversion_prompt}
    ]

    logging.info(f"Converting tool result to natural language for tool: {tool_name}")

    def generate_text():
        response = create_chat_completion(
            messages=messages,
            max_tokens=MODEL_MAX_TOKENS,
            temperature=0.7  # Slightly higher temperature for more natural responses
        )
        content = response['choices'][0]['message']['content']
        return content.strip()

    natural_response = await loop.run_in_executor(None, generate_text)

    if natural_response:
        await store_message(operator, "user", user_prompt)
        await store_message(operator, "assistant", natural_response)

    return natural_response


# Infrastructure Setup

async def setup_infrastructure():
    """Initialize infrastructure for agent"""
    logging.info("Initializing system...")

async def initialize_database():
    """Initialize SQLite database with WAL mode"""
    await enable_wal()
    await init_db()

async def install_tool_requirements():
    """Install requirements from all .config files in tools directory"""
    try:
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )

        if not in_venv:
            logging.warning("Warning: Not running in a virtual environment. Skipping automatic package installation.")
            logging.warning("Warning: Please activate a virtual environment and manually install required packages.")
            return

        tools_dir = "./tools"

        if not os.path.exists(tools_dir):
            logging.info("No tools directory found, skipping requirements installation")
            return

        all_requirements = set()

        for filename in os.listdir(tools_dir):
            if filename.endswith(".config"):
                config_path = os.path.join(tools_dir, filename)

                try:
                    with open(config_path, 'r') as f:
                        config_content = f.read()
                        config_data = json.loads(config_content)

                    requirements = config_data.get("requirements", [])

                    if requirements:
                        for req in requirements:
                            all_requirements.add(req)
                        logging.info(f"Found {len(requirements)} requirement(s) in {filename}")

                except json.JSONDecodeError as e:
                    logging.warning(f"Failed to parse {filename}: {e}")
                except Exception as e:
                    logging.warning(f"Error reading {filename}: {e}")

        if not all_requirements:
            logging.info("No tool requirements found in config files")
            return

        logging.info(f"Installing {len(all_requirements)} package(s): {', '.join(all_requirements)}")

        for requirement in all_requirements:
            try:
                logging.info(f"Installing {requirement}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", requirement],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0:
                    logging.info(f"Successfully installed {requirement}")
                else:
                    logging.error(f"Error: Failed to install {requirement}: {result.stderr}")

            except subprocess.TimeoutExpired:
                logging.error(f"Error: Timeout while installing {requirement}")
            except Exception as e:
                logging.error(f"Error: Error installing {requirement}: {e}")

        logging.info("Tool requirements installation complete")

    except Exception as e:
        logging.error(f"Error in install_tool_requirements: {e}")
        import traceback
        logging.error(traceback.format_exc())


async def setup_cell_connection():
    """Establish connection as Neuronum Cell and return cell instance"""
    cell = Cell()

    if not cell.env.get("HOST"):
        logging.error("Error: No HOST found in Cell credentials. Please run 'neuronum create-cell' or 'neuronum connect-cell' first.")
        await cell.close()
        sys.exit(1)

    logging.info(f"Connected to Cell: {cell.env.get('HOST')}")
    return cell

# Message Handlers

async def send_cell_response(cell, transmitter_id: str, data: dict, public_key: str):
    """Send response back through cell"""
    await cell.tx_response(
        transmitter_id=transmitter_id,
        data=data,
        client_public_key_str=public_key
    )

async def handle_add_knowledge(cell, transmitter: dict):
    """Handle adding knowledge to database"""
    data = transmitter.get("data", {})
    knowledge_topic = data.get("knowledge_topic", None)
    knowledge_data = data.get("knowledge_data", None)
    operator = data.get("operator", "default_user")

    logging.info("Adding knowledge to database...")
    await add_knowledge_entry(knowledge_topic, knowledge_data)

    await store_action(
        operator,
        "add_knowledge",
        f"Added knowledge on topic '{knowledge_topic}': {knowledge_data[:100]}..." if len(knowledge_data) > 100 else f"Added knowledge on topic '{knowledge_topic}': {knowledge_data}"
    )

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge updated"},
        data.get("public_key", "")
    )

async def handle_get_status(cell, transmitter: dict):
    """Handle agent status request"""
    data = transmitter.get("data", {})
    logging.info("Checking Agent Status")

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "agent running"},
        data.get("public_key", "")
    )

async def handle_update_knowledge(cell, transmitter: dict):
    """Handle updating existing knowledge in database"""
    data = transmitter.get("data", {})
    knowledge_id = data.get("knowledge_id", None)
    knowledge_data = data.get("knowledge_data", None)
    operator = data.get("operator", "default_user")

    logging.info("Updating knowledge in database...")
    await update_knowledge_entry(knowledge_id, knowledge_data)

    await store_action(
        operator,
        "update_knowledge",
        f"Updated knowledge ID {knowledge_id}: {knowledge_data[:100]}..." if len(knowledge_data) > 100 else f"Updated knowledge ID {knowledge_id}: {knowledge_data}"
    )

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge updated"},
        data.get("public_key", "")
    )

async def handle_delete_knowledge(cell, transmitter: dict):
    """Handle deleting knowledge from database"""
    data = transmitter.get("data", {})
    knowledge_id = data.get("knowledge_id", None)
    operator = data.get("operator", "default_user")

    logging.info("Deleting knowledge from database...")
    await delete_knowledge_entry(knowledge_id)

    await store_action(
        operator,
        "delete_knowledge",
        f"Deleted knowledge entry with ID {knowledge_id}"
    )

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge deleted"},
        data.get("public_key", "")
    )

async def handle_fetch_knowledge(cell, transmitter: dict):
    """Handle fetching all knowledge from database"""
    data = transmitter.get("data", {})
    logging.info("Fetching all stored knowledge for inspection...")

    knowledge_list = await fetch_all_knowledge()
    logging.info(knowledge_list)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": knowledge_list},
        data.get("public_key", "")
    )

async def handle_download_log(cell, transmitter: dict):
    """Handle downloading agent log file and clear it after download"""
    data = transmitter.get("data", {})
    logging.info("Fetching log from server.log...")

    try:
        with open("server.log", "r") as f:
            agent_log = f.read()
        logging.info("Agent log fetched successfully")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"log": agent_log}},
            data.get("public_key", "")
        )

        with open("server.log", "w") as f:
            f.write('')
        logging.info("Agent log cleared after download")

    except Exception as e:
        agent_log = f"Error reading agent log: {e}"
        logging.error(agent_log)

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"log": agent_log}},
            data.get("public_key", "")
        )


async def handle_prompt(cell, transmitter: dict):
    """Handle user prompt and generate LLM response"""
    data = transmitter.get("data", {})
    prompt = data.get("prompt", "")
    file = data.get("file", False)
    file_content = data.get("file_content", "")

    logging.info(f"DEBUG - Data keys: {list(data.keys())}")
    logging.info(f"DEBUG - Has 'file' key: {'file' in data}")

    logging.info(f"[User]: {prompt}")
    operator = data.get("operator", "default_user")

    try:
        answer = await get_model_answer(operator, prompt, file, file_content)
        logging.info(f"[Agent]: {answer}")

        for handler in logging.getLogger().handlers:
            handler.flush()

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": answer},
            data.get("public_key", "")
        )

        logging.info("\n--- Test Console End ---")

        for handler in logging.getLogger().handlers:
            handler.flush()

    except Exception as e:
        logging.error(f"Error handling prompt: {e}")
        import traceback
        logging.error(traceback.format_exc())

        try:
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": f"Error processing request: {str(e)}"},
                data.get("public_key", "")
            )
        except Exception as send_error:
            logging.error(f"Failed to send error response: {send_error}")

async def handle_get_tools(cell, transmitter: dict):
    """Handle get tools request and return config data for each tool_id and all tasks"""
    data = transmitter.get("data", {})
    logging.info("Fetching all tool configs and tasks...")

    try:
        tools_dir = "./tools"
        tools_by_id = {}

        if os.path.exists(tools_dir):
            for filename in os.listdir(tools_dir):
                if filename.endswith(".config"):
                    tool_id = filename[:-7]
                    config_path = os.path.join(tools_dir, filename)

                    try:
                        with open(config_path, 'r') as f:
                            config_content = f.read()
                            config_json = json.loads(config_content)

                        tools_by_id[tool_id] = config_json

                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse config file {filename}: {e}")
                    except Exception as e:
                        logging.warning(f"Failed to read config file {filename}: {e}")

        logging.info(f"Retrieved {len(tools_by_id)} tool configs")

        tasks_list = []
        if os.path.exists(TASKS_DIR):
            for filename in os.listdir(TASKS_DIR):
                if filename.endswith(".json"):
                    task_path = os.path.join(TASKS_DIR, filename)

                    try:
                        with open(task_path, 'r') as f:
                            task_data = json.load(f)
                        tasks_list.append(task_data)

                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse task file {filename}: {e}")
                    except Exception as e:
                        logging.warning(f"Failed to read task file {filename}: {e}")

        logging.info(f"Retrieved {len(tasks_list)} tasks")

        response_data = {
            "tools": tools_by_id,
            "tasks": tasks_list
        }

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": response_data},
            data.get("public_key", "")
        )

    except Exception as e:
        logging.error(f"Error fetching tools and tasks: {e}")
        import traceback
        logging.error(traceback.format_exc())

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": str(e)}},
            data.get("public_key", "")
        )

async def handle_call_tool(cell, transmitter: dict):
    """Handle tool execution requests using AI-assisted tool selection"""
    data = transmitter.get("data", {})
    tool_id = data.get("tool_id") 
    user_prompt = data.get("prompt", "")
    operator = data.get("operator", "default_user")

    logging.info(f"Tool call requested - Tool ID: {tool_id}")
    logging.info(f"User prompt: {user_prompt}")

    try:
        history = await fetch_latest_messages(operator, limit=5)
        logging.info(f"Retrieved {len(history)} messages from conversation history")

        registry = await tool_registry.get_registry()
        available_tools = await registry.get_all_tools()

        if not tool_id:
            error_msg = "'tool_id' is required for tool execution"
            logging.error(error_msg)
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": error_msg},
                data.get("public_key", "")
            )
            return

        if tool_id:
            logging.info(f"AI-assisted mode: Filtering tools by tool_id '{tool_id}'")

            filtered_tools = [
                tool for tool in available_tools
                if tool.get("server") == tool_id or tool.get("id") == tool_id or tool_id in tool.get("name", "")
            ]

            if not filtered_tools:
                error_msg = f"No tools found for tool_id '{tool_id}'"
                logging.error(error_msg)
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": error_msg},
                    data.get("public_key", "")
                )
                return

            logging.info(f"Found {len(filtered_tools)} tools for tool_id '{tool_id}'")

            tool_info_list = []
            for tool in filtered_tools:
                input_schema = tool.get("inputSchema", {})
                properties = input_schema.get("properties", {})

                params_desc = []
                for param_name, param_def in properties.items():
                    params_desc.append(f"{param_name} ({param_def.get('type', 'string')}): {param_def.get('description', '')}")

                tool_info = f"""Tool: {tool['name']}
Description: {tool.get('description', 'No description')}
Parameters: {', '.join(params_desc) if params_desc else 'none'}"""
                tool_info_list.append(tool_info)

            function_call_prompt = f"""User request: "{user_prompt}"

Available tools from '{tool_id}':
{chr(10).join(tool_info_list)}

Select the most appropriate tool and extract all required parameters from the user request.
IMPORTANT: Use proper JSON types - numbers as numbers (not strings), booleans as true/false, strings as quoted text.

Respond with JSON in this exact format:
{{"tool_name": "selected_tool_name", "parameters": {{"string_param": "text", "number_param": 123, "boolean_param": true}}}}

If no parameters are needed, use an empty object: {{"tool_name": "selected_tool_name", "parameters": {{}}}}

JSON:"""

            loop = asyncio.get_running_loop()

            def get_function_call():
                messages = [
                    {"role": "system", "content": "You are a function calling assistant. Select the most appropriate tool and extract parameters from user requests. Respond only with valid JSON."}
                ]

                for role, message in history:
                    messages.append({"role": role, "content": message})

                messages.append({"role": "user", "content": function_call_prompt})

                response = create_chat_completion(
                    messages=messages,
                    max_tokens=300,
                    temperature=0.1
                )
                content = response['choices'][0]['message']['content'].strip()
                return content

            logging.info("Using LLM to select tool and extract parameters...")
            result_json = await loop.run_in_executor(None, get_function_call)

            result_json = result_json.replace("```json", "").replace("```", "").strip()
            if result_json.startswith('{'):
                brace_count = 0
                end_index = 0
                for i, char in enumerate(result_json):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_index = i + 1
                            break
                result_json = result_json[:end_index]

            function_call = json.loads(result_json)
            tool_name = function_call.get("tool_name")
            parameters = function_call.get("parameters", {})

            logging.info(f"LLM selected tool: {tool_name} with parameters: {parameters}")

            if tool_name not in [t["name"] for t in filtered_tools]:
                error_msg = f"LLM selected invalid tool '{tool_name}'. Must be one of: {[t['name'] for t in filtered_tools]}"
                logging.error(error_msg)
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": error_msg},
                    data.get("public_key", "")
                )
                return

        tool_info = next((t for t in available_tools if t["name"] == tool_name), None)
        if tool_info:
            input_schema = tool_info.get("inputSchema", {})
            is_valid, error_msg = validate_tool_parameters(parameters, input_schema)

            if not is_valid:
                error_response = f"Parameter validation failed: {error_msg}"
                logging.error(error_response)
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": error_response},
                    data.get("public_key", "")
                )
                return

        logging.info(f"Calling Tool tool '{tool_name}' with parameters: {parameters}")

        try:
            mcp_result = await registry.call_tool(tool_name, parameters)
            logging.info(f"Tool tool response: {mcp_result}")

            content_items = mcp_result.get("content", [])
            if content_items and len(content_items) > 0:
                text_result = content_items[0].get("text", "")

                try:
                    result = json.loads(text_result)
                except json.JSONDecodeError:
                    result = {"result": text_result}
            else:
                result = {"result": "Tool executed successfully (no content returned)"}

            logging.info(f"Extracted tool result: {result}")

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logging.error(error_msg)
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": error_msg},
                data.get("public_key", "")
            )
            return

        operator = data.get("operator", "default_user")
        natural_response = await convert_tool_result_to_natural_language(
            operator=operator,
            user_prompt=user_prompt,
            tool_name=tool_name,
            tool_result=result
        )
        logging.info(f"Natural language response: {natural_response}")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": natural_response},
            data.get("public_key", "")
        )

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse parameters: {str(e)}"
        logging.error(error_msg)
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

    except Exception as e:
        logging.error(f"Error handling tool call: {e}")
        import traceback
        logging.error(traceback.format_exc())

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": str(e)},
            data.get("public_key", "")
        )

async def handle_install_tool(cell, transmitter: dict):
    """Handle adding new Tool tool from registry and restart agent"""
    data = transmitter.get("data", {})
    tool_id = data.get("tool_id", "")
    variables = data.get("variables", "")
    operator = data.get("operator", "default_user")

    if not tool_id:
        logging.error("No tool_id provided")
        return

    try:
        tools = await cell.list_tools()
        logging.info(f"Available tools count: {len(tools)}")

        tool = None
        for t in tools:
            if t.get("tool_id") == tool_id:
                tool = t
                break

        if not tool:
            error_msg = f"Tool with ID '{tool_id}' not found"
            logging.error(error_msg)
            return

        script = tool.get("script", "")
        config = tool.get("config", "")
        author = tool.get("author", "Unknown")
        tool_name = tool.get("name", tool_id)

        if not script:
            error_msg = f"Tool '{tool_id}' has no script content"
            logging.error(error_msg)
            return

        tools_dir = "./tools"
        os.makedirs(tools_dir, exist_ok=True)

        final_script = script
        if variables:
            if isinstance(variables, str):
                try:
                    variables = json.loads(variables)
                except json.JSONDecodeError:
                    logging.warning(f"Could not parse variables as JSON: {variables}")
                    variables = {}

            if isinstance(variables, dict) and variables:
                variable_lines = []
                for var_name, var_value in variables.items():
                    escaped_value = str(var_value).replace('"', '\\"')
                    variable_lines.append(f'{var_name} = "{escaped_value}"')

                variables_block = '\n'.join(variable_lines) + '\n\n'

                script_lines = script.split('\n')
                insert_position = 0

                for i, line in enumerate(script_lines):
                    stripped = line.strip()
                    if stripped.startswith('#!') or stripped.startswith('# -*-') or stripped.startswith('#-*-'):
                        insert_position = i + 1
                    elif stripped and not stripped.startswith('#'):
                        break

                script_lines.insert(insert_position, variables_block.rstrip('\n'))
                final_script = '\n'.join(script_lines)
                logging.info(f"Injected {len(variables)} variable(s) into script: {list(variables.keys())}")

        script_filename = f"{tool_id}.py"
        script_path = os.path.join(tools_dir, script_filename)

        with open(script_path, 'w') as f:
            f.write(final_script)

        logging.info(f"Tool script saved to {script_path}")

        if config:
            config_filename = f"{tool_id}.config"
            config_path = os.path.join(tools_dir, config_filename)

            with open(config_path, 'w') as f:
                f.write(config)

            logging.info(f"Tool config saved to {config_path}")

        logging.info(f"Tool '{tool_id}' successfully added to tools")

        await store_action(
            operator,
            "install_tool",
            f"Installed tool '{tool_name}' (ID: {tool_id})"
        )

        logging.info("Restarting agent to load new tool...")

        await cell.close()
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        error_msg = f"Error adding tool: {str(e)}"
        logging.error(error_msg)
        import traceback
        logging.error(traceback.format_exc())


async def handle_delete_tool(cell, transmitter: dict):
    """Handle deleting tool from tools directory and restart agent"""
    data = transmitter.get("data", {})
    tool_id = data.get("tool_id", None)
    operator = data.get("operator", "default_user")

    if not tool_id:
        logging.error("No tool_id provided for deletion")
        return

    try:
        tools_dir = "./tools"
        script_filename = f"{tool_id}.py"
        config_filename = f"{tool_id}.config"
        script_path = os.path.join(tools_dir, script_filename)
        config_path = os.path.join(tools_dir, config_filename)

        files_deleted = []

        if os.path.exists(script_path):
            os.remove(script_path)
            files_deleted.append(script_filename)
            logging.info(f"✅ Deleted tool script: {script_path}")

        if os.path.exists(config_path):
            os.remove(config_path)
            files_deleted.append(config_filename)
            logging.info(f"✅ Deleted tool config: {config_path}")

        if not files_deleted:
            logging.warning(f"Tool '{tool_id}' not found")
            return

        logging.info(f"✅ Tool '{tool_id}' successfully deleted. Files removed: {', '.join(files_deleted)}")

        await store_action(
            operator,
            "delete_tool",
            f"Removed tool with ID: {tool_id}"
        )

        logging.info("🔄 Restarting agent...")

        await cell.close()

        await asyncio.sleep(1)

        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        logging.error(f"Error deleting tool: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())


async def handle_delete_task(cell, transmitter: dict):
    """Handle deleting task from tasks directory and restart agent"""
    data = transmitter.get("data", {})
    task_id = data.get("task_id", None)
    operator = data.get("operator", "default_user")

    if not task_id:
        logging.error("No task_id provided for deletion")
        return

    try:
        task_filename = f"{task_id}.json"
        task_path = os.path.join(TASKS_DIR, task_filename)

        if not os.path.exists(task_path):
            logging.warning(f"Task with ID '{task_id}' not found")
            return

        task_name = "Unknown"
        try:
            with open(task_path, 'r') as f:
                task_data = json.load(f)
                task_name = task_data.get("name", "Unknown")
        except Exception as e:
            logging.warning(f"Could not read task name: {e}")

        os.remove(task_path)
        logging.info(f"Deleted task file: {task_path}")

        if task_name in active_tasks:
            del active_tasks[task_name]
            logging.info(f"Removed task '{task_name}' from active tasks")

        logging.info(f"Task '{task_name}' (ID: {task_id}) successfully deleted")

        await store_action(
            operator,
            "delete_task",
            f"Deleted scheduled task '{task_name}' (ID: {task_id})"
        )

        logging.info("Restarting agent...")

        await cell.close()
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        logging.error(f"Error deleting task: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())


async def handle_add_task(cell, transmitter: dict):
    """Handle adding new automated task to tasks directory"""
    data = transmitter.get("data", {})
    task_name = data.get("name", "")
    task_description = data.get("description", "")
    tool_id = data.get("tool_id", "")
    function_name = data.get("function_name", "")
    schedule = data.get("schedule", "")
    operator = data.get("operator", "default_user")

    # Only support simplified resource format
    resource = data.get("resource", None)

    if not resource:
        logging.error("No resource provided in add_task request")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": "Resource field is required"}},
            data.get("public_key", "")
        )
        return

    # Validate resource has prompt
    if "prompt" not in resource:
        logging.error("Resource missing required 'prompt' field")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": "resource.prompt is required"}},
            data.get("public_key", "")
        )
        return

    # Convert to array format for task_executor
    resources = [resource]

    if not task_name:
        logging.error("No task name provided")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": "Task name is required"}},
            data.get("public_key", "")
        )
        return

    if not tool_id:
        logging.error("No tool_id provided")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": "Tool ID is required"}},
            data.get("public_key", "")
        )
        return

    if not function_name:
        logging.error("No function_name provided")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": "Function name is required"}},
            data.get("public_key", "")
        )
        return

    if not schedule:
        logging.error("No schedule provided")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": "Schedule is required"}},
            data.get("public_key", "")
        )
        return

    try:
        import uuid
        from datetime import datetime
        task_id = str(uuid.uuid4())

        os.makedirs(TASKS_DIR, exist_ok=True)

        task_data = {
            "task_id": task_id,
            "name": task_name,
            "description": task_description,
            "tool_id": tool_id,
            "function_name": function_name,
            "resources": resources,
            "schedule": schedule,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }

        task_filename = f"{task_id}.json"
        task_path = os.path.join(TASKS_DIR, task_filename)

        with open(task_path, 'w') as f:
            json.dump(task_data, f, indent=2)

        logging.info(f"Task '{task_name}' saved to {task_path}")
        logging.info(f"   Tool: {tool_id}, Function: {function_name}")
        logging.info(f"   Resources: {len(resources)} resource(s), Schedule: {schedule}")

        active_tasks[task_name] = task_data

        logging.info(f"Task '{task_name}' successfully added with ID: {task_id}")

        await store_action(
            operator,
            "add_task",
            f"Created scheduled task '{task_name}' - runs {schedule} to execute {function_name} on tool {tool_id}"
        )

        logging.info("Restarting agent to load new task...")

        await cell.close()
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        error_msg = f"Error adding task: {str(e)}"
        logging.error(error_msg)
        import traceback
        logging.error(traceback.format_exc())

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": error_msg}},
            data.get("public_key", "")
        )  
  
# Message Routing

async def route_message(cell, transmitter: dict):
    """Route incoming messages to appropriate handlers"""
    try:
        data = transmitter.get("data", {})
        message_type = data.get("type", None)

        handlers = {
            "add_knowledge": lambda: handle_add_knowledge(cell, transmitter),
            "get_agent_status": lambda: handle_get_status(cell, transmitter),
            "update_knowledge": lambda: handle_update_knowledge(cell, transmitter),
            "delete_knowledge": lambda: handle_delete_knowledge(cell, transmitter),
            "fetch_all_knowledge": lambda: handle_fetch_knowledge(cell, transmitter),
            "download_log": lambda: handle_download_log(cell, transmitter),
            "prompt": lambda: handle_prompt(cell, transmitter),
            "call_tool": lambda: handle_call_tool(cell, transmitter),
            "get_tools": lambda: handle_get_tools(cell, transmitter),
            "install_tool": lambda: handle_install_tool(cell, transmitter),
            "add_task": lambda: handle_add_task(cell, transmitter),
            "delete_tool": lambda: handle_delete_tool(cell, transmitter),
            "delete_task": lambda: handle_delete_task(cell, transmitter)
        }

        handler = handlers.get(message_type)
        if handler:
            await handler()
        else:
            logging.warning(f"Unknown message type: {message_type}")
    except Exception as e:
        logging.error(f"Error routing message: {e}")
        import traceback
        logging.error(traceback.format_exc())

async def process_cell_messages(cell):
    """Main message processing loop for cell"""
    async for transmitter in cell.sync():
        await route_message(cell, transmitter)

# Main Function

async def server_main():
    """Main server logic"""
    cell = None
    try:
        logging.info("Setting up infrastructure...")
        await setup_infrastructure()

        logging.info("Initializing database...")
        await initialize_database()

        await install_tool_requirements()

        logging.info("Connecting to Neuronum network...")
        cell = await setup_cell_connection()
        logging.info(f"Connected as Cell: {cell.env.get('HOST') or cell.host}")

        logging.info("Loading Tools...")
        registry = await tool_registry.initialize_registry(cell, logging)

        available_tools = await registry.get_all_tools()
        tool_count = len(available_tools)
        server_info = await registry.get_server_info()
        logging.info(f"Tool Registry initialized with {server_info['total_servers']} servers and {tool_count} tools")

        logging.info(f"Agent started as Cell: {cell.host}")
        logging.info(f"Agent running with {tool_count} Tools")

        scheduler_task = asyncio.create_task(task_executor.task_scheduler_loop(cell, create_chat_completion))
        logging.info("Task scheduler started in background")
        
        if not cell.host.startswith("neuronumagent"):
            await cell.stream(cell.host, {"json": "ping"})

        await process_cell_messages(cell)

        scheduler_task.cancel()
    finally:
        if cell is not None:
            try:
                await cell.close()
                logging.info("Cell connection closed successfully")
            except Exception as e:
                logging.error(f"Error closing cell connection: {e}")

async def main():
    """Main entry point"""
    await server_main()


if __name__ == "__main__":
    asyncio.run(main())
