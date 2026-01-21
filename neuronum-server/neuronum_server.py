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
    You are a helpful assistant. You have access to three sources of information:

    1. CONVERSATION HISTORY - The previous user/assistant messages are your memory of past discussions.
       Use this to answer questions about what was discussed, recent activities, or follow-ups.

    2. RELEVANT CONTEXT - Knowledge retrieved from the database, marked with "RELEVANT CONTEXT:".
       This contains factual information. Trust it completely as the source of truth.

    3. SPACE CONTEXT - Instructions and knowledge for the current workspace, marked with "SPACE CONTEXT:".
       Follow any instructions provided and use the space knowledge to inform your answers.

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
                space_id TEXT,
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
                space_id TEXT,
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
             CREATE TABLE IF NOT EXISTS spaces (
                space_id,
                name,
                responsibility,
                instructions,
                knowledge,
                members
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS cell_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_cell_id TEXT,
                to_cell_id TEXT,
                message TEXT,
                is_read BOOLEAN DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()
        logging.info("Database initialized with FTS5 knowledge table.")

async def store_message(user, role, message, space_id=None, message_type="chat", context=None, db_path=DB_PATH):
    """Store message to memory table for conversation history

    Args:
        user: User identifier
        role: Message role (user, assistant, system)
        message: The message content
        space_id: Optional space_id to scope the conversation
        message_type: Type of message (chat, action_result, system_notification)
        context: Optional additional context (e.g., action_id reference)
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO memory (user, role, message, space_id, message_type, context) VALUES (?, ?, ?, ?, ?, ?)",
            (user, role, message, space_id, message_type, context)
        )
        await db.commit()

async def store_action_entry(subject: str, context: str, original_data: str, tool_id: str = None, tool_name: str = None, parameter: str = None, is_multi_step: bool = False, steps: str = None, space_id: str = None, status: str = 'pending', response: str = None, db_path=DB_PATH) -> int:
    """Store action entry in actions table

    Args:
        status: Action status ('pending', 'finished', 'failed', 'dismissed')
        response: Only used for failed actions to store error message

    Returns:
        The ID of the newly created action entry
    """
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO actions (subject, description, original_data, tool_id, tool_name, parameter, status, response, is_multi_step, steps, space_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (subject, context, original_data, tool_id, tool_name, parameter, status, response, is_multi_step, steps, space_id)
        )
        action_id = cursor.lastrowid
        await db.commit()
        if is_multi_step:
            logging.info(f"Multi-step action entry stored: {subject} (ID: {action_id}, status: {status})")
        else:
            logging.info(f"Single-step action entry stored: {subject} (ID: {action_id}, status: {status})")
        return action_id

async def fetch_latest_messages(user, limit=CONVERSATION_HISTORY_LIMIT, space_id=None, db_path=DB_PATH) -> List[Tuple[str, str]]:
    """Fetch latest N messages for conversation history

    Args:
        user: User identifier
        limit: Maximum number of messages to fetch
        space_id: Optional space_id to filter messages (None = global/no space filter)
    """
    async with aiosqlite.connect(db_path) as db:
        if space_id:
            # Fetch messages specific to a space
            query = "SELECT role, message FROM memory WHERE user = ? AND space_id = ? ORDER BY id DESC LIMIT ?"
            params = (user, space_id, limit)
        else:
            # Fetch messages without space filter (global conversations or space_id is NULL)
            query = "SELECT role, message FROM memory WHERE user = ? AND (space_id IS NULL OR space_id = '') ORDER BY id DESC LIMIT ?"
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

def generate_multi_step_summary(subject: str, step_responses: list) -> str:
    """Generate natural language summary for multi-step action results"""
    try:
        # Format step responses for the prompt
        steps_text = ""
        for step in step_responses:
            step_order = step.get("step_order", "?")
            step_subject = step.get("step_subject", "Unknown")
            status = step.get("status", "unknown")
            response = step.get("response", "No response")
            steps_text += f"\nStep {step_order} - {step_subject} ({status}):\n{response}\n"

        # Create prompt for overall summary
        prompt = f"""Convert these multi-step execution results into a direct, factual summary.

Task: {subject}

Step Results:
{steps_text}

Guidelines:
- Write in third person or passive voice - NO "you", "I", "we"
- State facts directly and concisely
- Include specific numbers, amounts, and data from each step
- No congratulations, praise, or emotional language
- No phrases like "successfully", "great job", "went smoothly", "as planned"
- Just state what happened in each step
- 2-3 short sentences maximum

Example good format:
- "Account balance is €1000. €200 sent to Steven. New balance: €800."
- "Balance checked: €500. Transfer failed: insufficient funds."

Factual summary:"""

        messages = [{"role": "user", "content": prompt}]

        response = create_chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0.3
        )

        natural_summary = response['choices'][0]['message']['content'].strip()
        return natural_summary

    except Exception as e:
        logging.error(f"Error generating multi-step summary: {e}")
        # Fallback to simple summary
        success_count = sum(1 for step in step_responses if step.get("status") == "success")
        total_count = len(step_responses)
        return f"Completed {success_count} out of {total_count} steps for: {subject}"

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

async def fetch_all_actions(cell_id: str = None, db_path=DB_PATH) -> List[dict]:
    """Fetch action entries from actions table filtered by user access

    Args:
        cell_id: The user's cell_id. If provided, only returns actions where:
                 - space_id matches cell_id (user's own actions), OR
                 - user is a member of the space (cell_id in space's members field), OR
                 - space_id is NULL (unassigned actions from queue processing)
                 If None, returns all actions (for admin/internal use)
    """
    async with aiosqlite.connect(db_path) as db:
        if cell_id:
            # First, get all space_ids where this user is a member
            spaces_query = "SELECT space_id, members FROM spaces"
            async with db.execute(spaces_query) as cursor:
                spaces_rows = await cursor.fetchall()

            # Find spaces where cell_id is in members
            accessible_space_ids = []
            for space_row in spaces_rows:
                space_id = space_row[0]
                members = space_row[1] or ""
                # Check if cell_id is in the members string (comma-separated or contains)
                if cell_id in members:
                    accessible_space_ids.append(space_id)

            # Build query to get actions for user's own space_id OR accessible spaces OR unassigned (NULL)
            if accessible_space_ids:
                placeholders = ",".join("?" * len(accessible_space_ids))
                query = f"""SELECT id, subject, description, original_data, tool_id, tool_name, parameter, response, status, is_multi_step, steps, space_id, timestamp
                           FROM actions
                           WHERE space_id = ? OR space_id IN ({placeholders}) OR space_id IS NULL
                           ORDER BY timestamp DESC"""
                params = [cell_id] + accessible_space_ids
            else:
                # Only user's own actions + unassigned actions
                query = """SELECT id, subject, description, original_data, tool_id, tool_name, parameter, response, status, is_multi_step, steps, space_id, timestamp
                           FROM actions
                           WHERE space_id = ? OR space_id IS NULL
                           ORDER BY timestamp DESC"""
                params = [cell_id]

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        else:
            # No cell_id filter - return all actions
            query = """SELECT id, subject, description, original_data, tool_id, tool_name, parameter, response, status, is_multi_step, steps, space_id, timestamp
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
                "space_id": row[11],
                "timestamp": row[12]
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

async def fetch_all_spaces(db_path=DB_PATH) -> List[dict]:
    """Fetch all space entries from spaces table"""
    async with aiosqlite.connect(db_path) as db:
        query = """SELECT space_id, name, responsibility, instructions, knowledge, members
                   FROM spaces"""

        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()

            spaces_list = []
            for row in rows:
                space_dict = {
                    "space_id": row[0],
                    "name": row[1],
                    "responsibility": row[2],
                    "instructions": row[3],
                    "knowledge": row[4],
                    "members": row[5]
                }

                spaces_list.append(space_dict)

            return spaces_list

async def fetch_space_by_id(space_id: str, db_path=DB_PATH) -> dict:
    """Fetch a specific space by its space_id"""
    if not space_id:
        return None

    async with aiosqlite.connect(db_path) as db:
        query = """SELECT space_id, name, responsibility, instructions, knowledge, members
                   FROM spaces WHERE space_id = ?"""

        async with db.execute(query, (space_id,)) as cursor:
            row = await cursor.fetchone()

            if row:
                return {
                    "space_id": row[0],
                    "name": row[1],
                    "responsibility": row[2],
                    "instructions": row[3],
                    "knowledge": row[4],
                    "members": row[5]
                }
            return None

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


async def get_model_answer(user_id: str, user_query: str, file: bool = False, file_content: str = "", space_context: dict = None) -> str:
    """Core RAG function for generating answers with context"""
    loop = asyncio.get_running_loop()

    # Extract space_id from space_context if provided
    space_id = space_context.get("space_id") if space_context else None

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
            await store_message(user_id, "user", full_prompt, space_id=space_id)
            await store_message(user_id, "assistant", answer, space_id=space_id)
        else:
            logging.warning("Warning: Model returned empty response, not storing in conversation history")

        return answer
    else:
        context = await retrieve_knowledge(user_query)
        augmented_system_prompt = RAG_PROMPT_TEMPLATE
        # Fetch messages filtered by space_id if provided
        history = await fetch_latest_messages(user_id, limit=10, space_id=space_id)

        # Start with fresh system prompt
        messages = [
            {"role": "system", "content": augmented_system_prompt},
        ]

        # Add space context if provided (instructions and knowledge from space)
        if space_context:
            space_instructions = space_context.get("instructions", "")
            space_knowledge = space_context.get("knowledge", "")
            space_name = space_context.get("name", "")
            space_responsibility = space_context.get("responsibility", "")

            space_context_parts = []
            if space_name:
                space_context_parts.append(f"Space: {space_name}")
            if space_responsibility:
                space_context_parts.append(f"Responsibility: {space_responsibility}")
            if space_instructions:
                space_context_parts.append(f"Instructions: {space_instructions}")
            if space_knowledge:
                space_context_parts.append(f"Knowledge: {space_knowledge}")

            if space_context_parts:
                messages.append({"role": "system", "content": f"SPACE CONTEXT:\n{chr(10).join(space_context_parts)}"})

        # Add conversation history, but filter out old system messages
        # Only keep user and assistant messages to preserve conversation flow
        for role, message in history:
            if role in ["user", "assistant"]:
                messages.append({"role": role, "content": message})

        # Add context as a separate system message if found, not merged with user query
        if context != "No specific business knowledge found in the database.":
            messages.append({"role": "system", "content": f"RELEVANT CONTEXT:\n{context}"})

        # Add the user's actual query without modifications
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
            await store_message(user_id, "user", user_query, space_id=space_id)
            await store_message(user_id, "assistant", answer, space_id=space_id)
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


# Queue Processing Functions

def move_queue_file_to_processed(file_path: str, prefix: str = "") -> str:
    """Helper to move queue file to processed folder"""
    queue_dir = "./queue"
    processed_dir = os.path.join(queue_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    filename = os.path.basename(file_path)
    if prefix:
        processed_path = os.path.join(processed_dir, f"{prefix}_{filename}")
    else:
        processed_path = os.path.join(processed_dir, filename)

    # If file already exists in processed, add timestamp
    if os.path.exists(processed_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        processed_path = os.path.join(processed_dir, f"{prefix}_{name}_{timestamp}{ext}" if prefix else f"{name}_{timestamp}{ext}")

    os.rename(file_path, processed_path)
    return processed_path


async def send_queue_notification(cell, cell_id: str, space_id: str, title: str, message: str, action_id: int = None):
    """Send notification to cell_id or all members of a space"""
    try:
        notification_data = {"title": title, "message": message}
        if action_id is not None:
            notification_data["action_id"] = action_id

        if space_id and space_id != cell_id:
            # Fetch space to get members
            space = await fetch_space_by_id(space_id)
            if space and space.get("members"):
                # Parse members (comma-separated string)
                members_str = space.get("members", "")
                members = [m.strip() for m in members_str.split(",") if m.strip()]

                # Send notification to each member
                for member_id in members:
                    try:
                        await cell.stream(member_id, {"notification": notification_data})
                        logging.info(f"Notification sent to space member: {member_id}")
                    except Exception as e:
                        logging.warning(f"Failed to send notification to {member_id}: {e}")
            else:
                # No members, send to cell_id as fallback
                await cell.stream(cell_id, {"notification": notification_data})
                logging.info(f"Notification sent to: {cell_id}")
        else:
            # No space_id or space_id equals cell_id, send directly to cell_id
            await cell.stream(cell_id, {"notification": notification_data})
            logging.info(f"Notification sent to: {cell_id}")
    except Exception as e:
        logging.error(f"Error sending queue notification: {e}")


async def process_queue_file(file_path: str, registry, cell) -> bool:
    """Process a single queue file and create action entry"""
    try:
        # Read the queue file (JSON format)
        with open(file_path, 'r') as f:
            file_content = f.read().strip()

        if not file_content:
            error_msg = "Empty queue file - no content to process"
            logging.warning(f"Empty queue file: {file_path}")

            # Store as failed action entry
            await store_action_entry(
                subject="Empty queue request",
                context="Failed to process - empty file",
                original_data="",
                status='failed',
                response=error_msg
            )

            processed_path = move_queue_file_to_processed(file_path, "empty")
            logging.info(f"Queue file moved to: {processed_path}")
            return False

        # Parse JSON to extract prompt, space_id, and cell_id
        try:
            queue_data = json.loads(file_content)
            original_data = queue_data.get("prompt", "")
            space_id = queue_data.get("space_id", None)
            cell_id = queue_data.get("cell_id", "default_user")
        except json.JSONDecodeError:
            # Fallback for legacy .txt files - treat content as prompt
            original_data = file_content
            space_id = None
            cell_id = "default_user"

        if not original_data:
            error_msg = "No prompt provided in queue request"
            logging.warning(f"No prompt in queue file: {file_path}")

            # Store as failed action entry
            await store_action_entry(
                subject="Invalid queue request",
                context="Failed to process - no prompt provided",
                original_data=file_content,
                space_id=space_id,
                status='failed',
                response=error_msg
            )

            processed_path = move_queue_file_to_processed(file_path, "no_prompt")
            logging.info(f"Queue file moved to: {processed_path}")
            return False

        logging.info(f"Processing queue file: {file_path}")
        if space_id:
            logging.info(f"Queue item has space_id: {space_id}")

        # Fetch space context if space_id is provided
        space_context = None
        if space_id:
            space_context = await fetch_space_by_id(space_id)
            if space_context:
                logging.info(f"Using space context for queue item: {space_context.get('name')}")

        # Get available tools
        available_tools = await registry.get_all_tools()

        if not available_tools:
            error_msg = "No tools available for queue processing"
            logging.error(error_msg)

            # Store as failed action entry
            await store_action_entry(
                subject=original_data[:100],
                context="Failed to process - no tools available",
                original_data=original_data,
                space_id=space_id,
                status='failed',
                response=error_msg
            )

            processed_path = move_queue_file_to_processed(file_path, "no_tools")
            logging.info(f"Queue file moved to: {processed_path}")
            return False

        # Build tool list for LLM
        tool_info_list = []
        for tool in available_tools:
            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})

            params_desc = []
            for param_name, param_def in properties.items():
                params_desc.append(f"{param_name} ({param_def.get('type', 'string')}): {param_def.get('description', '')}")

            tool_info = f"""Tool ID: {tool.get('server', 'unknown')}
Tool Name: {tool['name']}
Description: {tool.get('description', 'No description')}
Parameters: {', '.join(params_desc) if params_desc else 'none'}"""
            tool_info_list.append(tool_info)

        # Build space context string for the prompt
        space_context_str = ""
        if space_context:
            space_parts = []
            if space_context.get("name"):
                space_parts.append(f"Space: {space_context.get('name')}")
            if space_context.get("responsibility"):
                space_parts.append(f"Responsibility: {space_context.get('responsibility')}")
            if space_context.get("instructions"):
                space_parts.append(f"Instructions: {space_context.get('instructions')}")
            if space_context.get("knowledge"):
                space_parts.append(f"Knowledge: {space_context.get('knowledge')}")
            if space_parts:
                space_context_str = f"\n\nSPACE CONTEXT:\n{chr(10).join(space_parts)}\n"

        # Create LLM prompt for analysis
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        analysis_prompt = f"""Analyze the following request/dataset and determine if it requires multiple steps to complete.

CRITICAL: If NONE of the available tools can fulfill the user's request, you MUST respond with "no_tool_available" instead of forcing an inappropriate tool.

IMPORTANT: Think critically about what prerequisite steps, safety checks, or validations are needed BEFORE executing the main action, even if the request doesn't explicitly mention them.

Examples of implicit prerequisites:
- Money transfers → Check balance first
- Deleting data → Backup or verification first
- Sending messages → Validate recipient exists
- Booking reservations → Check availability first
- Updating records → Fetch current state first

REQUEST/DATASET:
{original_data}
Sent by: {cell_id} at {current_timestamp}
{space_context_str}
AVAILABLE TOOLS:
{chr(10).join(tool_info_list)}

Your task:
1. Identify the PRIMARY goal of the request
2. Determine what PREREQUISITE steps are needed (validation, checks, fetching data) BEFORE the main action
3. If prerequisites are needed OR multiple actions are required → MULTI-STEP
4. If it's truly a single, safe operation with no prerequisites → SINGLE STEP
5. If NO tools can fulfill the request → NO TOOL AVAILABLE

CRITICAL THINKING REQUIRED:
- Does this action need validation before execution? (e.g., check balance before transfer)
- Does this action modify important data? (should we check current state first?)
- Does this action have dependencies? (e.g., need to verify something exists first)
- Could this action fail if preconditions aren't met?
- Are the available tools actually capable of fulfilling this request?

For MULTI-STEP requests, respond with:
{{
  "is_multi_step": true,
  "overall_subject": "Brief overall subject (5-10 words)",
  "steps": [
    {{
      "step_order": 1,
      "subject": "Step 1 subject (usually prerequisite/check)",
      "context": "Why this check is needed",
      "tool_id": "tool_id",
      "tool_name": "tool_name",
      "parameters": {{"param1": "value1"}}
    }},
    {{
      "step_order": 2,
      "subject": "Step 2 subject (main action)",
      "context": "The actual requested action",
      "tool_id": "tool_id",
      "tool_name": "tool_name",
      "parameters": {{"param1": "value1"}}
    }}
  ]
}}

For SINGLE-STEP requests (only if no prerequisites needed), respond with:
{{
  "is_multi_step": false,
  "subject": "Brief subject here",
  "context": "Description of what needs to be done",
  "tool_id": "selected_tool_id",
  "tool_name": "selected_tool_name",
  "parameters": {{"param1": "value1", "param2": 123}}
}}

For NO SUITABLE TOOL available, respond with:
{{
  "no_tool_available": true,
  "reason": "Brief explanation of what capability is missing"
}}

Use proper JSON types - numbers as numbers, booleans as true/false, strings as quoted text.

JSON:"""

        # Get LLM analysis
        loop = asyncio.get_running_loop()

        def get_analysis():
            messages = [
                {"role": "system", "content": "You are an intelligent task analyzer. Extract structured information from requests and match them to appropriate tools. Respond only with valid JSON."},
                {"role": "user", "content": analysis_prompt}
            ]

            response = create_chat_completion(
                messages=messages,
                max_tokens=500,
                temperature=0.2
            )
            content = response['choices'][0]['message']['content'].strip()
            return content

        logging.info("Using LLM to analyze queue item and select tool...")
        result_json = await loop.run_in_executor(None, get_analysis)

        # Clean up JSON response
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

        analysis = json.loads(result_json)

        # Check if no suitable tool is available
        if analysis.get("no_tool_available", False):
            reason = analysis.get("reason", "No suitable tool found")
            error_msg = f"No tool available: {reason}"
            logging.warning(f"Queue file {file_path}: {error_msg}")

            # Store as failed action entry for tracking
            await store_action_entry(
                subject=original_data[:100],
                context="Failed to process - no suitable tool available",
                original_data=original_data,
                space_id=space_id,
                status='failed',
                response=error_msg
            )

            # Move to processed folder
            processed_path = move_queue_file_to_processed(file_path, "no_tool")
            logging.info(f"Queue file moved to: {processed_path}")
            return False

        is_multi_step = analysis.get("is_multi_step", False)

        if is_multi_step:
            # Multi-step request - store as single action with steps as JSON
            overall_subject = analysis.get("overall_subject", "Multi-step request")
            steps = analysis.get("steps", [])

            logging.info(f"Multi-step queue analysis complete:")
            logging.info(f"  Overall Subject: {overall_subject}")
            logging.info(f"  Number of steps: {len(steps)}")

            # Log each step
            for step in steps:
                step_order = step.get("step_order", 1)
                subject = step.get("subject", f"Step {step_order}")
                tool_name = step.get("tool_name", "")
                logging.info(f"  Step {step_order}: {subject} using {tool_name}")

            # Store as single action entry with steps as JSON string
            steps_str = json.dumps(steps)
            context = f"Multi-step action with {len(steps)} steps"

            action_id = await store_action_entry(
                subject=overall_subject,
                context=context,
                original_data=original_data,
                tool_id=None,
                tool_name=None,
                parameter=None,
                is_multi_step=True,
                steps=steps_str,
                space_id=space_id
            )

            notification_subject = overall_subject

        else:
            # Single-step request
            subject = analysis.get("subject", "Unknown Request")
            context = analysis.get("context", "No description provided")
            tool_id = analysis.get("tool_id", "")
            tool_name = analysis.get("tool_name", "")
            parameters = analysis.get("parameters", {})
            parameter_str = json.dumps(parameters)

            logging.info(f"Single-step queue analysis complete:")
            logging.info(f"  Subject: {subject}")
            logging.info(f"  Context: {context}")
            logging.info(f"  Tool ID: {tool_id}")
            logging.info(f"  Tool Name: {tool_name}")
            logging.info(f"  Parameters: {parameter_str}")

            # Store in actions database as single-step action
            action_id = await store_action_entry(
                subject=subject,
                context=context,
                original_data=original_data,
                tool_id=tool_id,
                tool_name=tool_name,
                parameter=parameter_str,
                is_multi_step=False,
                steps=None,
                space_id=space_id
            )

            notification_subject = subject

        # Move processed file to processed folder
        processed_path = move_queue_file_to_processed(file_path)
        logging.info(f"Queue file processed and moved to: {processed_path}")

        # Send notification to creator or space members
        if is_multi_step:
            notification_title = "New Action Created"
            notification_message = f"{notification_subject} - Multi-step action with {len(steps)} steps ready for review"
        else:
            notification_title = "New Action Created"
            notification_message = f"{notification_subject} - Ready for review"

        await send_queue_notification(cell, cell_id, space_id, notification_title, notification_message, action_id)

        return True

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM response: {str(e)}"
        logging.error(f"Failed to parse LLM response for queue file {file_path}: {e}")

        # Store as failed action entry - use original_data if available
        try:
            await store_action_entry(
                subject=original_data[:100] if 'original_data' in dir() and original_data else "LLM parse error",
                context="Failed to process - could not parse LLM response",
                original_data=original_data if 'original_data' in dir() and original_data else "",
                space_id=space_id if 'space_id' in dir() else None,
                status='failed',
                response=error_msg
            )
            processed_path = move_queue_file_to_processed(file_path, "parse_error")
            logging.info(f"Queue file moved to: {processed_path}")
        except Exception as store_error:
            logging.error(f"Failed to store error action: {store_error}")

        return False

    except Exception as e:
        error_msg = f"Error processing queue file: {str(e)}"
        logging.error(f"Error processing queue file {file_path}: {e}")
        import traceback
        logging.error(traceback.format_exc())

        # Store as failed action entry - use original_data if available
        try:
            await store_action_entry(
                subject=original_data[:100] if 'original_data' in dir() and original_data else "Processing error",
                context="Failed to process - unexpected error",
                original_data=original_data if 'original_data' in dir() and original_data else "",
                space_id=space_id if 'space_id' in dir() else None,
                status='failed',
                response=error_msg
            )
            processed_path = move_queue_file_to_processed(file_path, "error")
            logging.info(f"Queue file moved to: {processed_path}")
        except Exception as store_error:
            logging.error(f"Failed to store error action: {store_error}")

        return False


async def queue_processor_loop(registry, cell):
    """Background task that monitors and processes queue folder"""
    queue_dir = "./queue"
    os.makedirs(queue_dir, exist_ok=True)

    logging.info("Queue processor started, monitoring ./queue folder")

    while True:
        try:
            # Get all .json and .txt files in queue directory (json preferred, txt for backwards compatibility)
            queue_files = [
                os.path.join(queue_dir, f)
                for f in os.listdir(queue_dir)
                if (f.endswith('.json') or f.endswith('.txt')) and os.path.isfile(os.path.join(queue_dir, f))
            ]

            if queue_files:
                logging.info(f"Found {len(queue_files)} file(s) in queue")

                for file_path in queue_files:
                    success = await process_queue_file(file_path, registry, cell)
                    if success:
                        logging.info(f"Successfully processed: {file_path}")
                    else:
                        logging.warning(f"Failed to process: {file_path}")

                    # Small delay between files
                    await asyncio.sleep(1)

            # Check queue every 10 seconds
            await asyncio.sleep(10)

        except Exception as e:
            logging.error(f"Error in queue processor loop: {e}")
            import traceback
            logging.error(traceback.format_exc())
            await asyncio.sleep(10)


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

async def handle_get_actions(cell, transmitter: dict):
    """Handle fetching all actions from database (all statuses)

    Returns only actions where:
    - space_id matches the user's cell_id (user's own actions), OR
    - user is a member of the space (cell_id in space's members field)
    """
    data = transmitter.get("data", {})
    cell_id = transmitter.get("operator", "default_user")
    logging.info(f"Fetching actions for user: {cell_id}")

    actions_list = await fetch_all_actions(cell_id=cell_id)
    logging.info(f"Retrieved {len(actions_list)} actions for user {cell_id}")

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": actions_list},
        data.get("public_key", "")
    )

async def handle_get_spaces(cell, transmitter: dict):
    """Handle fetching all spaces from database"""
    data = transmitter.get("data", {})
    logging.info("Fetching all stored spaces...")

    spaces_list = await fetch_all_spaces()
    logging.info(f"Retrieved {len(spaces_list)} spaces")

    await send_cell_response(
        cell,
        transmitter.get("transmitter_id"),
        {"json": spaces_list},
        data.get("public_key", "")
    )

async def handle_create_space(cell, transmitter: dict):
    """Handle creating a new space in the database"""
    data = transmitter.get("data", {})
    name = data.get("name", None)
    responsibility = data.get("responsibility", "")
    instructions = data.get("instructions", "")
    knowledge = data.get("knowledge", "")
    members = data.get("members", "")
    cell_id = transmitter.get("operator", "default_user")

    combined = f"{name}:{responsibility}"
    space_id = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    if not space_id or not name:
        error_msg = "space_id and name are required to create a space"
        logging.error(error_msg)
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": f"Error: {error_msg}"},
            data.get("public_key", "")
        )
        return

    try:
        logging.info(f"Creating space: {name} (ID: {space_id})")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO spaces (space_id, name, responsibility, instructions, knowledge, members) VALUES (?, ?, ?, ?, ?, ?)",
                (space_id, name, responsibility, instructions, knowledge, members)
            )
            await db.commit()

        logging.info(f"Space created successfully: {name}")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": f"Space '{name}' created successfully"},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error creating space: {str(e)}"
        logging.error(error_msg)
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_delete_space(cell, transmitter: dict):
    """Handle deleting space from database"""
    data = transmitter.get("data", {})
    space_id = data.get("space_id", None)
    cell_id = transmitter.get("operator", "default_user")

    if not space_id:
        error_msg = "space_id is required to delete a space"
        logging.error(error_msg)
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": f"Error: {error_msg}"},
            data.get("public_key", "")
        )
        return

    try:
        logging.info(f"Deleting space from database: {space_id}")

        async with aiosqlite.connect(DB_PATH) as db:
            # First check if space exists and get its name
            async with db.execute(
                "SELECT name FROM spaces WHERE space_id = ?",
                (space_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                logging.warning(f"Space with ID '{space_id}' not found")
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": f"Error: Space with ID '{space_id}' not found"},
                    data.get("public_key", "")
                )
                return

            space_name = row[0]

            # Delete the space
            await db.execute(
                "DELETE FROM spaces WHERE space_id = ?",
                (space_id,)
            )
            await db.commit()

        logging.info(f"Space '{space_name}' deleted successfully")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": f"Space '{space_name}' deleted successfully"},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error deleting space: {str(e)}"
        logging.error(error_msg)
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_update_space(cell, transmitter: dict):
    """Handle updating existing space in database"""
    data = transmitter.get("data", {})
    space_id = data.get("space_id", None)
    name = data.get("name", None)
    responsibility = data.get("responsibility", None)
    instructions = data.get("instructions", None)
    knowledge = data.get("knowledge", None)
    members = data.get("members", None)
    cell_id = transmitter.get("operator", "default_user")

    if not space_id:
        error_msg = "space_id is required to update a space"
        logging.error(error_msg)
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": f"Error: {error_msg}"},
            data.get("public_key", "")
        )
        return

    try:
        logging.info(f"Updating space in database: {space_id}")

        async with aiosqlite.connect(DB_PATH) as db:
            # First check if space exists
            async with db.execute(
                "SELECT space_id FROM spaces WHERE space_id = ?",
                (space_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                logging.warning(f"Space with ID '{space_id}' not found")
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": f"Error: Space with ID '{space_id}' not found"},
                    data.get("public_key", "")
                )
                return

            # Build dynamic UPDATE query for provided fields
            update_fields = []
            update_values = []

            if name is not None:
                update_fields.append("name = ?")
                update_values.append(name)
            if responsibility is not None:
                update_fields.append("responsibility = ?")
                update_values.append(responsibility)
            if instructions is not None:
                update_fields.append("instructions = ?")
                update_values.append(instructions)
            if knowledge is not None:
                update_fields.append("knowledge = ?")
                update_values.append(knowledge)
            if members is not None:
                update_fields.append("members = ?")
                update_values.append(members)

            if not update_fields:
                error_msg = "No fields provided to update"
                logging.warning(error_msg)
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": f"Error: {error_msg}"},
                    data.get("public_key", "")
                )
                return

            # Add space_id to values for WHERE clause
            update_values.append(space_id)

            # Execute UPDATE query
            query = f"UPDATE spaces SET {', '.join(update_fields)} WHERE space_id = ?"
            await db.execute(query, tuple(update_values))
            await db.commit()

        logging.info(f"Space with ID '{space_id}' updated successfully")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": f"Space updated successfully"},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error updating space: {str(e)}"
        logging.error(error_msg)
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_execute_action(cell, transmitter: dict):
    """Handle executing an action (single or multi-step) from the actions database"""
    data = transmitter.get("data", {})
    action_id = data.get("action_id", "")
    cell_id = transmitter.get("operator", "default_user")

    if not action_id:
        logging.error("No action_id provided for execution")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Action ID is required"},
            data.get("public_key", "")
        )
        return

    try:
        # Fetch the action from database
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT subject, description, tool_id, tool_name, parameter, is_multi_step, steps FROM actions WHERE id = ?",
                (action_id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            logging.error(f"Action with ID {action_id} not found")
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": f"Error: Action with ID {action_id} not found"},
                data.get("public_key", "")
            )
            return

        subject, _description, tool_id, tool_name, parameter_str, is_multi_step, steps_str = row

        # Check if this is a multi-step action
        if is_multi_step:
            logging.info(f"Action {action_id} is multi-step, executing all steps")
            # Execute all steps
            await execute_multi_step_action_internal(cell, transmitter, action_id, subject, steps_str)
            return

        # Single action execution
        logging.info(f"Executing single action {action_id}: {subject}")

        # Parse parameters
        try:
            parameters = json.loads(parameter_str) if parameter_str else {}
        except json.JSONDecodeError:
            parameters = {}

        logging.info(f"Executing action {action_id}: {subject}")
        logging.info(f"  Tool: {tool_name} (ID: {tool_id})")
        logging.info(f"  Parameters: {parameters}")

        # Get registry and execute tool
        registry = await tool_registry.get_registry()

        try:
            mcp_result = await registry.call_tool(tool_name, parameters)
            logging.info(f"Tool execution result: {mcp_result}")

            # Generate natural language response from tool result
            natural_response = await convert_tool_result_to_natural_language(
                tool_name,
                mcp_result,
                subject
            )

            # Store the natural language response and mark as finished in the database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE actions SET response = ?, status = ? WHERE id = ?",
                    (natural_response, 'finished', action_id)
                )
                await db.commit()

            logging.info(f"Action response stored in database and marked as finished")
            logging.info(f"Natural language response: {natural_response}")

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": natural_response},
                data.get("public_key", "")
            )

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logging.error(error_msg)

            # Store the error and mark as failed in the database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE actions SET response = ?, status = ? WHERE id = ?",
                    (f"ERROR: {error_msg}", 'failed', action_id)
                )
                await db.commit()

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": error_msg},
                data.get("public_key", "")
            )

    except Exception as e:
        error_msg = f"Error executing action: {str(e)}"
        logging.error(error_msg)
        import traceback
        logging.error(traceback.format_exc())

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def execute_multi_step_action_internal(cell, transmitter: dict, action_id: int, subject: str, steps_str: str):
    """Internal function to execute all steps in a multi-step action sequentially"""
    try:
        # Parse steps from JSON
        try:
            steps = json.loads(steps_str) if steps_str else []
        except json.JSONDecodeError:
            error_msg = "Failed to parse steps JSON"
            logging.error(error_msg)
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": f"Error: {error_msg}"},
                transmitter.get("data", {}).get("public_key", "")
            )
            return

        if not steps:
            error_msg = "No steps found in multi-step action"
            logging.error(error_msg)
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": f"Error: {error_msg}"},
                transmitter.get("data", {}).get("public_key", "")
            )
            return

        logging.info(f"Executing multi-step action '{subject}' with {len(steps)} steps")

        registry = await tool_registry.get_registry()
        executed_steps = 0
        step_responses = []

        for step in steps:
            step_order = step.get("step_order", 1)
            step_subject = step.get("subject", f"Step {step_order}")
            tool_name = step.get("tool_name", "")
            parameters = step.get("parameters", {})

            logging.info(f"Executing step {step_order}: {step_subject}")

            try:
                # Execute the tool
                mcp_result = await registry.call_tool(tool_name, parameters)

                # Generate natural language response from tool result
                natural_response = await convert_tool_result_to_natural_language(
                    tool_name,
                    mcp_result,
                    step_subject
                )

                step_responses.append({
                    "step_order": step_order,
                    "step_subject": step_subject,
                    "status": "success",
                    "response": natural_response
                })

                logging.info(f"Step {step_order} completed successfully")
                executed_steps += 1

            except Exception as e:
                error_msg = f"Step {step_order} failed: {str(e)}"
                logging.error(error_msg)

                step_responses.append({
                    "step_order": step_order,
                    "step_subject": step_subject,
                    "status": "error",
                    "response": f"ERROR: {error_msg}"
                })

                # Stop on first error
                # Generate natural language summary of partial execution
                loop = asyncio.get_running_loop()
                natural_summary = await loop.run_in_executor(
                    None,
                    generate_multi_step_summary,
                    subject,
                    step_responses
                )

                # Store partial results with natural language summary and mark as failed
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE actions SET response = ?, status = ? WHERE id = ?",
                        (natural_summary, 'failed', action_id)
                    )
                    await db.commit()

                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": natural_summary},
                    transmitter.get("data", {}).get("public_key", "")
                )

                return

        # All steps completed successfully
        # Generate natural language summary of all steps
        loop = asyncio.get_running_loop()
        natural_summary = await loop.run_in_executor(
            None,
            generate_multi_step_summary,
            subject,
            step_responses
        )

        # Mark action as finished with natural language summary
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE actions SET response = ?, status = ? WHERE id = ?",
                (natural_summary, 'finished', action_id)
            )
            await db.commit()

        logging.info(f"Multi-step action '{subject}' completed successfully: {executed_steps} steps executed")
        logging.info(f"Natural language summary: {natural_summary}")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": natural_summary},
            transmitter.get("data", {}).get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error executing multi-step action: {str(e)}"
        logging.error(error_msg)
        import traceback
        logging.error(traceback.format_exc())

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            transmitter.get("data", {}).get("public_key", "")
        )

