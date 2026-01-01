"""Task scheduler and executor for automated task execution."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Callable

import tool_registry


async def execute_scheduled_task(cell, task_data: dict, create_chat_completion: Callable):
    """Execute single scheduled task by calling its tool function with resource"""
    task_name = task_data.get("name", "Unknown")
    tool_id = task_data.get("tool_id")
    function_name = task_data.get("function_name")
    resources = task_data.get("resources", [])

    logging.info(f"Executing scheduled task: {task_name}")
    logging.info(f"   Tool: {tool_id}, Function: {function_name}")
    logging.info(f"   Resources: {len(resources)} resource(s)")

    if not tool_id:
        logging.error(f"Error: Task '{task_name}' has no tool_id configured. Skipping execution.")
        return

    if not function_name:
        logging.error(f"Error: Task '{task_name}' has no function_name configured. Skipping execution.")
        return

    try:
        registry = await tool_registry.get_registry()
        available_tools = await registry.get_all_tools()

        matching_tools = [
            tool for tool in available_tools
            if tool.get("server") == tool_id or (tool_id and tool_id in tool.get("name", ""))
        ]

        if not matching_tools:
            logging.error(f"Error: No tools found for tool_id '{tool_id}'")
            return

        target_tool = None
        for tool in matching_tools:
            if tool.get("name") == function_name:
                target_tool = tool
                break

        if not target_tool:
            logging.error(f"Error: Function '{function_name}' not found in tool '{tool_id}'")
            return

        # Process resources
        resource_data = []
        for idx, resource in enumerate(resources):
            prompt_text = resource.get("prompt", "")
            resource_tool_id = resource.get("tool_id")
            resource_function_name = resource.get("function_name")

            logging.info(f"Processing resource {idx + 1}/{len(resources)}")

            # If tool_id and function_name are provided, call the tool with the prompt
            if resource_tool_id and resource_function_name:
                logging.info(f"   Calling tool: {resource_tool_id}/{resource_function_name} with prompt")

                # Find the resource tool
                resource_tools = [
                    t for t in available_tools
                    if t.get("server") == resource_tool_id or (resource_tool_id and resource_tool_id in t.get("name", ""))
                ]

                resource_target_tool = None
                for t in resource_tools:
                    if t.get("name") == resource_function_name:
                        resource_target_tool = t
                        break

                if resource_target_tool:
                    # LLM extracts parameters from prompt
                    resource_params = {}
                    resource_input_schema = resource_target_tool.get("inputSchema", {})
                    resource_properties = resource_input_schema.get("properties", {})

                    if resource_properties:
                        param_info = []
                        for param_name, param_def in resource_properties.items():
                            description = param_def.get("description", "")
                            param_type = param_def.get("type", "string")
                            param_info.append(f"  - {param_name} ({param_type}): {description}")

                        extraction_prompt = f"""Extract parameters from this instruction: "{prompt_text}"

Tool: {resource_function_name}
Required parameters:
{chr(10).join(param_info)}

Respond ONLY with valid JSON using these exact parameter names."""

                        logging.info("   Extracting parameters from prompt using LLM...")

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

                        try:
                            params_json_str = await loop.run_in_executor(None, extract_params)
                            logging.info(f"   LLM response: {params_json_str[:200]}...")

                            # Strip common prefixes and markdown
                            params_json_str = params_json_str.replace("```json", "").replace("```", "").strip()
                            # Remove "JSON:" prefix if present
                            if params_json_str.startswith("JSON:"):
                                params_json_str = params_json_str[5:].strip()

                            if not params_json_str:
                                logging.warning("   LLM returned empty response, using empty parameters")
                                resource_params = {}
                            elif params_json_str.startswith('{'):
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

                                resource_params = json.loads(params_json_str)
                                logging.info(f"   Extracted parameters: {resource_params}")
                            else:
                                logging.warning(f"   LLM response doesn't start with '{{': {params_json_str[:100]}")
                                resource_params = {}
                        except Exception as e:
                            logging.error(f"   Error extracting parameters: {str(e)}")
                            resource_params = {}

                    try:
                        tool_result = await registry.call_tool(resource_function_name, resource_params)
                        result_content = tool_result.get("content", [])

                        # Extract text from tool result
                        result_text = ""
                        for content_item in result_content:
                            if content_item.get("type") == "text":
                                result_text += content_item.get("text", "")

                        # Add both prompt and tool result to resource data
                        resource_data.append(f"{prompt_text}\n\nData from {resource_function_name}:\n{result_text}")
                        logging.info(f"   Tool result added: {result_text[:100]}...")
                    except Exception as e:
                        logging.error(f"   Error calling resource tool: {str(e)}")
                        resource_data.append(f"{prompt_text}\n\nError fetching data from {resource_function_name}: {str(e)}")
                else:
                    logging.warning(f"   Tool {resource_function_name} not found, using prompt only")
                    resource_data.append(prompt_text)
            else:
                # No tool specified, just use the prompt
                resource_data.append(prompt_text)
                logging.info(f"   Added prompt data: {prompt_text[:100]}...")

        # Combine all resource data
        combined_input = "\n\n---\n\n".join(resource_data)
        logging.info(f"Combined {len(resource_data)} resources into input data")

        # Extract parameters from combined input for main task
        parameters = {}
        if combined_input:
            input_schema = target_tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})

            if properties:
                param_info = []
                for param_name, param_def in properties.items():
                    description = param_def.get("description", "")
                    param_type = param_def.get("type", "string")
                    param_info.append(f"  - {param_name} ({param_type}): {description}")

                extraction_prompt = f"""Extract parameters from this instruction: "{combined_input}"

