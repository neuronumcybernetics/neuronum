#!/bin/bash
# ============================================================================
# Neuronum Server Stop Script
# ============================================================================
# This script stops the Neuronum Server and vLLM server processes.
# ============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
VLLM_PID_FILE=".vllm_pid"
SERVER_PID_FILE=".server_pid"

# Helper functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

# Stop a process by PID file
stop_process() {
    local pid_file=$1
    local process_name=$2

    if [ ! -f "$pid_file" ]; then
        print_info "No PID file found for $process_name"
        return 1
    fi

    local pid=$(cat "$pid_file")

    if ! ps -p "$pid" > /dev/null 2>&1; then
        print_warning "$process_name (PID: $pid) is not running"
        rm -f "$pid_file"
        return 1
    fi

    print_info "Stopping $process_name (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    # Wait up to 10 seconds for graceful shutdown
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        ((count++))
    done

    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        print_warning "Force stopping $process_name..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$pid_file"
    print_success "$process_name stopped"
    return 0
}

# Main execution
main() {
    print_header "Stopping Neuronum Server"

    local stopped_any=false

    # Stop Neuronum Server
    if stop_process "$SERVER_PID_FILE" "Neuronum Server"; then
        stopped_any=true
    fi

    # Stop vLLM Server
    if stop_process "$VLLM_PID_FILE" "vLLM Server"; then
        stopped_any=true
    fi

    if [ "$stopped_any" = true ]; then
        echo ""
        print_success "Shutdown complete!"
    else
        echo ""
        print_info "No running processes found"
    fi
}

# Run main function
main
