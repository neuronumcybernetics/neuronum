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

# Import Tool Registry (manages multiple Tool servers)
import tool_registry

# Import configuration
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

active_tasks = {}  # Store loaded tasks by task_name

# ============================================================================
# LOGGING SETUP
# ============================================================================

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# ============================================================================
# LLM AND SYSTEM PROMPTS
# ============================================================================
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

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

async def enable_wal(db_path=DB_PATH):
    """Enables WAL mode for better concurrency (read/write access)."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.commit()
        logging.info("WAL mode enabled.")

async def init_db(db_path=DB_PATH):
    """Initializes the memory and FTS5 knowledge tables."""
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
        logging.info("✅ Database initialized with FTS5 knowledge table.")

async def store_message(user, role, message, db_path=DB_PATH):
    """Stores a message to the memory table for conversation history."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO memory (user, role, message) VALUES (?, ?, ?)",
            (user, role, message)
        )
        await db.commit()

async def fetch_latest_messages(user, limit=CONVERSATION_HISTORY_LIMIT, db_path=DB_PATH) -> List[Tuple[str, str]]:
    """Fetches the latest N messages for conversation history."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT role, message FROM memory WHERE user = ? ORDER BY id DESC LIMIT ?",
            (user, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return list(reversed(rows))

def validate_tool_parameters(parameters: dict, input_schema: dict) -> tuple[bool, str]:
    """
    Validate parameters against a JSON schema (MCP inputSchema format).

    Returns:
        (is_valid, error_message) tuple
    """
    if not input_schema:
        # No schema means no validation required
        return True, ""

    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    # Check required parameters
    for req_param in required:
        if req_param not in parameters:
            return False, f"Missing required parameter: '{req_param}'"

    # Validate each parameter
    for param_name, param_value in parameters.items():
        if param_name not in properties:
            # Extra parameters are allowed (for flexibility)
            continue

        param_schema = properties[param_name]
        expected_type = param_schema.get("type", "string")

        # Type validation
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

        # Enum validation
        if "enum" in param_schema:
            if param_value not in param_schema["enum"]:
                return False, (
                    f"Parameter '{param_name}' value '{param_value}' not in allowed values: "
                    f"{param_schema['enum']}"
                )

        # Array item validation
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
    """Utility function to add a knowledge entry to the FTS5 table (requires ID)."""
    combined = f"{topic}:{data}"
    knowledge_id = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO knowledge (knowledge_id, topic, content) VALUES (?, ?, ?)",
            (knowledge_id, topic, data)
        )
        await db.commit()

async def delete_knowledge_entry(knowledge_id: str, db_path=DB_PATH):
    """Deletes a knowledge entry from the FTS5 table using its unique knowledge_id."""
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
            logging.info(f"✅ Knowledge entry with ID '{knowledge_id}' deleted successfully.")
            return True
        else:
            logging.warning(f"Knowledge entry with ID '{knowledge_id}' not found or not deleted.")
            return False

async def update_knowledge_entry(knowledge_id: str, new_data: str, db_path=DB_PATH) -> bool:
    """Updates the 'content' of an existing FTS5 entry."""
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
            logging.info(f"✅ Knowledge entry with ID '{knowledge_id}' updated successfully.")
            return True
        else:
            logging.warning(f"Knowledge entry with ID '{knowledge_id}' not found or not updated.")
            return False

async def retrieve_knowledge(user_query: str, db_path=DB_PATH) -> str:
    """Retrieves relevant knowledge using FTS5 with improved keyword search."""
    tokens = re.findall(r"\b\w+\b", user_query.lower())

    # Enhanced stopwords including FTS5 operators to prevent syntax injection
    ENHANCED_STOPWORDS = FTS5_STOPWORDS | {"or", "and", "not", "near"}
    keywords = [t for t in tokens if t not in ENHANCED_STOPWORDS]

    if not keywords:
        return "No specific business knowledge found in the database."

    # Limit to prevent DoS attacks (max 10 keywords for reasonable performance)
    keywords = keywords[:10]

    # Quote each keyword for literal search - this prevents FTS5 operator injection
    # Quotes tell FTS5 to treat the content as literal text, not operators
    quoted_keywords = [f'"{keyword}"' for keyword in keywords]
    search_expr = " OR ".join(quoted_keywords)

    async with aiosqlite.connect(db_path) as db:
        try:
            # Use parameterized query for the MATCH expression
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
            # Log the full error internally but don't expose details to user
            logging.warning(f"Knowledge retrieval error: {str(e)[:100]}")
            return "Knowledge retrieval temporarily unavailable."

# --- OpenAI API Client Configuration ---
# Connect to local vLLM server instead of loading model directly
try:
    logging.info(f"🤖 Connecting to vLLM API server at {VLLM_API_BASE}")

    # Create OpenAI client pointing to local vLLM server
    client = OpenAI(
        base_url=VLLM_API_BASE,
        api_key="EMPTY"  # vLLM uses "EMPTY" as convention for local servers
    )

    logging.info(f"✅ OpenAI client initialized for vLLM server")

except Exception as e:
    logging.error(f"❌ Error initializing OpenAI client: {e}")
    logging.error("Make sure vLLM is running: python -m vllm.entrypoints.openai.api_server --model <model-name>")
    sys.exit(1)

# --- Helper function for chat completion ---
def create_chat_completion(messages, max_tokens=MODEL_MAX_TOKENS, temperature=MODEL_TEMPERATURE):
    """
    Generate chat completion using OpenAI-compatible API (Ollama server).

    Args:
        messages: List of message dicts with 'role' and 'content'
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature

    Returns:
        Dict with 'choices' containing generated response
    """
    try:
        # Call the OpenAI API (which points to our local vLLM server)
        response = client.chat.completions.create(
            model=VLLM_MODEL_NAME,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=MODEL_TOP_P,
        )

        # Return in compatible format
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
    """Fetches all knowledge entries from the FTS5 table."""
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
    """Erases all data from the database and clears the log file."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("DELETE FROM memory")
            logging.info("✅ All conversation history deleted from memory table.")
            
            await db.execute("DELETE FROM knowledge")
            logging.info("✅ All knowledge entries deleted from knowledge table.")
            
            await db.commit()
        
        with open(LOG_FILE, 'w') as f:
            f.write('')
        logging.info("✅ Log file cleared.")
        
        logging.info("✅ All data erased successfully.")
        return True
        
    except Exception as e:
        logging.error(f"❌ Error during data erasure: {e}")
        return False


