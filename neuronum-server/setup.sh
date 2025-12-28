#!/bin/bash
# ============================================================================
# Neuronum Server Setup Script
# ============================================================================
# This script automates the setup and launch of the Neuronum Server.
# It will:
# 1. Create a Python virtual environment
# 2. Install all dependencies
# 3. Start the vLLM server in the background
# 4. Launch the agent
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
VENV_DIR="venv"
VLLM_LOG_FILE="vllm_server.log"
VLLM_PID_FILE=".vllm_pid"

# Helper functions
print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

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

# Check if Python is installed
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python $PYTHON_VERSION found"
        return 0
    else
        print_error "Python 3 is not installed. Please install Python 3.8 or higher."
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    print_header "Setting up Virtual Environment"

    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists at $VENV_DIR"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            print_info "Using existing virtual environment"
            return 0
        fi
    fi

    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created at $VENV_DIR"
}

# Activate virtual environment
activate_venv() {
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    print_success "Virtual environment activated"
}

# Install dependencies
install_dependencies() {
    print_header "Installing Dependencies"

    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found!"
        exit 1
    fi

    print_info "Upgrading pip..."
    pip install --upgrade pip

    print_info "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt

    print_success "All dependencies installed"
}

# Check configuration
check_config() {
    print_header "Checking Configuration"

    if [ ! -f "server.config" ]; then
        print_error "server.config not found!"
        exit 1
    fi

    # Check if mnemonic is set
    if grep -q "your_12_word_mnemonic_here" server.config; then
        print_warning "MNEMONIC in server.config is not configured!"
        print_info "Please edit server.config and set your Cell mnemonic before running the agent."
        exit 1
    fi

    print_success "Configuration file validated"
}

# Start vLLM server
start_vllm() {
    print_header "Starting vLLM Server"

    # Check if vLLM is already running
    if [ -f "$VLLM_PID_FILE" ]; then
        OLD_PID=$(cat "$VLLM_PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            print_warning "vLLM server is already running (PID: $OLD_PID)"
            read -p "Do you want to restart it? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Stopping existing vLLM server..."
                kill "$OLD_PID" 2>/dev/null || true
                sleep 2
            else
                print_info "Using existing vLLM server"
                return 0
            fi
        fi
    fi

    print_info "Starting vLLM server in background..."
    print_info "Log file: $VLLM_LOG_FILE"

    # Start vLLM server in background
    nohup python start_vllm_server.py > "$VLLM_LOG_FILE" 2>&1 &
    VLLM_PID=$!
    echo "$VLLM_PID" > "$VLLM_PID_FILE"

    print_info "Waiting for vLLM server to start (PID: $VLLM_PID)..."
    sleep 5

    # Check if process is still running
    if ps -p "$VLLM_PID" > /dev/null 2>&1; then
        print_success "vLLM server started successfully (PID: $VLLM_PID)"
    else
        print_error "vLLM server failed to start. Check $VLLM_LOG_FILE for details."
        exit 1
    fi
}

# Start agent
serve_agent() {
    print_header "Starting Neuronum Server"

    print_info "Launching server.py..."
    print_info "Press Ctrl+C to stop the agent"
    echo

    # Run the agent
    python server.py
}

# Cleanup function
cleanup() {
    print_header "Cleanup"

    if [ -f "$VLLM_PID_FILE" ]; then
        VLLM_PID=$(cat "$VLLM_PID_FILE")
        if ps -p "$VLLM_PID" > /dev/null 2>&1; then
            print_info "Stopping vLLM server (PID: $VLLM_PID)..."
            kill "$VLLM_PID" 2>/dev/null || true
        fi
        rm -f "$VLLM_PID_FILE"
    fi

    print_success "Cleanup complete"
}

# Trap Ctrl+C to cleanup
trap cleanup EXIT

# Main execution
main() {
    print_header "Neuronum Server Setup"

    check_python
    create_venv
    activate_venv
    install_dependencies
    check_config
    start_vllm
    serve_agent
}

# Run main function
main
