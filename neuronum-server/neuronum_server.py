import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import sys
import textwrap
from datetime import datetime
from openai import OpenAI
import aiosqlite
from typing import List, Tuple
import re
from neuronum import Cell
import hashlib
import logging
import subprocess
import json
from jinja2 import Environment, FileSystemLoader

import tool_registry
from config import (
    HOST,
    PRIVATE_KEY,
    PUBLIC_KEY,
    LOG_FILE,
    DB_PATH,
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

# Setup Jinja2 environment
env = Environment(loader=FileSystemLoader("templates"))

# Logging Setup
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# System Prompts

RAG_PROMPT_TEMPLATE = textwrap.dedent("""
    You are a helpful assistant. You have access to two sources of information:

    1. CONVERSATION HISTORY - The previous user/assistant messages are your memory of past discussions.
       Use this to answer questions about what was discussed, recent activities, or follow-ups.

    2. RELEVANT CONTEXT - Knowledge retrieved from the database, marked with "RELEVANT CONTEXT:".
       This contains factual information. Trust it completely as the source of truth.

    IMPORTANT RULES:
    - If the user asks about past conversations but there are NO previous messages, say "I don't have any record of previous conversations."
    - NEVER make up or invent information. Only use what is explicitly provided.
    - If you don't have information to answer a question, say so honestly.
    - Be concise and direct.
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
                message_type TEXT DEFAULT 'chat',
                context TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                description TEXT,
                original_data TEXT,
                tool_id TEXT,
                tool_name TEXT,
                parameter TEXT,
                response TEXT,
                status TEXT DEFAULT 'pending',
                is_multi_step BOOLEAN,
                steps TEXT,
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

        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.commit()
        logging.info("Database initialized.")

async def store_message(user, role, message, message_type="chat", context=None, db_path=DB_PATH):
    """Store message to memory table for conversation history

    Args:
        user: User identifier
        role: Message role (user, assistant, system)
        message: The message content
        message_type: Type of message (chat, action_result, system_notification)
        context: Optional additional context (e.g., action_id reference)
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO memory (user, role, message, message_type, context) VALUES (?, ?, ?, ?, ?)",
            (user, role, message, message_type, context)
        )
        await db.commit()

async def store_action_entry(subject: str, context: str, original_data: str, tool_id: str = None, tool_name: str = None, parameter: str = None, is_multi_step: bool = False, steps: str = None, status: str = 'pending', response: str = None, db_path=DB_PATH) -> int:
    """Store action entry in actions table

    Args:
        status: Action status ('pending', 'finished', 'failed', 'dismissed')
        response: Only used for failed actions to store error message

    Returns:
        The ID of the newly created action entry
    """
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO actions (subject, description, original_data, tool_id, tool_name, parameter, status, response, is_multi_step, steps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (subject, context, original_data, tool_id, tool_name, parameter, status, response, is_multi_step, steps)
        )
        action_id = cursor.lastrowid
        await db.commit()
        if is_multi_step:
            logging.info(f"Multi-step action entry stored: {subject} (ID: {action_id}, status: {status})")
        else:
            logging.info(f"Single-step action entry stored: {subject} (ID: {action_id}, status: {status})")
        return action_id

async def fetch_pending_action(action_id: int, db_path=DB_PATH) -> dict | None:
    """Fetch a pending action by ID for approval/execution"""
    async with aiosqlite.connect(db_path) as db:
        query = """SELECT id, subject, description, original_data, tool_id, tool_name, parameter, status
                   FROM actions WHERE id = ? AND status = 'pending'"""
        async with db.execute(query, (action_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "subject": row[1],
                    "description": row[2],
                    "original_data": row[3],
                    "tool_id": row[4],
                    "tool_name": row[5],
                    "parameter": row[6],
                    "status": row[7]
                }
            return None

async def update_action_status(action_id: int, status: str, response: str = None, db_path=DB_PATH):
    """Update an action's status and optionally its response"""
    async with aiosqlite.connect(db_path) as db:
        if response:
            await db.execute(
                "UPDATE actions SET status = ?, response = ? WHERE id = ?",
                (status, response, action_id)
            )
        else:
            await db.execute(
                "UPDATE actions SET status = ? WHERE id = ?",
                (status, action_id)
            )
        await db.commit()
        logging.info(f"Action {action_id} status updated to: {status}")

async def fetch_latest_messages(user, limit=CONVERSATION_HISTORY_LIMIT, db_path=DB_PATH) -> List[Tuple[str, str]]:
    """Fetch latest N messages for conversation history

    Args:
        user: User identifier
        limit: Maximum number of messages to fetch
    """
    async with aiosqlite.connect(db_path) as db:
        query = "SELECT role, message FROM memory WHERE user = ? ORDER BY id DESC LIMIT ?"
        params = (user, limit)

        async with db.execute(query, params) as cursor:
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

async def get_setting(key: str, db_path=DB_PATH) -> str:
    """Get a setting value from the settings table"""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_setting(key: str, value: str, db_path=DB_PATH):
    """Set a setting value (insert or update)"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?, timestamp = CURRENT_TIMESTAMP",
            (key, value, value)
        )
        await db.commit()

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

async def fetch_all_actions(db_path=DB_PATH) -> List[dict]:
    """Fetch all action entries from actions table (audit log)"""
    async with aiosqlite.connect(db_path) as db:
        query = """SELECT id, subject, description, original_data, tool_id, tool_name, parameter, response, status, is_multi_step, steps, timestamp
                   FROM actions ORDER BY timestamp DESC"""
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()

        actions_list = []
        for row in rows:
            action_dict = {
                "id": row[0],
                "subject": row[1],
                "description": row[2],
                "original_data": row[3],
                "tool_id": row[4],
                "tool_name": row[5],
                "parameter": row[6],
                "response": row[7],
                "status": row[8],
                "is_multi_step": bool(row[9]),
                "timestamp": row[11]
            }

            # Parse steps if it's a multi-step action
            if row[9]:  # is_multi_step
                try:
                    action_dict["steps"] = json.loads(row[10]) if row[10] else []
                except json.JSONDecodeError:
                    action_dict["steps"] = []
            else:
                action_dict["steps"] = None

            actions_list.append(action_dict)

        return actions_list

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
        augmented_system_prompt = FILE_RAG_PROMPT_TEMPLATE.format(prompt=user_query, context=file_content)

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
        history = await fetch_latest_messages(user_id, limit=10)

        messages = [
            {"role": "system", "content": augmented_system_prompt},
        ]

        # Add conversation history (user and assistant messages only)
        for role, message in history:
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": message})

        # Add context as a separate system message if found
        if context != "No specific business knowledge found in the database.":
            messages.append({"role": "system", "content": f"RELEVANT CONTEXT:\n{context}"})

        # Add the user's actual query
        messages.append({"role": "user", "content": user_query})

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
    tool_name: str,
    tool_result: dict,
    subject: str = ""
) -> str:
    """Convert tool JSON response to natural language using LLM (async version)"""
    loop = asyncio.get_running_loop()

    def generate_response():
        try:
            # Extract the actual response content from the tool result
            content_items = tool_result.get("content", [])
            if content_items and len(content_items) > 0:
                tool_output = content_items[0].get("text", str(tool_result))
            else:
                tool_output = str(tool_result)

            # Create prompt for LLM to interpret the response
            prompt = f"""Convert this tool execution result into a direct, factual statement.

Tool: {tool_name}
Task: {subject if subject else 'Tool execution'}

Tool Response:
{tool_output}

Guidelines:
- Write in third person or passive voice - NO "you", "I", "we"
- State facts directly and concisely
- Include specific numbers, amounts, and data
- No congratulations, praise, or emotional language
- No phrases like "successfully", "great job", "went smoothly"
- Just state what happened and the result
- 1-2 short sentences maximum

Example good responses:
- "Account balance is €1000."
- "€200 sent to Steven. New balance: €800."
- "Transfer completed. Balance updated to €1500."

Factual statement:"""

            messages = [{"role": "user", "content": prompt}]

            response = create_chat_completion(
                messages=messages,
                max_tokens=200,
                temperature=0.3
            )

            natural_response = response['choices'][0]['message']['content'].strip()
            return natural_response

        except Exception as e:
            logging.error(f"Error generating natural language response: {e}")
            # Fallback to a simple extraction
            content_items = tool_result.get("content", [])
            if content_items and len(content_items) > 0:
                return content_items[0].get("text", "Tool executed.")
            return "Tool executed."

    return await loop.run_in_executor(None, generate_response)


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

async def handle_upload_knowledge(cell, transmitter: dict):
    """Handle adding knowledge to database"""
    data = transmitter.get("data", {})
    knowledge_topic = data.get("knowledge_topic", None)
    knowledge_data = data.get("knowledge_data", None)
    cell_id = transmitter.get("operator", "default_user")

    logging.info("Adding knowledge to database...")
    await add_knowledge_entry(knowledge_topic, knowledge_data)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge updated"},
        data.get("public_key", "")
    )

async def handle_get_status(cell, transmitter: dict):
    """Handle agent status request (health check)"""
    data = transmitter.get("data", {})
    logging.info("Checking Agent Status")

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "running"},
        data.get("public_key", "")
    )

async def handle_get_icebreaker(cell, transmitter: dict):
    """Handle getting the icebreaker/welcome message for customers"""
    data = transmitter.get("data", {})
    operator = transmitter.get("operator", {})
    logging.info("Fetching icebreaker message")

    icebreaker = await get_setting("icebreaker")
    if not icebreaker:
        icebreaker = "Welcome to Neuronum Webserver!"

    # Load and render template
    template = env.get_template("welcome.html")
    html_content = template.render(
        welcome_message=f"Welcome to Neuronum!",
    )

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": icebreaker, "html": html_content},
        data.get("public_key", "")
    )

async def handle_update_icebreaker(cell, transmitter: dict):
    """Handle updating the icebreaker/welcome message"""
    data = transmitter.get("data", {})
    icebreaker = data.get("icebreaker", "")

    logging.info("Updating icebreaker message...")
    await set_setting("icebreaker", icebreaker)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "icebreaker updated"},
        data.get("public_key", "")
    )

async def handle_update_knowledge(cell, transmitter: dict):
    """Handle updating existing knowledge in database"""
    data = transmitter.get("data", {})
    knowledge_id = data.get("knowledge_id", None)
    knowledge_data = data.get("knowledge_data", None)
    cell_id = transmitter.get("operator", "default_user")

    logging.info("Updating knowledge in database...")
    await update_knowledge_entry(knowledge_id, knowledge_data)

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
    cell_id = transmitter.get("operator", "default_user")

    logging.info("Deleting knowledge from database...")
    await delete_knowledge_entry(knowledge_id)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": "knowledge deleted"},
        data.get("public_key", "")
    )

async def handle_get_knowledge(cell, transmitter: dict):
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

async def handle_get_actions(cell, transmitter: dict):
    """Handle fetching all actions from database (audit log)"""
    data = transmitter.get("data", {})
    logging.info("Fetching actions audit log")

    actions_list = await fetch_all_actions()
    logging.info(f"Retrieved {len(actions_list)} actions")

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": actions_list},
        data.get("public_key", "")
    )


async def handle_approve(cell, transmitter: dict):
    """Handle customer approval of a pending action

    Payload: {type: "approve", action_id: X}
    """
    data = transmitter.get("data", {})
    action_id = data.get("action_id")
    customer_id = transmitter.get("operator", "anonymous_customer")

    logging.info(f"[Customer {customer_id}] Approving action {action_id}")

    if not action_id:
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: action_id is required"},
            data.get("public_key", "")
        )
        return

    # Fetch the pending action
    pending_action = await fetch_pending_action(action_id)

    if not pending_action:
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Action not found or already processed"},
            data.get("public_key", "")
        )
        return

    tool_name = pending_action.get("tool_name")
    parameters = json.loads(pending_action.get("parameter", "{}"))
    original_data = json.loads(pending_action.get("original_data", "{}"))
    customer_user_id = original_data.get("customer_user_id", f"customer_{customer_id}")

    try:
        # Execute the tool
        registry = await tool_registry.get_registry()
        mcp_result = await registry.call_tool(tool_name, parameters, customer_id)
        logging.info(f"[Approved Tool Result]: {mcp_result}")

        # Convert tool result to natural language
        tool_response = await convert_tool_result_to_natural_language(
            tool_name,
            mcp_result,
            pending_action.get("subject", "")[:50]
        )

        # Update action status to success
        await update_action_status(action_id, "success", tool_response)

        await store_message(customer_user_id, "assistant", tool_response)

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": tool_response},
            data.get("public_key", "")
        )

    except Exception as tool_error:
        logging.error(f"Approved tool execution failed: {tool_error}")
        error_message = "I apologize, but I encountered an issue while processing your request."

        # Update action status to failed
        await update_action_status(action_id, "failed", str(tool_error))

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_message},
            data.get("public_key", "")
        )


async def handle_decline(cell, transmitter: dict):
    """Handle customer declining a pending action

    Payload: {type: "decline", action_id: X}
    """
    data = transmitter.get("data", {})
    action_id = data.get("action_id")
    customer_id = transmitter.get("operator", "anonymous_customer")

    logging.info(f"[Customer {customer_id}] Declining action {action_id}")

    if not action_id:
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: action_id is required"},
            data.get("public_key", "")
        )
        return

    # Fetch the pending action
    pending_action = await fetch_pending_action(action_id)

    if not pending_action:
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Action not found or already processed"},
            data.get("public_key", "")
        )
        return

    # Update action status to dismissed
    await update_action_status(action_id, "dismissed", "Declined by customer")

    original_data = json.loads(pending_action.get("original_data", "{}"))
    customer_user_id = original_data.get("customer_user_id", f"customer_{customer_id}")

    decline_message = "No problem, I've cancelled that action. Is there anything else I can help you with?"

    await store_message(customer_user_id, "assistant", decline_message)

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": decline_message},
        data.get("public_key", "")
    )


async def handle_prompt(cell, transmitter: dict):
    """Handle customer prompt with conversational tool capability

    This customer-facing endpoint:
    - Answers questions based on the agent's knowledge base
    - Can use customer-accessible tools in a conversational flow
    - Can escalate requests to the queue for employee handling
    - Maintains separate conversation history per customer
    """
    data = transmitter.get("data", {})
    prompt = data.get("prompt", "")
    customer_id = transmitter.get("operator", "anonymous_customer")

    logging.info(f"[Customer {customer_id}]: {prompt}")

    if not prompt:
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: No prompt provided"},
            data.get("public_key", "")
        )
        return

    try:
        # Retrieve relevant knowledge from database
        context = await retrieve_knowledge(prompt)

        # Fetch customer's conversation history
        customer_user_id = f"customer_{customer_id}"
        history = await fetch_latest_messages(customer_user_id, limit=10)

        # Get all available tools for customer use
        registry = await tool_registry.get_registry()
        customer_tools = await registry.get_all_tools()

        # Build tool descriptions for LLM
        tool_info_list = []
        for tool in customer_tools:
            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            required_params = input_schema.get("required", [])

            params_desc = []
            for param_name, param_def in properties.items():
                if param_name == "operator":  # Hide internal operator param
                    continue
                is_required = "(REQUIRED)" if param_name in required_params else "(optional)"
                params_desc.append(f"  - {param_name} {is_required}: {param_def.get('description', '')}")

            package_info = ""
            if tool.get("package_name"):
                package_info = f"\nPackage: {tool['package_name']}"
                if tool.get("package_description"):
                    package_info += f" - {tool['package_description']}"

            tool_info = f"""Tool: {tool['name']}
Description: {tool.get('description', 'No description')}{package_info}
Parameters:
{chr(10).join(params_desc) if params_desc else '  none'}"""
            tool_info_list.append(tool_info)

        tools_context = "\n\n".join(tool_info_list) if tool_info_list else "No tools available."

        # Build system prompt with tool awareness
        system_prompt = textwrap.dedent(f"""
            You are a customer service assistant that helps customers by answering questions or executing tools.

            AVAILABLE TOOLS:
            {tools_context}

            DECISION RULES:
            - If the customer asks a question → use action "answer"
            - If the customer wants to perform an action AND a suitable tool exists → use action "tool"
            - If you need more information to use a tool → use action "clarify"
            - If no tool can handle the request → use action "escalate"

            RESPONSE FORMAT - You MUST respond with ONLY valid JSON, nothing else:

            For answering questions:
            {{"action": "answer", "message": "Your response here"}}

            For executing a tool - you MUST include ALL required parameters from the tool definition:
            {{"action": "tool", "tool_name": "exact_tool_name", "parameters": {{"param1": "value1", "param2": "value2"}}, "message": "Confirmation message with ALL details"}}

            For asking clarification:
            {{"action": "clarify", "message": "What information do you need?"}}

            For escalating:
            {{"action": "escalate", "reason": "Why", "message": "Message to customer"}}

            CRITICAL RULES FOR TOOL CALLS:
            - Copy the EXACT tool_name from AVAILABLE TOOLS
            - Include EVERY parameter marked (REQUIRED) - missing required parameters will cause errors
            - The "parameters" object must contain all required parameter names with appropriate values
            - Extract parameter values from the user's request or conversation context
            - IMPORTANT: The "message" field must be a CONFIRMATION REQUEST that includes ALL the specific details (dates, times, names, locations, etc.) so the customer can verify before approving. Example: "I'll schedule a meeting titled 'Prep Talk' for today at 4pm in Office Room 16 with Yannis. Should I proceed?"

            Respond with JSON only:
        """)

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for role, message in history:
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": message})

        # Add knowledge context if found
        if context != "No specific business knowledge found in the database.":
            messages.append({"role": "system", "content": f"KNOWLEDGE CONTEXT:\n{context}"})

        # Add the customer's question
        messages.append({"role": "user", "content": prompt})

        logging.info(f"[Customer Messages for Agent]: {len(messages)} messages, {len(customer_tools)} tools available")

        # Generate response
        loop = asyncio.get_running_loop()

        def generate_response():
            response = create_chat_completion(
                messages=messages,
                max_tokens=MODEL_MAX_TOKENS,
                temperature=0.3  # Lower temperature for more consistent JSON
            )
            content = response['choices'][0]['message']['content']
            return content.strip()

        result_json = await loop.run_in_executor(None, generate_response)

        # Parse JSON response - find JSON anywhere in the response
        result_json = result_json.replace("```json", "").replace("```", "").strip()

        # Find the first '{' in the response
        json_start = result_json.find('{')
        if json_start != -1:
            brace_count = 0
            end_index = json_start
            for i, char in enumerate(result_json[json_start:], start=json_start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_index = i + 1
                        break
            result_json = result_json[json_start:end_index]

        try:
            decision = json.loads(result_json)
        except json.JSONDecodeError:
            # Fallback: treat as plain text answer
            decision = {"action": "answer", "message": result_json}

        action = decision.get("action", "answer")
        customer_message = decision.get("message", "I'm here to help. Could you please rephrase your question?")

        logging.info(f"[Customer Agent Decision]: action={action}")

        if action == "answer" or action == "clarify":
            # Simply respond to customer
            logging.info(f"[Agent to Customer]: {customer_message}")

            await store_message(customer_user_id, "user", prompt)
            await store_message(customer_user_id, "assistant", customer_message)

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": customer_message},
                data.get("public_key", "")
            )

        elif action == "tool":
            # Execute customer tool
            tool_name = decision.get("tool_name", "")
            parameters = decision.get("parameters", {})

            logging.info(f"[Customer Tool Execution]: {tool_name} with params {parameters}")

            # Verify tool is customer-accessible
            tool_info = next((t for t in customer_tools if t["name"] == tool_name), None)
            if not tool_info:
                # Tool not available - escalate instead
                logging.warning(f"Customer attempted to use non-accessible tool: {tool_name}")
                customer_message = "I apologize, but I'm unable to perform that action directly. Let me forward your request to our team."

                # Escalate to queue
                await add_customer_request_to_queue(customer_id, prompt, "Tool not available for customers")

                await store_message(customer_user_id, "user", prompt)
                await store_message(customer_user_id, "assistant", customer_message)

                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": customer_message},
                    data.get("public_key", "")
                )
                return

            # Store as pending action for customer approval
            action_id = await store_action_entry(
                subject=prompt[:100],
                context=f"Customer {customer_id} tool suggestion",
                original_data=json.dumps({"prompt": prompt, "customer_id": customer_id, "customer_user_id": customer_user_id}),
                tool_name=tool_name,
                parameter=json.dumps(parameters),
                status="pending"
            )

            logging.info(f"[Pending Action Created]: ID {action_id} for tool {tool_name}")

            await store_message(customer_user_id, "user", prompt)
            await store_message(customer_user_id, "assistant", customer_message)

            # Send response with action_id for frontend to render approve button
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": customer_message, "action_id": action_id},
                data.get("public_key", "")
            )

        elif action == "escalate":
            # Forward request to queue for employee handling
            reason = decision.get("reason", "Requires human assistance")
            logging.info(f"[Customer Escalation]: {reason}")

            await add_customer_request_to_queue(customer_id, prompt, reason)

            await store_message(customer_user_id, "user", prompt)
            await store_message(customer_user_id, "assistant", customer_message)

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": customer_message},
                data.get("public_key", "")
            )

        else:
            # Unknown action - treat as answer
            await store_message(customer_user_id, "user", prompt)
            await store_message(customer_user_id, "assistant", customer_message)

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": customer_message},
                data.get("public_key", "")
            )

    except Exception as e:
        logging.error(f"Error handling customer prompt: {e}")
        import traceback
        logging.error(traceback.format_exc())

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "I apologize, but I'm having trouble processing your request. Please try again."},
            data.get("public_key", "")
        )


async def add_customer_request_to_queue(customer_id: str, prompt: str, reason: str):
    """Add a customer request to the queue for employee handling"""
    import uuid

    queue_dir = "./queue"
    os.makedirs(queue_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"customer_{timestamp}_{unique_id}.json"
    file_path = os.path.join(queue_dir, filename)

    queue_data = {
        "prompt": f"[Customer Request from {customer_id}]\n\nOriginal request: {prompt}\n\nEscalation reason: {reason}",
        "cell_id": customer_id,
        "source": "customer_escalation"
    }

    with open(file_path, 'w') as f:
        json.dump(queue_data, f)

    logging.info(f"Customer request escalated to queue: {filename}")


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

        response_data = {
            "tools": tools_by_id
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

async def handle_install_tool(cell, transmitter: dict):
    """Handle adding new Tool tool from registry and restart agent"""
    data = transmitter.get("data", {})
    tool_id = data.get("tool_id", "")
    variables = data.get("variables", "")
    cell_id = transmitter.get("operator", "default_user")

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
    cell_id = transmitter.get("operator", "default_user")

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

        logging.info(f"Tool '{tool_id}' successfully deleted. Files removed: {', '.join(files_deleted)}")

        logging.info("Restarting agent...")

        await cell.close()

        await asyncio.sleep(1)

        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        logging.error(f"Error deleting tool: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())


# Message Routing

def is_authorized_internal_cell(operator: str, server_host: str) -> bool:
    """Check if operator is authorized to access internal handlers

    Authorization is based on the server's cell_id (host):
    - If server is 'neuronum.net::cell', authorized operators are:
      - 'neuronum.net::cell' (the business cell itself)
      - '*@neuronum.net::cell' (employees with emails from that domain)

    Args:
        operator: The cell_id of the request sender
        server_host: The cell_id of this server (cell.host)

    Returns:
        True if operator belongs to this organization, False otherwise
    """
    if not operator or not server_host:
        return False

    # Extract domain from server host (e.g., 'neuronum.net' from 'neuronum.net::cell')
    if not server_host.endswith("::cell"):
        return False

    server_domain = server_host[:-6]  # Remove '::cell'

    # Check if operator is the business cell itself
    if operator == server_host:
        return True

    # Check if operator is an employee (email@domain::cell)
    if operator.endswith("::cell"):
        operator_id = operator[:-6]  # Remove '::cell'

        # Employee pattern: user@domain
        if "@" in operator_id:
            email_domain = operator_id.split("@")[-1]
            if email_domain == server_domain:
                return True

    return False


# Handlers that community/customers are allowed to access
CUSTOMER_ALLOWED_HANDLERS = {
    "prompt",
    "approve",
    "decline",
    "get_agent_status",
    "get_icebreaker"
}


async def route_message(cell, transmitter: dict):
    """Route incoming messages to appropriate handlers with access control"""
    try:
        data = transmitter.get("data", {})
        message_type = data.get("type", None)
        operator = transmitter.get("operator", "")

        # Get the server's cell_id to determine authorized cells
        server_host = cell.host or cell.env.get("HOST", "")

        # Check if operator is authorized for internal access
        is_internal = is_authorized_internal_cell(operator, server_host)

        # If not internal and trying to access internal handlers, deny access
        if not is_internal and message_type not in CUSTOMER_ALLOWED_HANDLERS:
            logging.warning(f"Access denied: '{operator}' attempted to access '{message_type}' (not authorized for {server_host})")
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": "Access denied: This endpoint is not available."},
                data.get("public_key", "")
            )
            return

        handlers = {
            "update_icebreaker": lambda: handle_update_icebreaker(cell, transmitter),
            "get_icebreaker": lambda: handle_get_icebreaker(cell, transmitter),
            "upload_knowledge": lambda: handle_upload_knowledge(cell, transmitter),
            "get_agent_status": lambda: handle_get_status(cell, transmitter),
            "update_knowledge": lambda: handle_update_knowledge(cell, transmitter),
            "delete_knowledge": lambda: handle_delete_knowledge(cell, transmitter),
            "get_knowledge": lambda: handle_get_knowledge(cell, transmitter),
            "get_actions": lambda: handle_get_actions(cell, transmitter),
            "prompt": lambda: handle_prompt(cell, transmitter),
            "approve": lambda: handle_approve(cell, transmitter),
            "decline": lambda: handle_decline(cell, transmitter),
            "get_tools": lambda: handle_get_tools(cell, transmitter),
            "install_tool": lambda: handle_install_tool(cell, transmitter),
            "delete_tool": lambda: handle_delete_tool(cell, transmitter)
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

        if not cell.host.startswith("neuronumagent"):
            await cell.stream(cell.host, {"json": "ping"})

        await process_cell_messages(cell)
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