async def get_model_answer(user_id: str, user_query: str, file: bool = False, file_content: str = "") -> str:
    """Core function for RAG logic."""
    loop = asyncio.get_running_loop()

    # Handle file content requests
    if file:
        # Format the system prompt with the context
        augmented_system_prompt = FILE_RAG_PROMPT_TEMPLATE.format(prompt=user_query,context=file_content)

        # Build the messages list
        messages = [
            {"role": "user", "content": augmented_system_prompt},
        ]

        logging.info(f"[Messages for Agent]: {messages}")
        # Generate the response
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

        # Only store the conversation if we got a non-empty answer
        if answer:
            await store_message(user_id, "user", full_prompt)
            await store_message(user_id, "assistant", answer)
        else:
            logging.warning("⚠️ Model returned empty response, not storing in conversation history")

        return answer
    else:
        # Otherwise, retrieve knowledge from the database
        context = await retrieve_knowledge(user_query)

        # Format the system prompt
        augmented_system_prompt = RAG_PROMPT_TEMPLATE

        # Get conversation history
        history = await fetch_latest_messages(user_id, limit=5)

        # Build the messages list
        messages = [
            {"role": "system", "content": augmented_system_prompt},
        ]

        for role, message in history:
            messages.append({"role": role, "content": message})

        # Include context directly in the user message for maximum weight
        # Prepend system prompt to the user message since Gemma 2 doesn't support system role
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

        # Generate the response
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

        # Only store the conversation if we got a non-empty answer
        if answer:
            await store_message(user_id, "user", user_query)
            await store_message(user_id, "assistant", answer)
        else:
            logging.warning("⚠️ Model returned empty response, not storing in conversation history")

        return answer


async def convert_tool_result_to_natural_language(
    operator: str,
    user_prompt: str,
    tool_name: str,
    tool_result: dict
) -> str:
    """Convert structured tool result to natural language response.

    Args:
        operator: User ID for conversation context
        user_prompt: The original user request
        tool_name: Name of the tool that was executed
        tool_result: The structured result from the tool

    Returns:
        Natural language response string
    """
    loop = asyncio.get_running_loop()

    # Create a prompt that asks the LLM to convert the tool result to natural language
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

    # Store in conversation history
    if natural_response:
        await store_message(operator, "user", user_prompt)
        await store_message(operator, "assistant", natural_response)

    return natural_response


# ============================================================================
# INFRASTRUCTURE SETUP HELPERS
# ============================================================================

async def setup_infrastructure():
    """Initialize infrastructure for the agent."""
    logging.info("Initializing system...")

async def initialize_database():
    """Initialize the SQLite database with WAL mode."""
    await enable_wal()
    await init_db()