async def handle_delete_action(cell, transmitter: dict):
    """Handle dismissing an action (soft delete by updating status to 'dismissed')"""
    data = transmitter.get("data", {})
    action_id = data.get("action_id", "")

    if not action_id:
        logging.error("No action_id provided for dismissal")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Action ID is required"},
            data.get("public_key", "")
        )
        return

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # First check if action exists
            async with db.execute(
                "SELECT subject FROM actions WHERE id = ?",
                (action_id,)
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                logging.warning(f"Action with ID {action_id} not found")
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": f"Error: Action with ID {action_id} not found"},
                    data.get("public_key", "")
                )
                return

            subject = row[0]

            # Soft delete: Update status to 'dismissed' instead of deleting
            await db.execute(
                "UPDATE actions SET status = ? WHERE id = ?",
                ('dismissed', action_id)
            )
            await db.commit()

        logging.info(f"Action dismissed: {subject} (ID: {action_id})")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": f"Action '{subject}' dismissed successfully"},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error dismissing action: {str(e)}"
        logging.error(error_msg)

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_cell_message(cell, transmitter: dict):
    """Handle sending a message from one cell to another

    Stores the message in the database and streams it to the recipient cell.
    """
    data = transmitter.get("data", {})
    from_cell_id = transmitter.get("operator", "")
    to_cell_id = data.get("to_cell_id", "")
    message = data.get("message", "")
    logging.info(f"Message Payload: {transmitter}")
    logging.info(f"Message from: {from_cell_id}")

    if not to_cell_id:
        logging.error("No to_cell_id provided for cell_message")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Recipient cell_id is required"},
            data.get("public_key", "")
        )
        return

    if not message:
        logging.error("No message provided for cell_message")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Message is required"},
            data.get("public_key", "")
        )
        return

    try:
        # Store message in database
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO cell_messages (from_cell_id, to_cell_id, message)
                   VALUES (?, ?, ?)""",
                (from_cell_id, to_cell_id, message)
            )
            message_id = cursor.lastrowid
            await db.commit()

        logging.info(f"Cell message stored: {from_cell_id} -> {to_cell_id} (ID: {message_id})")

        # Stream message to recipient cell
        await cell.stream(to_cell_id, {
            "cell_message": {
                "id": message_id,
                "from_cell_id": from_cell_id,
                "message": message
            }
        })

        # Send notification to recipient cell
        await cell.stream(to_cell_id, {
            "notification": {
                "title": f"Message from {from_cell_id}",
                "message": f"{message}",
                "message_id": message_id
            }
        })

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Message sent successfully"},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error sending cell message: {str(e)}"
        logging.error(error_msg)

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_get_messages(cell, transmitter: dict):
    """Handle fetching messages for a cell

    Returns messages where the cell is the recipient.
    Optionally filters by unread only and marks messages as read.
    """
    data = transmitter.get("data", {})
    cell_id = transmitter.get("operator", "")
    unread_only = data.get("unread_only", False)
    mark_as_read = data.get("mark_as_read", True)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            # Build query based on filters (get sent and received messages)
            if unread_only:
                query = """SELECT id, from_cell_id, to_cell_id, message, is_read, timestamp
                           FROM cell_messages
                           WHERE (to_cell_id = ? OR from_cell_id = ?) AND is_read = 0
                           ORDER BY timestamp DESC"""
            else:
                query = """SELECT id, from_cell_id, to_cell_id, message, is_read, timestamp
                           FROM cell_messages
                           WHERE to_cell_id = ? OR from_cell_id = ?
                           ORDER BY timestamp DESC"""

            async with db.execute(query, (cell_id, cell_id)) as cursor:
                rows = await cursor.fetchall()

            messages = []
            message_ids = []
            for row in rows:
                messages.append({
                    "id": row["id"],
                    "from_cell_id": row["from_cell_id"],
                    "to_cell_id": row["to_cell_id"],
                    "message": row["message"],
                    "is_read": bool(row["is_read"]),
                    "timestamp": row["timestamp"]
                })
                if not row["is_read"]:
                    message_ids.append(row["id"])

            # Mark fetched messages as read
            if mark_as_read and message_ids:
                placeholders = ",".join("?" * len(message_ids))
                await db.execute(
                    f"UPDATE cell_messages SET is_read = 1 WHERE id IN ({placeholders})",
                    message_ids
                )
                await db.commit()

        logging.info(f"Fetched {len(messages)} messages for cell {cell_id}")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"messages": messages}},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error fetching messages: {str(e)}"
        logging.error(error_msg)

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_edit_action(cell, transmitter: dict):
    """Handle editing an action using natural language prompts

    Users can:
    - Ask questions about the action (get info)
    - Request changes to tool, parameters, subject, etc.
    """
    data = transmitter.get("data", {})
    action_id = data.get("action_id", "")
    prompt = data.get("prompt", "")
    space_id = data.get("space_id", None)
    cell_id = transmitter.get("operator", "default_user")

    if not action_id:
        logging.error("No action_id provided for edit")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Action ID is required"},
            data.get("public_key", "")
        )
        return

    if not prompt:
        logging.error("No prompt provided for edit action")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Prompt is required"},
            data.get("public_key", "")
        )
        return

    try:
        # Fetch the action from database
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                """SELECT id, subject, description, original_data, tool_id, tool_name, parameter,
                          response, status, is_multi_step, steps, space_id, timestamp
                   FROM actions WHERE id = ?""",
                (action_id,)
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            logging.error(f"Action with ID {action_id} not found")
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": f"Error: Action with ID {action_id} not found"},
                data.get("public_key", "")
            )
            return

        # Build action dict
        action_data = {
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
            "steps": row[10],
            "space_id": row[11],
            "timestamp": row[12]
        }

        logging.info(f"Editing action {action_id}: {action_data['subject']}")
        logging.info(f"User prompt: {prompt}")

        # Get available tools for context
        registry = await tool_registry.get_registry()
        available_tools = await registry.get_all_tools()

        # Build tool list for LLM
        tool_info_list = []
        for tool in available_tools:
            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})

            params_desc = []
            for param_name, param_def in properties.items():
                params_desc.append(f"{param_name} ({param_def.get('type', 'string')}): {param_def.get('description', '')}")

            tool_info = f"""Tool ID: {tool.get('server', 'unknown')}
