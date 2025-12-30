#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VLLM_PID_FILE=".vllm_pid"
SERVER_PID_FILE=".server_pid"

stop_process() {
    local pid_file=$1
    local process_name=$2

    if [ ! -f "$pid_file" ]; then
        echo "No PID file found for $process_name"
        return 1
    fi

    local pid=$(cat "$pid_file")

    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo "$process_name (PID: $pid) is not running"
        rm -f "$pid_file"
        return 1
    fi

    echo "Stopping $process_name (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        ((count++))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        echo "Force stopping $process_name..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$pid_file"
    echo "$process_name stopped"
    return 0
}

main() {
    echo "Stopping Neuronum Server"
    echo ""

    local stopped_any=false

    if stop_process "$SERVER_PID_FILE" "Neuronum Server"; then
        stopped_any=true
    fi

    if stop_process "$VLLM_PID_FILE" "vLLM Server"; then
        stopped_any=true
    fi

    echo ""
    if [ "$stopped_any" = true ]; then
        echo "Shutdown complete"
    else
        echo "No running processes found"
    fi
}

main