async def install_tool_requirements():
    """Install requirements from all .config files in the tools directory."""
    try:
        # Check if we're in a virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )

        if not in_venv:
            logging.warning("⚠️ Not running in a virtual environment. Skipping automatic package installation.")
            logging.warning("⚠️ Please activate a virtual environment and manually install required packages.")
            return

        tools_dir = "./tools"

        # Check if directory exists
        if not os.path.exists(tools_dir):
            logging.info("No tools directory found, skipping requirements installation")
            return

        # Collect all requirements from .config files
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

        logging.info(f"📦 Installing {len(all_requirements)} package(s): {', '.join(all_requirements)}")

        # Install packages using pip
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
                    logging.info(f"✅ Successfully installed {requirement}")
                else:
                    logging.error(f"❌ Failed to install {requirement}: {result.stderr}")

            except subprocess.TimeoutExpired:
                logging.error(f"❌ Timeout while installing {requirement}")
            except Exception as e:
                logging.error(f"❌ Error installing {requirement}: {e}")

        logging.info("✅ Tool requirements installation complete")

    except Exception as e:
        logging.error(f"Error in install_tool_requirements: {e}")
        import traceback
        logging.error(traceback.format_exc())


async def setup_cell_connection():
    """Establish connection as a Neuronum Cell and return cell instance."""
    # Cell credentials are automatically loaded from ~/.neuronum/ by the Cell class
    cell = Cell()

    # Verify the cell is properly configured
    if not cell.env.get("HOST"):
        logging.error("❌ No HOST found in Cell credentials. Please run 'neuronum create-cell' or 'neuronum connect-cell' first.")
        await cell.close()
        sys.exit(1)

    logging.info(f"✅ Connected to Cell: {cell.env.get('HOST')}")
    return cell
# ============================================================================
# MESSAGE HANDLERS
# ============================================================================

async def send_cell_response(cell, transmitter_id: str, data: dict, public_key: str):
    """Helper to send response back through the cell."""
    await cell.tx_response(
        transmitter_id=transmitter_id,
        data=data,
        client_public_key_str=public_key
    )

async def handle_add_knowledge(cell, transmitter: dict):
    """Handle adding knowledge to the database."""
    data = transmitter.get("data", {})
    knowledge_topic = data.get("knowledge_topic", None)
    knowledge_data = data.get("knowledge_data", None)

    logging.info("Adding knowledge to database...")
    await add_knowledge_entry(knowledge_topic, knowledge_data)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge updated"},
        data.get("public_key", "")
    )

async def handle_get_status(cell, transmitter: dict):
    """Handle get agent status request."""
    data = transmitter.get("data", {})
    logging.info("Checking Agent Status")

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "agent running"},
        data.get("public_key", "")
    )

async def handle_update_knowledge(cell, transmitter: dict):
    """Handle updating existing knowledge in the database."""
    data = transmitter.get("data", {})
    knowledge_id = data.get("knowledge_id", None)
    knowledge_data = data.get("knowledge_data", None)

    logging.info("Updating knowledge in database...")
    await update_knowledge_entry(knowledge_id, knowledge_data)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge updated"},
        data.get("public_key", "")
    )

async def handle_delete_knowledge(cell, transmitter: dict):
    """Handle deleting knowledge from the database."""
    data = transmitter.get("data", {})
    knowledge_id = data.get("knowledge_id", None)

    logging.info("Deleting knowledge from database...")
    await delete_knowledge_entry(knowledge_id)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge deleted"},
        data.get("public_key", "")
    )

async def handle_fetch_knowledge(cell, transmitter: dict):
    """Handle fetching all knowledge from the database."""
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
    """Handle downloading the agent log file and clear it after download."""
    data = transmitter.get("data", {})
    logging.info("Fetching log from agent.log...")

    try:
        # Read the log file
        with open("agent.log", "r") as f:
            agent_log = f.read()
        logging.info("Agent log fetched successfully")

        # Send the log content to the user
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"log": agent_log}},
            data.get("public_key", "")
        )

        # Clear the log file after successful download
        with open("agent.log", "w") as f:
            f.write('')
        logging.info("Agent log cleared after download")

    except Exception as e:
        agent_log = f"Error reading agent log: {e}"
        logging.error(agent_log)

        # Send error response
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"log": agent_log}},
            data.get("public_key", "")
        )