Tool Name: {tool['name']}
Description: {tool.get('description', 'No description')}
Parameters: {', '.join(params_desc) if params_desc else 'none'}"""
            tool_info_list.append(tool_info)

        # Format current action info for LLM
        if action_data['is_multi_step']:
            steps_info = action_data['steps'] or "[]"
            action_info = f"""Action ID: {action_data['id']}
Subject: {action_data['subject']}
Description: {action_data['description']}
Original Request: {action_data['original_data']}
Status: {action_data['status']}
Type: Multi-step action
Steps: {steps_info}
Created: {action_data['timestamp']}"""
        else:
            action_info = f"""Action ID: {action_data['id']}
Subject: {action_data['subject']}
Description: {action_data['description']}
Original Request: {action_data['original_data']}
Tool ID: {action_data['tool_id']}
Tool Name: {action_data['tool_name']}
Parameters: {action_data['parameter']}
Status: {action_data['status']}
Response: {action_data['response'] or 'Not executed yet'}
Created: {action_data['timestamp']}"""

        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create LLM prompt
        edit_prompt = f"""You are an assistant that helps users view and modify actions in a task management system.

CURRENT ACTION:
{action_info}

AVAILABLE TOOLS:
{chr(10).join(tool_info_list)}

USER REQUEST:
{prompt}
Sent by: {cell_id} at {current_timestamp}

