"""Task scheduler and executor for automated task execution."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict

import tool_registry
from llm_interface import create_chat_completion


async def execute_scheduled_task(cell, task_data: dict):
    """Execute single scheduled task by calling its tool function"""
    task_name = task_data.get("name", "Unknown")
    tool_id = task_data.get("tool_id")
    function_name = task_data.get("function_name")
    input_type = task_data.get("input_type", "")
    input_data = task_data.get("input_data", "")

    logging.info(f"Executing scheduled task: {task_name}")
    logging.info(f"   Tool: {tool_id}, Function: {function_name}")
    logging.info(f"   Input Type: {input_type}, Input Data: {input_data}")

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

        parameters = {}
        if input_data:
            input_schema = target_tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})

            if properties:
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

        logging.info(f"Calling Tool tool '{function_name}' with parameters: {parameters}")

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

        tolerance = 30
        for scheduled_ts in timestamps:
            if abs(current_timestamp - scheduled_ts) <= tolerance:
                if last_run_timestamp < scheduled_ts - tolerance:
                    return True

        return False

    return False


async def task_scheduler(cell, tasks_dir: str):
    """Background task scheduler that runs tasks based on schedule"""
    logging.info("Task scheduler started")

    last_execution: Dict[str, int] = {}

    while True:
        try:
            if not os.path.exists(tasks_dir):
                await asyncio.sleep(60)
                continue

            current_timestamp = int(time.time())

            for filename in os.listdir(tasks_dir):
                if not filename.endswith(".json"):
                    continue

                task_path = os.path.join(tasks_dir, filename)

                try:
                    with open(task_path, 'r') as f:
                        task_data = json.load(f)

                    task_id = task_data.get("task_id")
                    task_name = task_data.get("name")
                    schedule_str = task_data.get("schedule")
                    status = task_data.get("status", "active")

                    if status != "active":
                        continue

                    if not schedule_str:
                        logging.warning(f"Task '{task_name}' has no schedule defined")
                        continue

                    schedule_info = parse_schedule(schedule_str)
                    last_run_timestamp = last_execution.get(task_id, 0)

                    if should_task_run(schedule_info, last_run_timestamp, current_timestamp):
                        logging.info(f"Triggering scheduled task: {task_name}")
                        logging.info(f"   Schedule: {schedule_str}")

                        await execute_scheduled_task(cell, task_data)
                        last_execution[task_id] = current_timestamp

                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse task file {filename}: {e}")
                except Exception as e:
                    logging.error(f"Error processing task {filename}: {e}")
                    import traceback
                    logging.error(traceback.format_exc())

            await asyncio.sleep(60)

        except Exception as e:
            logging.error(f"Error in task scheduler: {e}")
            import traceback
            logging.error(traceback.format_exc())
            await asyncio.sleep(60)