async def handle_prompt(cell, transmitter: dict):
    """Handle user prompt and generate LLM response."""
    data = transmitter.get("data", {})
    prompt = data.get("prompt", "")
    file = data.get("file", False)  # Should be boolean
    file_content = data.get("file_content", "")   # This contains the actual file content if present

    # Debug: Log what keys are in the data
    logging.info(f"DEBUG - Data keys: {list(data.keys())}")
    logging.info(f"DEBUG - Has 'file' key: {'file' in data}")

    logging.info(f"[User]: {prompt}")
    operator = data.get("operator", "default_user")

    try:
        # Pass the file content to the model (empty string if no file)
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

        # Send error response to client
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
    """Handle get tools request - returns config file data for each tool_id and all tasks.

    Returns a dictionary with two keys:
    - 'tools': dictionary where each key is a tool_id and value is the parsed config file content
    - 'tasks': list of all task objects from the tasks directory
    """
    data = transmitter.get("data", {})
    logging.info("Fetching all tool configs and tasks...")

    try:
        # Load config files from tools directory
        tools_dir = "./tools"
        tools_by_id = {}

        if os.path.exists(tools_dir):
            for filename in os.listdir(tools_dir):
                if filename.endswith(".config"):
                    tool_id = filename[:-7]  # Remove .config extension
                    config_path = os.path.join(tools_dir, filename)

                    try:
                        with open(config_path, 'r') as f:
                            config_content = f.read()
                            config_json = json.loads(config_content)

                        # Store the entire config for this tool_id
                        tools_by_id[tool_id] = config_json

                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse config file {filename}: {e}")
                    except Exception as e:
                        logging.warning(f"Failed to read config file {filename}: {e}")

        logging.info(f"Retrieved {len(tools_by_id)} tool configs")

        # Load tasks from tasks directory
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

        # Send combined response with tools and tasks
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
    """Handle tool execution requests using AI-assisted tool selection.

    Client sends:
    - tool_id: The tool/server ID to use
    - prompt: Natural language request

    The LLM selects the appropriate tool function and extracts parameters from the prompt.
    """
    data = transmitter.get("data", {})
    tool_id = data.get("tool_id")  # Tool category/server ID (required)
    user_prompt = data.get("prompt", "")  # The natural language request (required)
    operator = data.get("operator", "default_user")  # User ID for conversation history

    logging.info(f"Tool call requested - Tool ID: {tool_id}")
    logging.info(f"User prompt: {user_prompt}")

    try:
        # Get conversation history for context
        history = await fetch_latest_messages(operator, limit=5)
        logging.info(f"Retrieved {len(history)} messages from conversation history")

        # Get available tools from Tool Registry
        registry = await tool_registry.get_registry()
        available_tools = await registry.get_all_tools()

        # Validate tool_id is provided
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

        # AI-assisted tool selection: Filter tools by tool_id
        if tool_id:
            logging.info(f"AI-assisted mode: Filtering tools by tool_id '{tool_id}'")

            # Filter tools by tool_id (assumes tools have a 'server' or 'id' field matching tool_id)
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

            # Build detailed tool info for LLM
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

            # Single LLM call to select tool AND extract parameters (Option 2)
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

                # Add conversation history for context
                for role, message in history:
                    messages.append({"role": role, "content": message})

                # Add the current function call prompt
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

            # Clean and parse JSON
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

            # Validate that selected tool is in the filtered list
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

        # Step 2: Validate parameters before calling the tool
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

        # Step 3: Call the tool via Tool Registry (returns standardized Tool format)
        logging.info(f"Calling Tool tool '{tool_name}' with parameters: {parameters}")

        try:
            mcp_result = await registry.call_tool(tool_name, parameters)
            logging.info(f"Tool tool response: {mcp_result}")

            # Extract text content from standardized Tool response format
            # Tool format: {"content": [{"type": "text", "text": "..."}], "isError": false}
            content_items = mcp_result.get("content", [])
            if content_items and len(content_items) > 0:
                # Get the first text content item
                text_result = content_items[0].get("text", "")

                # Try to parse as JSON for structured results
                try:
                    result = json.loads(text_result)
                except json.JSONDecodeError:
                    # If not JSON, use as plain text result
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

        # Step 4: Convert result to natural language
        operator = data.get("operator", "default_user")
        natural_response = await convert_tool_result_to_natural_language(
            operator=operator,
            user_prompt=user_prompt,
            tool_name=tool_name,
            tool_result=result
        )
        logging.info(f"Natural language response: {natural_response}")

        # Step 5: Send response back
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