Analyze the user's request and determine if they want to:
1. GET INFORMATION - They're asking questions about the action (what tool, what parameters, status, etc.)
2. UPDATE ACTION - They want to change something (different tool, different parameters, change subject, etc.)

IMPORTANT RULES:
- Only allow updates to actions with status 'pending'. If status is 'finished', 'failed', or 'dismissed', inform the user they cannot edit it.
- When updating tool or parameters, validate that the tool exists in AVAILABLE TOOLS.
- For multi-step actions: ONLY modify the specific step(s) the user mentions. DO NOT touch other steps.

Respond with JSON:

For INFORMATION requests:
{{
  "action_type": "info",
  "response": "Your natural language answer about the action"
}}

For UPDATE requests (single-step action):
{{
  "action_type": "update",
  "updates": {{
    "subject": "new subject if changed, or null",
    "description": "new description if changed, or null",
    "tool_id": "new tool_id if changed, or null",
    "tool_name": "new tool_name if changed, or null",
    "parameters": {{"param": "value"}} or null if not changed
  }},
  "response": "Confirmation message describing what was changed"
}}

For UPDATE requests (multi-step action) - ONLY include steps that need changes:
{{
  "action_type": "update_step",
  "step_updates": [
    {{
      "step_order": 2,
      "subject": "new subject or null to keep current",
      "context": "new context or null to keep current",
      "tool_id": "new tool_id or null to keep current",
      "tool_name": "new tool_name or null to keep current",
      "parameters": {{"param": "value"}} or null to keep current
    }}
  ],
  "response": "Confirmation message describing what was changed"
}}