Tool: {function_name}
Required parameters:
{chr(10).join(param_info)}

Respond ONLY with valid JSON using these exact parameter names."""

                logging.info("Extracting parameters from input_data using LLM...")

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
                logging.info(f"LLM response: {params_json_str[:200]}...")

                # Strip common prefixes and markdown
                params_json_str = params_json_str.replace("```json", "").replace("```", "").strip()
                # Remove "JSON:" prefix if present
                if params_json_str.startswith("JSON:"):
                    params_json_str = params_json_str[5:].strip()

                if not params_json_str:
                    logging.warning("LLM returned empty response, using empty parameters")
                    parameters = {}
                elif params_json_str.startswith('{'):
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

                    try:
                        parameters = json.loads(params_json_str)
                        logging.info(f"Extracted parameters: {parameters}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse JSON: {params_json_str}")
                        logging.error(f"JSON error: {str(e)}")
                        parameters = {}
                else:
                    logging.warning(f"LLM response doesn't start with '{{': {params_json_str[:100]}")
                    parameters = {}

        logging.info(f"Calling tool '{function_name}' with parameters: {parameters}")

        try:
            mcp_result = await registry.call_tool(function_name, parameters)
            logging.info(f"Task '{task_name}' completed successfully")
            logging.info(f"Result: {mcp_result}")

        except Exception as e:
            logging.error(f"Error: Task '{task_name}' execution failed: {str(e)}")

    except Exception as e:
        logging.error(f"Error executing scheduled task '{task_name}': {e}")
        import traceback
        logging.error(traceback.format_exc())


def parse_schedule(schedule: str) -> dict:
    """Parse schedule string into days and timestamps"""
    if '@' in schedule:
        parts = schedule.split('@')
        days_part = parts[0].strip()
        times_part = parts[1].strip() if len(parts) > 1 else ""

        days = [day.strip().lower() for day in days_part.split(',') if day.strip()]

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
    """Determine if task should run based on schedule"""
    if schedule_info['type'] == 'interval':
        interval = schedule_info['interval_seconds']
        time_since_last = current_timestamp - last_run_timestamp
        return time_since_last >= interval

    elif schedule_info['type'] == 'dynamic':
        days = schedule_info['days']
        timestamps = schedule_info['timestamps']

        if not days or not timestamps:
            return False

        current_dt = datetime.fromtimestamp(current_timestamp)
        day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        current_day = day_names[current_dt.weekday()]

        if current_day not in days:
            return False

        # Check if current timestamp is within 60 seconds of any scheduled timestamp
        for scheduled_ts in timestamps:
            time_diff = abs(current_timestamp - scheduled_ts)
            if time_diff < 60:
                if last_run_timestamp < scheduled_ts:
                    return True

        return False

    return False


async def load_tasks_from_directory(tasks_dir: str = "tasks"):
    """Load all task definitions from JSON files in tasks directory"""
    tasks = []

    if not os.path.exists(tasks_dir):
        logging.warning(f"Tasks directory '{tasks_dir}' does not exist")
        return tasks

    for filename in os.listdir(tasks_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(tasks_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    task_data = json.load(f)
                    if task_data.get("status") == "active":
                        tasks.append(task_data)
            except Exception as e:
                logging.error(f"Error loading task file '{filename}': {e}")

    logging.info(f"Loaded {len(tasks)} active tasks from '{tasks_dir}'")
    return tasks


async def task_scheduler_loop(cell, create_chat_completion: Callable, check_interval: int = 30):
    """Main scheduler loop that checks and executes tasks"""
    logging.info("Task scheduler started")

    task_last_run = {}  # Track last run timestamp for each task

    while True:
        try:
            current_timestamp = int(time.time())
            tasks = await load_tasks_from_directory()

            for task in tasks:
                task_id = task.get("task_id")
                schedule_str = task.get("schedule", "")

                if not schedule_str:
                    continue

                schedule_info = parse_schedule(schedule_str)
                if not schedule_info:
                    continue

                last_run = task_last_run.get(task_id, 0)

                if should_task_run(schedule_info, last_run, current_timestamp):
                    logging.info(f"Triggering scheduled task: {task.get('name')}")
                    logging.info(f"   Schedule: {schedule_str}")

                    # Execute task
                    await execute_scheduled_task(cell, task, create_chat_completion)

                    # Update last run time
                    task_last_run[task_id] = current_timestamp

        except Exception as e:
            logging.error(f"Error in task scheduler loop: {e}")
            import traceback
            logging.error(traceback.format_exc())

        # Wait before next check
        await asyncio.sleep(check_interval)