async def handle_add_tool(cell, transmitter: dict):
    """Handle adding a new Tool tool from the registry and restart the agent."""
    data = transmitter.get("data", {})
    tool_id = data.get("tool_id", "")
    variables = data.get("variables", "")

    if not tool_id:
        logging.error("No tool_id provided")
        return

    try:
        # Fetch all available tools from the cell
        tools = await cell.list_tools()
        logging.info(f"Available tools count: {len(tools)}")

        # Find the tool matching the provided tool_id
        tool = None
        for t in tools:
            if t.get("tool_id") == tool_id:
                tool = t
                break

        if not tool:
            error_msg = f"Tool with ID '{tool_id}' not found"
            logging.error(error_msg)
            return

        # Extract the script and config
        script = tool.get("script", "")
        config = tool.get("config", "")
        author = tool.get("author", "Unknown")


        if not script:
            error_msg = f"Tool '{tool_id}' has no script content"
            logging.error(error_msg)
            return

        # Create tools directory if it doesn't exist
        tools_dir = "./tools"
        os.makedirs(tools_dir, exist_ok=True)

        # Prepare the script with variables injected at the top
        final_script = script
        if variables:
            # Parse variables if it's a string (JSON)
            if isinstance(variables, str):
                try:
                    variables = json.loads(variables)
                except json.JSONDecodeError:
                    logging.warning(f"Could not parse variables as JSON: {variables}")
                    variables = {}

            # Build variable declarations
            if isinstance(variables, dict) and variables:
                variable_lines = []
                for var_name, var_value in variables.items():
                    # Escape quotes in the value and wrap in quotes
                    escaped_value = str(var_value).replace('"', '\\"')
                    variable_lines.append(f'{var_name} = "{escaped_value}"')

                variables_block = '\n'.join(variable_lines) + '\n\n'

                # Smart injection: Insert after shebang/encoding but before imports
                script_lines = script.split('\n')
                insert_position = 0

                # Skip shebang and encoding declarations
                for i, line in enumerate(script_lines):
                    stripped = line.strip()
                    if stripped.startswith('#!') or stripped.startswith('# -*-') or stripped.startswith('#-*-'):
                        insert_position = i + 1
                    elif stripped and not stripped.startswith('#'):
                        # First non-comment, non-empty line
                        break

                # Insert variables at the calculated position
                script_lines.insert(insert_position, variables_block.rstrip('\n'))
                final_script = '\n'.join(script_lines)
                logging.info(f"✅ Injected {len(variables)} variable(s) into script: {list(variables.keys())}")

        # Save the script using tool_id as filename
        script_filename = f"{tool_id}.py"
        script_path = os.path.join(tools_dir, script_filename)

        with open(script_path, 'w') as f:
            f.write(final_script)

        logging.info(f"✅ Tool script saved to {script_path}")

        # Save the config if available
        if config:
            config_filename = f"{tool_id}.config"
            config_path = os.path.join(tools_dir, config_filename)

            with open(config_path, 'w') as f:
                # Write config as-is (it's already a string from the API)
                f.write(config)

            logging.info(f"✅ Tool config saved to {config_path}")

        logging.info(f"✅ Tool '{tool_id}' successfully added to tools")
        logging.info("🔄 Restarting agent to load new tool...")

        # Close cell connection before restart
        await cell.close()

        # Wait before restart
        await asyncio.sleep(1)

        # Restart the agent
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        error_msg = f"Error adding tool: {str(e)}"
        logging.error(error_msg)
        import traceback
        logging.error(traceback.format_exc())