CRITICAL FOR MULTI-STEP: Only include in step_updates the steps the user wants to modify.
- If user says "change step 2 to use tool X", only include step 2 in step_updates.
- If user says "update the amount in step 1", only include step 1 in step_updates.
- NEVER include steps the user didn't mention - they will remain unchanged.

For DENIED requests (action not editable):
{{
  "action_type": "denied",
  "response": "Explanation of why the action cannot be edited"
}}

JSON:"""

        loop = asyncio.get_running_loop()

        def get_edit_response():
            messages = [
                {"role": "system", "content": "You are an assistant that helps users view and modify actions. Respond only with valid JSON."},
                {"role": "user", "content": edit_prompt}
            ]

            response = create_chat_completion(
                messages=messages,
                max_tokens=800,
                temperature=0.3
            )
            content = response['choices'][0]['message']['content'].strip()
            return content

        logging.info("Using LLM to process edit action request...")
        result_json = await loop.run_in_executor(None, get_edit_response)

        # Clean up JSON response
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

        edit_result = json.loads(result_json)
        action_type = edit_result.get("action_type", "info")
        response_text = edit_result.get("response", "Request processed.")

        if action_type == "info" or action_type == "denied":
            # Just return the information/denial response
            logging.info(f"Edit action info/denied response: {response_text}")

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": response_text},
                data.get("public_key", "")
            )

        elif action_type == "update":
            # Update single-step action
            updates = edit_result.get("updates", {})

            # Build dynamic UPDATE query
            update_fields = []
            update_values = []

            if updates.get("subject") is not None:
                update_fields.append("subject = ?")
                update_values.append(updates["subject"])

            if updates.get("description") is not None:
                update_fields.append("description = ?")
                update_values.append(updates["description"])

            if updates.get("tool_id") is not None:
                update_fields.append("tool_id = ?")
                update_values.append(updates["tool_id"])

            if updates.get("tool_name") is not None:
                update_fields.append("tool_name = ?")
                update_values.append(updates["tool_name"])

            if updates.get("parameters") is not None:
                update_fields.append("parameter = ?")
                update_values.append(json.dumps(updates["parameters"]))

            if update_fields:
                update_values.append(action_id)
                query = f"UPDATE actions SET {', '.join(update_fields)} WHERE id = ?"

                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(query, tuple(update_values))
                    await db.commit()

                logging.info(f"Action {action_id} updated: {update_fields}")

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": response_text},
                data.get("public_key", "")
            )

        elif action_type == "update_step":
            # Update specific steps in multi-step action (merge changes)
            step_updates = edit_result.get("step_updates", [])

            # Parse existing steps
            try:
                existing_steps = json.loads(action_data['steps']) if action_data['steps'] else []
            except json.JSONDecodeError:
                existing_steps = []

            # Apply updates to specific steps
            for update in step_updates:
                target_order = update.get("step_order")
                if target_order is None:
                    continue

                # Find the step to update
                for step in existing_steps:
                    if step.get("step_order") == target_order:
                        # Only update fields that are not null
                        if update.get("subject") is not None:
                            step["subject"] = update["subject"]
                        if update.get("context") is not None:
                            step["context"] = update["context"]
                        if update.get("tool_id") is not None:
                            step["tool_id"] = update["tool_id"]
                        if update.get("tool_name") is not None:
                            step["tool_name"] = update["tool_name"]
                        if update.get("parameters") is not None:
                            step["parameters"] = update["parameters"]
                        logging.info(f"Updated step {target_order} in action {action_id}")
                        break

            # Save merged steps back to database
            steps_json = json.dumps(existing_steps)

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE actions SET steps = ? WHERE id = ?",
                    (steps_json, action_id)
                )
                await db.commit()

            logging.info(f"Action {action_id} steps updated: {len(step_updates)} step(s) modified")

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": response_text},
                data.get("public_key", "")
            )

        # Store in conversation history
        await store_message(cell_id, "user", f"[Edit Action {action_id}] {prompt}", space_id=space_id)
        await store_message(cell_id, "assistant", response_text, space_id=space_id)

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM response: {str(e)}"
        logging.error(error_msg)

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error editing action: {str(e)}"
        logging.error(error_msg)
        import traceback
        logging.error(traceback.format_exc())

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_add_to_queue(cell, transmitter: dict):
    """Handle adding a text request to the queue folder"""
    data = transmitter.get("data", {})
    prompt = data.get("prompt", "")
    space_id = data.get("space_id", None)
    cell_id = transmitter.get("operator", "default_user")

    if not prompt:
        logging.error("No prompt provided for queue")
        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Error: Prompt is required"},
            data.get("public_key", "")
        )
        return

    try:
        import uuid

        # Create queue directory if it doesn't exist
        queue_dir = "./queue"
        os.makedirs(queue_dir, exist_ok=True)

        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"request_{timestamp}_{unique_id}.json"
        file_path = os.path.join(queue_dir, filename)

        # Build queue request data
        queue_data = {
            "prompt": prompt,
            "cell_id": cell_id
        }
        if space_id:
            queue_data["space_id"] = space_id

        # Write request data to JSON file
        with open(file_path, 'w') as f:
            json.dump(queue_data, f)

        logging.info(f"Request added to queue: {filename}")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": "Request added to queue. The action will be processed and appear in your actions list."},
            data.get("public_key", "")
        )

    except Exception as e:
        error_msg = f"Error adding request to queue: {str(e)}"
        logging.error(error_msg)

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

async def handle_download_log(cell, transmitter: dict):
    """Handle downloading last 100 lines from agent log file"""
    data = transmitter.get("data", {})
    logging.info("Fetching last 100 lines from server.log...")

    try:
        # Read the last 100 lines from the log file
        with open("server.log", "r") as f:
            lines = f.readlines()
            last_100_lines = lines[-100:] if len(lines) > 100 else lines
            agent_log = ''.join(last_100_lines)

        logging.info(f"Agent log fetched successfully ({len(last_100_lines)} lines)")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": {"log": agent_log}},
            data.get("public_key", "")
        )

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
    space_id = data.get("space_id", None)

    logging.info(f"DEBUG - Data keys: {list(data.keys())}")
    logging.info(f"DEBUG - Has 'file' key: {'file' in data}")

    logging.info(f"[User]: {prompt}")
    cell_id = transmitter.get("operator", "default_user")

    # Fetch space context if space_id is provided
    space_context = None
    if space_id:
        space_context = await fetch_space_by_id(space_id)
        if space_context:
            logging.info(f"Using space context: {space_context.get('name')}")

    try:
        answer = await get_model_answer(cell_id, prompt, file, file_content, space_context)
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
    user_prompt = data.get("prompt", "")
    execution_mode = data.get("execution_mode", "")
    space_id = data.get("space_id", None)
    cell_id = transmitter.get("operator", "default_user")

    # Use cell_id as space_id if no space_id provided (assign action to user)
    if not space_id:
        space_id = cell_id

    logging.info(f"Tool call requested")
    logging.info(f"User prompt: {user_prompt}")

    # Fetch space context if space_id is provided (and it's not just the cell_id)
    space_context = None
    if space_id and space_id != cell_id:
        space_context = await fetch_space_by_id(space_id)
        if space_context:
            logging.info(f"Using space context for action: {space_context.get('name')}")

    try:
        if not user_prompt:
            error_msg = "'prompt' is required for tool execution"
            logging.error(error_msg)
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": error_msg},
                data.get("public_key", "")
            )
            return

        history = await fetch_latest_messages(cell_id, limit=5, space_id=space_id)
        logging.info(f"Retrieved {len(history)} messages from conversation history")

        registry = await tool_registry.get_registry()
        available_tools = await registry.get_all_tools()

        if not available_tools:
            error_msg = "No tools available for execution"
            logging.error(error_msg)
            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": error_msg},
                data.get("public_key", "")
            )
            return

        logging.info(f"AI-assisted mode: Using all {len(available_tools)} available tools")

        # Build tool list for LLM (same as queue processor)
        tool_info_list = []
        for tool in available_tools:
            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})

            params_desc = []
            for param_name, param_def in properties.items():
                params_desc.append(f"{param_name} ({param_def.get('type', 'string')}): {param_def.get('description', '')}")

            tool_info = f"""Tool ID: {tool.get('server', 'unknown')}