async def handle_delete_tool(cell, transmitter: dict):
    """Handle deleting a tool from the tools directory and restart the agent."""
    data = transmitter.get("data", {})
    tool_id = data.get("tool_id", None)

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

        # Delete the script file
        if os.path.exists(script_path):
            os.remove(script_path)
            files_deleted.append(script_filename)
            logging.info(f"✅ Deleted tool script: {script_path}")

        # Delete the config file if it exists
        if os.path.exists(config_path):
            os.remove(config_path)
            files_deleted.append(config_filename)
            logging.info(f"✅ Deleted tool config: {config_path}")

        if not files_deleted:
            logging.warning(f"Tool '{tool_id}' not found")
            return

        logging.info(f"✅ Tool '{tool_id}' successfully deleted. Files removed: {', '.join(files_deleted)}")
        logging.info("🔄 Restarting agent...")

        # Close cell connection before restart
        await cell.close()

        # Wait before restart
        await asyncio.sleep(1)

        # Restart the agent
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        logging.error(f"Error deleting tool: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())


async def handle_delete_task(cell, transmitter: dict):
    """Handle deleting a task from the tasks directory and restart the agent."""
    data = transmitter.get("data", {})
    task_id = data.get("task_id", None)

    if not task_id:
        logging.error("No task_id provided for deletion")
        return

    try:
        task_filename = f"{task_id}.json"
        task_path = os.path.join(TASKS_DIR, task_filename)

        # Check if task file exists
        if not os.path.exists(task_path):
            logging.warning(f"Task with ID '{task_id}' not found")
            return

        # Load task data to get the task name for logging
        task_name = "Unknown"
        try:
            with open(task_path, 'r') as f:
                task_data = json.load(f)
                task_name = task_data.get("name", "Unknown")
        except Exception as e:
            logging.warning(f"Could not read task name: {e}")

        # Delete the task file
        os.remove(task_path)
        logging.info(f"✅ Deleted task file: {task_path}")

        # Remove from active_tasks dictionary if present
        if task_name in active_tasks:
            del active_tasks[task_name]
            logging.info(f"✅ Removed task '{task_name}' from active tasks")

        logging.info(f"✅ Task '{task_name}' (ID: {task_id}) successfully deleted")
        logging.info("🔄 Restarting agent...")

        # Close cell connection before restart
        await cell.close()

        # Wait before restart
        await asyncio.sleep(1)

        # Restart the agent
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        logging.error(f"Error deleting task: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())


async def handle_add_task(cell, transmitter: dict):
    """Handle adding a new automated task to the tasks directory.

    Tasks are automated workflows that use Tool tools on a schedule.
    """
    data = transmitter.get("data", {})
    task_name = data.get("name", "")
    task_description = data.get("description", "")
    tool_id = data.get("tool_id", "")
    function_name = data.get("function_name", "")
    input_type = data.get("input_type", "")
    input_data = data.get("input_data", "")
    schedule = data.get("schedule", "")

    # Validate required fields
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

    if not input_type:
        logging.error("No input_type provided")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"error": "Input type is required"}},
            data.get("public_key", "")
        )
        return

    try:
        # Generate unique task ID
        import uuid
        from datetime import datetime
        task_id = str(uuid.uuid4())

        # Create tasks directory if it doesn't exist
        os.makedirs(TASKS_DIR, exist_ok=True)

        # Create task data structure with new automated workflow fields
        task_data = {
            "task_id": task_id,
            "name": task_name,
            "description": task_description,
            "tool_id": tool_id,
            "function_name": function_name,
            "input_type": input_type,
            "input_data": input_data,
            "schedule": schedule,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }

        # Save task as JSON file
        task_filename = f"{task_id}.json"
        task_path = os.path.join(TASKS_DIR, task_filename)

        with open(task_path, 'w') as f:
            json.dump(task_data, f, indent=2)

        logging.info(f"✅ Task '{task_name}' saved to {task_path}")
        logging.info(f"   Tool: {tool_id}, Function: {function_name}")
        logging.info(f"   Input Type: {input_type}, Schedule: {schedule}")

        # Store task in active_tasks dictionary
        active_tasks[task_name] = task_data

        logging.info(f"✅ Task '{task_name}' successfully added with ID: {task_id}")
        logging.info("🔄 Restarting agent to load new task...")

        # Close cell connection before restart
        await cell.close()
        await asyncio.sleep(1)

        # Restart the agent
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
  
# ============================================================================
# MESSAGE ROUTING
# ============================================================================

async def route_message(cell, transmitter: dict):
    """Route incoming messages to appropriate handlers."""
    try:
        data = transmitter.get("data", {})
        message_type = data.get("type", None)

        # Message handler mapping
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
            "add_tool": lambda: handle_add_tool(cell, transmitter),
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

async def execute_scheduled_task(cell, task_data: dict):
    """Execute a single scheduled task by calling its tool function.

    Args:
        cell: The cell instance for Tool registry access
        task_data: Task configuration with tool_id, function_name, input_type, input_data, etc.
    """
    task_name = task_data.get("name", "Unknown")
    tool_id = task_data.get("tool_id")
    function_name = task_data.get("function_name")
    input_type = task_data.get("input_type", "")
    input_data = task_data.get("input_data", "")

    logging.info(f"⏰ Executing scheduled task: {task_name}")
    logging.info(f"   Tool: {tool_id}, Function: {function_name}")
    logging.info(f"   Input Type: {input_type}, Input Data: {input_data}")

    # Validate required fields
    if not tool_id:
        logging.error(f"❌ Task '{task_name}' has no tool_id configured. Skipping execution.")
        return

    if not function_name:
        logging.error(f"❌ Task '{task_name}' has no function_name configured. Skipping execution.")
        return

    try:
        # Get Tool Registry
        registry = await tool_registry.get_registry()

        # Get all available tools
        available_tools = await registry.get_all_tools()

        # Find tools matching the tool_id (safely handle None)
        matching_tools = [
            tool for tool in available_tools
            if tool.get("server") == tool_id or (tool_id and tool_id in tool.get("name", ""))
        ]

        if not matching_tools:
            logging.error(f"❌ No tools found for tool_id '{tool_id}'")
            return

        # Find the specific function in the matching tools
        target_tool = None
        for tool in matching_tools:
            if tool.get("name") == function_name:
                target_tool = tool
                break

        if not target_tool:
            logging.error(f"❌ Function '{function_name}' not found in tool '{tool_id}'")
            return

        # Extract parameters from input_data using LLM if input_data is provided
        parameters = {}
        if input_data:
            # Get parameter schema from the tool
            input_schema = target_tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})

            if properties:
                # Build parameter extraction prompt
                param_info = []
                for param_name, param_def in properties.items():
                    description = param_def.get("description", "")
                    param_type = param_def.get("type", "string")
                    param_info.append(f"  - {param_name} ({param_type}): {description}")

                extraction_prompt = f"""Extract parameters from this instruction: "{input_data}"

Tool: {function_name}
Required parameters:
{chr(10).join(param_info)}

Respond ONLY with valid JSON using these exact parameter names.

JSON:"""

                logging.info("Extracting parameters from input_data using LLM...")

                # Use LLM to extract parameters
                loop = asyncio.get_running_loop()

                def extract_params():
                    messages = [
                        {"role": "system", "content": "You extract parameters from user requests. Respond only with valid JSON."},
                        {"role": "user", "content": extraction_prompt}
                    ]

                    response = create_chat_completion(
                        messages=messages,
                        max_tokens=200,
                        temperature=0.1
                    )
                    content = response['choices'][0]['message']['content'].strip()
                    return content

                params_json_str = await loop.run_in_executor(None, extract_params)

                # Clean and parse JSON
                params_json_str = params_json_str.replace("```json", "").replace("```", "").strip()
                if params_json_str.startswith('{'):
                    brace_count = 0
                    end_index = 0
                    for i, char in enumerate(params_json_str):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_index = i + 1
                                break
                    params_json_str = params_json_str[:end_index]

                parameters = json.loads(params_json_str)
                logging.info(f"Extracted parameters: {parameters}")

        # Call the tool with extracted parameters
        logging.info(f"Calling Tool tool '{function_name}' with parameters: {parameters}")

        try:
            mcp_result = await registry.call_tool(function_name, parameters)
            logging.info(f"✅ Task '{task_name}' completed successfully")
            logging.info(f"Result: {mcp_result}")

            # Optionally: Store result or send notification
            # For now, just log it

        except Exception as e:
            logging.error(f"❌ Task '{task_name}' execution failed: {str(e)}")

    except Exception as e:
        logging.error(f"Error executing scheduled task '{task_name}': {e}")
        import traceback
        logging.error(traceback.format_exc())

def parse_schedule(schedule: str) -> dict:
    """Parse schedule string into days and timestamps.

    Format: "mon,tue,wed@timestamp1,timestamp2" or old format like "daily", "1hour"

    Returns:
        dict with 'type', 'days' (list), and 'timestamps' (list of int)
    """
    # Check if it's the new dynamic format (contains @ symbol)
    if '@' in schedule:
        parts = schedule.split('@')
        days_part = parts[0].strip()
        times_part = parts[1].strip() if len(parts) > 1 else ""

        # Parse days (comma-separated)
        days = [day.strip().lower() for day in days_part.split(',') if day.strip()]

        # Parse Unix timestamps (comma-separated)
        timestamps = []
        if times_part:
            for ts in times_part.split(','):
                try:
                    timestamps.append(int(ts.strip()))
                except ValueError:
                    logging.warning(f"Invalid timestamp in schedule: {ts}")

        return {
            'type': 'dynamic',
            'days': days,
            'timestamps': timestamps
        }
    else:
        pass

def should_task_run(schedule_info: dict, last_run_timestamp: int, current_timestamp: int) -> bool:
    """Determine if a task should run based on its schedule.

    Args:
        schedule_info: Parsed schedule from parse_schedule()
        last_run_timestamp: Unix timestamp of last execution
        current_timestamp: Current Unix timestamp

    Returns:
        True if task should run now
    """
    from datetime import datetime

    if schedule_info['type'] == 'interval':
        # Old interval-based logic
        interval = schedule_info['interval_seconds']
        time_since_last = current_timestamp - last_run_timestamp
        return time_since_last >= interval

    elif schedule_info['type'] == 'dynamic':
        # New day + timestamp logic
        days = schedule_info['days']
        timestamps = schedule_info['timestamps']

        if not days or not timestamps:
            return False

        # Get current day of week (mon, tue, wed, etc.)
        current_dt = datetime.fromtimestamp(current_timestamp)
        day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        current_day = day_names[current_dt.weekday()]

        # Check if today is in the scheduled days
        if current_day not in days:
            return False

        # Check if any of the scheduled timestamps should trigger now
        # Allow a 60-second window for execution (current time ± 30 seconds)
        tolerance = 30
        for scheduled_ts in timestamps:
            if abs(current_timestamp - scheduled_ts) <= tolerance:
                # Make sure we haven't already run at this timestamp
                if last_run_timestamp < scheduled_ts - tolerance:
                    return True

        return False

    return False