Tool Name: {tool['name']}
Description: {tool.get('description', 'No description')}
Parameters: {', '.join(params_desc) if params_desc else 'none'}"""
            tool_info_list.append(tool_info)

        # Build space context string for the prompt
        space_context_str = ""
        if space_context:
            space_parts = []
            if space_context.get("name"):
                space_parts.append(f"Space: {space_context.get('name')}")
            if space_context.get("responsibility"):
                space_parts.append(f"Responsibility: {space_context.get('responsibility')}")
            if space_context.get("instructions"):
                space_parts.append(f"Instructions: {space_context.get('instructions')}")
            if space_context.get("knowledge"):
                space_parts.append(f"Knowledge: {space_context.get('knowledge')}")
            if space_parts:
                space_context_str = f"\n\nSPACE CONTEXT:\n{chr(10).join(space_parts)}\n"

        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        function_call_prompt = f"""User request: "{user_prompt}"
Sent by: {cell_id} at {current_timestamp}
{space_context_str}
AVAILABLE TOOLS:
{chr(10).join(tool_info_list)}

Analyze the request and determine if it requires single or multiple tool calls.

CRITICAL: If NONE of the available tools can fulfill the user's request, you MUST respond with "no_tool_available" instead of forcing an inappropriate tool.

IMPORTANT: Think critically about what prerequisite steps, safety checks, or validations are needed BEFORE executing the main action, even if the request doesn't explicitly mention them.