async def task_scheduler(cell):
    """Background task scheduler that runs tasks based on their schedule.

    Runs continuously in the background, checking and executing scheduled tasks.
    Supports both interval-based schedules (e.g., "daily", "1hour") and
    dynamic day+timestamp schedules (e.g., "mon,tue@1766482200,1766529600").
    """
    import time

    logging.info("🕐 Task scheduler started")

    # Track last execution Unix timestamp for each task
    last_execution = {}

    while True:
        try:
            # Load all tasks from the tasks directory
            if not os.path.exists(TASKS_DIR):
                await asyncio.sleep(60)  # Check every minute
                continue

            # Use Unix timestamp for consistent time tracking
            current_timestamp = int(time.time())

            for filename in os.listdir(TASKS_DIR):
                if not filename.endswith(".json"):
                    continue

                task_path = os.path.join(TASKS_DIR, filename)

                try:
                    with open(task_path, 'r') as f:
                        task_data = json.load(f)

                    task_id = task_data.get("task_id")
                    task_name = task_data.get("name")
                    schedule_str = task_data.get("schedule")
                    status = task_data.get("status", "active")

                    # Skip inactive tasks
                    if status != "active":
                        continue

                    if not schedule_str:
                        logging.warning(f"Task '{task_name}' has no schedule defined")
                        continue

                    # Parse the schedule
                    schedule_info = parse_schedule(schedule_str)

                    # Get last run timestamp (default to 0 if never run)
                    last_run_timestamp = last_execution.get(task_id, 0)

                    # Check if task should run based on schedule
                    if should_task_run(schedule_info, last_run_timestamp, current_timestamp):
                        logging.info(f"⏰ Triggering scheduled task: {task_name}")
                        logging.info(f"   Schedule: {schedule_str}")

                        # Execute the task
                        await execute_scheduled_task(cell, task_data)

                        # Update last execution timestamp
                        last_execution[task_id] = current_timestamp

                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse task file {filename}: {e}")
                except Exception as e:
                    logging.error(f"Error processing task {filename}: {e}")
                    import traceback
                    logging.error(traceback.format_exc())

            # Sleep for 60 seconds before next check
            await asyncio.sleep(60)

        except Exception as e:
            logging.error(f"Error in task scheduler: {e}")
            import traceback
            logging.error(traceback.format_exc())
            await asyncio.sleep(60)  # Continue running despite errors

async def process_cell_messages(cell):
    """Main message processing loop for the cell."""
    async for transmitter in cell.sync():
        await route_message(cell, transmitter)

# ============================================================================
# MAIN FUNCTION
# ============================================================================

async def agent_main():
    """Main agent logic"""
    cell = None
    try:
        # Setup
        logging.info("Setting up infrastructure...")
        await setup_infrastructure()

        logging.info("Initializing database...")
        await initialize_database()

        await install_tool_requirements()

        # Connect as Cell
        logging.info("Connecting to Neuronum network...")
        cell = await setup_cell_connection()
        logging.info(f"✅ Connected as Cell: {cell.env.get('HOST') or cell.host}")

        # Initialize Tool Registry with all servers (fully async)
        logging.info("Loading Tools...")
        registry = await tool_registry.initialize_registry(cell, logging)

        # Count available tools from all servers
        available_tools = await registry.get_all_tools()
        tool_count = len(available_tools)
        server_info = await registry.get_server_info()
        logging.info(f"✅ Tool Registry initialized with {server_info['total_servers']} servers and {tool_count} tools")

        logging.info(f"🤖 Agent started as Cell: {cell.host}")
        logging.info(f"✅ Agent running with {tool_count} Tools")

        # Start the task scheduler in the background
        scheduler_task = asyncio.create_task(task_scheduler(cell))
        logging.info("✅ Task scheduler started in background")
        
        if not cell.host.startswith("neuronumagent"):
            await cell.stream(cell.host, {"json": "ping"}) 

        # Process incoming messages
        await process_cell_messages(cell)

        scheduler_task.cancel()
    finally:
        # Ensure cell is properly closed on exit
        if cell is not None:
            try:
                await cell.close()
                logging.info("Cell connection closed successfully")
            except Exception as e:
                logging.error(f"Error closing cell connection: {e}")

async def main():
    """Main entry point"""
    await agent_main()


if __name__ == "__main__":
    asyncio.run(main())