Examples of implicit prerequisites:
- Money transfers → Check balance first
- Deleting data → Backup or verification first
- Sending messages → Validate recipient exists
- Booking reservations → Check availability first
- Updating records → Fetch current state first

CRITICAL THINKING REQUIRED:
- Does this action need validation before execution? (e.g., check balance before transfer)
- Does this action modify important data? (should we check current state first?)
- Does this action have dependencies? (e.g., need to verify something exists first)
- Could this action fail if preconditions aren't met?
- Are the available tools actually capable of fulfilling this request?

Use proper JSON types - numbers as numbers (not strings), booleans as true/false, strings as quoted text.

For SINGLE tool requests, respond with:
{{"is_multi_tool": false, "tool_name": "selected_tool_name", "parameters": {{"string_param": "text", "number_param": 123}}}}

For MULTI-TOOL requests (including prerequisite checks), respond with:
{{"is_multi_tool": true, "tools": [
  {{"step_order": 1, "tool_name": "prerequisite_tool", "parameters": {{"param": "value"}}}},
  {{"step_order": 2, "tool_name": "main_action_tool", "parameters": {{"param": "value"}}}}
]}}

For NO SUITABLE TOOL available, respond with:
{{"no_tool_available": true, "reason": "Brief explanation of what capability is missing"}}

If no parameters are needed, use an empty object: {{"parameters": {{}}}}

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
                max_tokens=500,
                temperature=0.2
            )
            content = response['choices'][0]['message']['content'].strip()
            return content

        logging.info("Using LLM to select tool(s) and extract parameters...")
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

        # Check if no suitable tool is available
        if function_call.get("no_tool_available", False):
            error_msg = "No tool available to perform this action. Please install or create an appropriate tool."
            logging.warning(f"No suitable tool found for request: {user_prompt}")

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": error_msg},
                data.get("public_key", "")
            )

            # Store in conversation history
            await store_message(cell_id, "user", user_prompt, space_id=space_id)
            await store_message(cell_id, "assistant", error_msg, space_id=space_id)
            return

        is_multi_tool = function_call.get("is_multi_tool", False)

        # Check if multi-tool execution
        if is_multi_tool:
            tools_to_execute = function_call.get("tools", [])
            logging.info(f"LLM selected multi-tool execution with {len(tools_to_execute)} tools")

            # Validate all tools are valid
            for tool_step in tools_to_execute:
                tool_name = tool_step.get("tool_name")
                if tool_name not in [t["name"] for t in available_tools]:
                    # Treat selecting non-existent tool as "no tool available"
                    error_msg = "No tool available to perform this action. Please install or create an appropriate tool."
                    logging.warning(f"LLM attempted to select non-existent tool in multi-step: {tool_name}")
                    await send_cell_response(
                        cell,
                        transmitter.get("transmitter_id"),
                        {"json": error_msg},
                        data.get("public_key", "")
                    )

                    # Store in conversation history
                    await store_message(cell_id, "user", user_prompt, space_id=space_id)
                    await store_message(cell_id, "assistant", error_msg, space_id=space_id)
                    return

            # Prepare steps for storage (without execution)
            steps_for_storage = []
            for tool_step in tools_to_execute:
                step_order = tool_step.get("step_order", 1)
                tool_name = tool_step.get("tool_name")
                tool_id = next((t.get('server', 'unknown') for t in available_tools if t["name"] == tool_name), 'unknown')
                parameters = tool_step.get("parameters", {})

                steps_for_storage.append({
                    "step_order": step_order,
                    "subject": f"Step {step_order}: {tool_name}",
                    "context": f"Execute {tool_name}",
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "parameters": parameters
                })

            # Store in actions database as multi-step action (not executed yet)
            steps_json = json.dumps(steps_for_storage)

            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "INSERT INTO actions (subject, description, original_data, status, is_multi_step, steps, space_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_prompt[:100], f"Multi-step action with {len(steps_for_storage)} steps", user_prompt, 'pending', True, steps_json, space_id)
                )
                action_id = cursor.lastrowid
                await db.commit()

            logging.info(f"Created multi-step action entry with ID: {action_id}")

            # Fetch the created action to get full details
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT id, subject, description, original_data, tool_id, tool_name, parameter, response, status, is_multi_step, steps, space_id, timestamp FROM actions WHERE id = ?",
                    (action_id,)
                ) as cursor:
                    row = await cursor.fetchone()

            # Build action dict (same structure as fetch_all_actions)
            action_details = {
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
                "space_id": row[11],
                "timestamp": row[12],
                "steps": json.loads(row[10]) if row[10] else []
            }

            # Generate natural language description of what the action will do
            steps_description = []
            for step in steps_for_storage:
                tool_name = step['tool_name']
                params = step['parameters']
                if params:
                    param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                    steps_description.append(f"{tool_name}({param_str})")
                else:
                    steps_description.append(f"{tool_name}()")

            action_description = f"This multi-step action will execute {len(steps_for_storage)} steps in sequence: {' → '.join(steps_description)}."

            # Response includes both action details and description
            response_data = {
                "action": action_details,
                "description": action_description
            }

            # Check if execution mode is enabled
            if execution_mode == "enabled":
                logging.info(f"Execution mode enabled - executing multi-step action {action_id} immediately")
                # Execute the multi-step action immediately
                await execute_multi_step_action_internal(cell, transmitter, action_id, user_prompt[:100], steps_json)
                return

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": response_data},
                data.get("public_key", "")
            )

            # Store in conversation history
            await store_message(cell_id, "user", user_prompt, space_id=space_id)
            await store_message(cell_id, "assistant", action_description, space_id=space_id)

        else:
            # Single tool storage (no execution)
            tool_name = function_call.get("tool_name")
            parameters = function_call.get("parameters", {})

            logging.info(f"LLM selected single tool: {tool_name} with parameters: {parameters}")

            if tool_name not in [t["name"] for t in available_tools]:
                # Treat selecting non-existent tool as "no tool available"
                error_msg = "No tool available to perform this action. Please install or create an appropriate tool."
                logging.warning(f"LLM attempted to select non-existent tool: {tool_name}")
                await send_cell_response(
                    cell,
                    transmitter.get("transmitter_id"),
                    {"json": error_msg},
                    data.get("public_key", "")
                )

                # Store in conversation history
                await store_message(cell_id, "user", user_prompt, space_id=space_id)
                await store_message(cell_id, "assistant", error_msg, space_id=space_id)
                return

            # Validate parameters
            tool_info = next((t for t in available_tools if t["name"] == tool_name), None)
            if tool_info:
                input_schema = tool_info.get("inputSchema", {})
                is_valid, error_msg = validate_tool_parameters(parameters, input_schema)

                if not is_valid:
                    error_response = f"Parameter validation failed: {error_msg}"
                    logging.error(error_response)

                    # Create a failed action entry for parameter validation failure
                    tool_id_for_db = next((t.get('server', 'unknown') for t in available_tools if t["name"] == tool_name), 'unknown')
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute(
                            "INSERT INTO actions (subject, description, original_data, tool_id, tool_name, parameter, status, response, is_multi_step, steps, space_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (user_prompt[:100], f"Failed: {tool_name}", user_prompt, tool_id_for_db, tool_name, json.dumps(parameters), 'failed', f"ERROR: {error_response}", False, None, space_id)
                        )
                        await db.commit()

                    await send_cell_response(
                        cell,
                        transmitter.get("transmitter_id"),
                        {"json": error_response},
                        data.get("public_key", "")
                    )

                    # Store in conversation history
                    await store_message(cell_id, "user", user_prompt, space_id=space_id)
                    await store_message(cell_id, "assistant", error_response, space_id=space_id)
                    return

            # Store in actions database as single-step action (not executed yet)
            tool_id_for_db = next((t.get('server', 'unknown') for t in available_tools if t["name"] == tool_name), 'unknown')

            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "INSERT INTO actions (subject, description, original_data, tool_id, tool_name, parameter, status, is_multi_step, steps, space_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_prompt[:100], f"Single tool call: {tool_name}", user_prompt, tool_id_for_db, tool_name, json.dumps(parameters), 'pending', False, None, space_id)
                )
                action_id = cursor.lastrowid
                await db.commit()

            logging.info(f"Created single-step action entry with ID: {action_id}")

            # Fetch the created action to get full details
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT id, subject, description, original_data, tool_id, tool_name, parameter, response, status, is_multi_step, steps, space_id, timestamp FROM actions WHERE id = ?",
                    (action_id,)
                ) as cursor:
                    row = await cursor.fetchone()

            # Build action dict (same structure as fetch_all_actions)
            action_details = {
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
                "space_id": row[11],
                "timestamp": row[12],
                "steps": None
            }

            # Generate natural language description of what the action will do
            if parameters:
                param_str = ", ".join([f"{k}={v}" for k, v in parameters.items()])
                action_description = f"This action will execute {tool_name}({param_str})."
            else:
                action_description = f"This action will execute {tool_name}()."

            # Check if execution mode is enabled
            if execution_mode == "enabled":
                logging.info(f"Execution mode enabled - executing single-tool action {action_id} immediately")

                # Get registry and execute tool
                registry = await tool_registry.get_registry()

                try:
                    mcp_result = await registry.call_tool(tool_name, parameters)
                    logging.info(f"Tool execution result: {mcp_result}")

                    # Generate natural language response from tool result
                    natural_response = await convert_tool_result_to_natural_language(
                        tool_name,
                        mcp_result,
                        user_prompt[:100]
                    )

                    # Store the natural language response and mark as finished in the database
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute(
                            "UPDATE actions SET response = ?, status = ? WHERE id = ?",
                            (natural_response, 'finished', action_id)
                        )
                        await db.commit()

                    logging.info(f"Action response stored in database and marked as finished")
                    logging.info(f"Natural language response: {natural_response}")

                    await send_cell_response(
                        cell,
                        transmitter.get("transmitter_id"),
                        {"json": natural_response},
                        data.get("public_key", "")
                    )

                    # Store in conversation history
                    await store_message(cell_id, "user", user_prompt, space_id=space_id, message_type="action_result")
                    await store_message(cell_id, "assistant", natural_response, space_id=space_id, message_type="action_result")
                    return

                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    logging.error(error_msg)

                    # Store the error and mark as failed in the database
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute(
                            "UPDATE actions SET response = ?, status = ? WHERE id = ?",
                            (f"ERROR: {error_msg}", 'failed', action_id)
                        )
                        await db.commit()

                    await send_cell_response(
                        cell,
                        transmitter.get("transmitter_id"),
                        {"json": error_msg},
                        data.get("public_key", "")
                    )

                    # Store in conversation history
                    await store_message(cell_id, "user", user_prompt, space_id=space_id)
                    await store_message(cell_id, "assistant", error_msg, space_id=space_id)
                    return

            # Response includes both action details and description
            response_data = {
                "action": action_details,
                "description": action_description
            }

            await send_cell_response(
                cell,
                transmitter.get("transmitter_id"),
                {"json": response_data},
                data.get("public_key", "")
            )

            # Store in conversation history
            await store_message(cell_id, "user", user_prompt, space_id=space_id)
            await store_message(cell_id, "assistant", action_description, space_id=space_id)

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM response: {str(e)}"
        logging.error(error_msg)

        # Create a failed action entry
        try:
            await store_action_entry(
                subject=user_prompt[:100],
                context=error_msg,
                original_data=user_prompt,
                tool_id=None,
                tool_name=None,
                parameter=None,
                is_multi_step=False,
                steps=None
            )
            # Update the stored entry to failed status with error message
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE actions SET status = ?, response = ? WHERE original_data = ? ORDER BY id DESC LIMIT 1",
                    ('failed', f"ERROR: {error_msg}", user_prompt)
                )
                await db.commit()
        except Exception as store_error:
            logging.error(f"Failed to store error action: {store_error}")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

        # Store in conversation history
        await store_message(cell_id, "user", user_prompt, space_id=space_id)
        await store_message(cell_id, "assistant", error_msg, space_id=space_id)

    except Exception as e:
        error_msg = f"Error handling tool call: {str(e)}"
        logging.error(error_msg)
        import traceback
        logging.error(traceback.format_exc())

        # Create a failed action entry
        try:
            await store_action_entry(
                subject=user_prompt[:100],
                context=error_msg,
                original_data=user_prompt,
                tool_id=None,
                tool_name=None,
                parameter=None,
                is_multi_step=False,
                steps=None,
                space_id=space_id
            )
            # Update the stored entry to failed status with error message
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE actions SET status = ?, response = ? WHERE original_data = ? ORDER BY id DESC LIMIT 1",
                    ('failed', f"ERROR: {error_msg}", user_prompt)
                )
                await db.commit()
        except Exception as store_error:
            logging.error(f"Failed to store error action: {store_error}")

        await send_cell_response(
            cell,
            transmitter.get("transmitter_id"),
            {"json": error_msg},
            data.get("public_key", "")
        )

        # Store in conversation history
        await store_message(cell_id, "user", user_prompt, space_id=space_id)
        await store_message(cell_id, "assistant", error_msg, space_id=space_id)

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

        logging.info(f"✅ Tool '{tool_id}' successfully deleted. Files removed: {', '.join(files_deleted)}")

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
    cell_id = transmitter.get("operator", "default_user")

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
    cell_id = transmitter.get("operator", "default_user")

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
            "get_actions": lambda: handle_get_actions(cell, transmitter),
            "get_spaces": lambda: handle_get_spaces(cell, transmitter),
            "create_space": lambda: handle_create_space(cell, transmitter),
            "update_space": lambda: handle_update_space(cell, transmitter),
            "delete_space": lambda: handle_delete_space(cell, transmitter),
            "execute_action": lambda: handle_execute_action(cell, transmitter),
            "delete_action": lambda: handle_delete_action(cell, transmitter),
            "edit_action": lambda: handle_edit_action(cell, transmitter),
            "cell_message": lambda: handle_cell_message(cell, transmitter),
            "get_messages": lambda: handle_get_messages(cell, transmitter),
            "add_to_queue": lambda: handle_add_to_queue(cell, transmitter),
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

        queue_task = asyncio.create_task(queue_processor_loop(registry, cell))
        logging.info("Queue processor started in background")

        if not cell.host.startswith("neuronumagent"):
            await cell.stream(cell.host, {"json": "ping"})

        await process_cell_messages(cell)

        scheduler_task.cancel()
        queue_task.cancel()
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
