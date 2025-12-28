#!/usr/bin/env python3
"""
vLLM Server Startup Script

This script starts a vLLM server with OpenAI-compatible API endpoints.
It can be run in the foreground or background to serve LLM requests.

Usage:
    python start_vllm_server.py

Or run in background:
    nohup python start_vllm_server.py > vllm_server.log 2>&1 &
"""

import subprocess
import sys
import logging
import argparse

# Import configuration from centralized config
from config import VLLM_MODEL_NAME, VLLM_HOST, VLLM_PORT

# Set aliases for backward compatibility
MODEL_NAME = VLLM_MODEL_NAME
HOST = VLLM_HOST
PORT = VLLM_PORT

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# SERVER STARTUP
# ============================================================================

def start_vllm_server(model: str, host: str, port: int):
    """
    Start the vLLM server using the simplified 'vllm serve' command.

    Args:
        model: Model path (e.g., "bartowski/Llama-3.2-3B-Instruct-GGUF")
        host: Server host address
        port: Server port number
    """

    logger.info("=" * 70)
    logger.info("Starting vLLM Server")
    logger.info("=" * 70)
    logger.info(f"Model: {model}")
    logger.info(f"Server: http://{host}:{port}")
    logger.info(f"API Endpoint: http://{host}:{port}/v1")
    logger.info("=" * 70)

    # Build command using simplified 'vllm serve' syntax
    cmd = [
        "vllm",
        "serve",
        model,
        "--host", host,
        "--port", str(port)
    ]

    logger.info(f"Executing: {' '.join(cmd)}")
    logger.info("=" * 70)
    logger.info("Server is starting... This may take a few minutes to load the model.")
    logger.info("Press Ctrl+C to stop the server.")
    logger.info("=" * 70)

    try:
        # Run the server (blocks until server stops)
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 70)
        logger.info("Server stopped by user (Ctrl+C)")
        logger.info("=" * 70)
    except subprocess.CalledProcessError as e:
        logger.error(f"Server exited with error code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        logger.error("vLLM command not found. Make sure vLLM is installed:")
        logger.error("  pip install vllm")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Start vLLM OpenAI-compatible API server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with default settings
  python start_vllm_server.py

  # Run in background
  nohup python start_vllm_server.py > vllm_server.log 2>&1 &

  # Use a different model (GGUF format)
  python start_vllm_server.py --model bartowski/Llama-3.2-3B-Instruct-GGUF

  # Use a different model (standard format)
  python start_vllm_server.py --model mistralai/Mistral-7B-Instruct-v0.2

  # Use custom host and port
  python start_vllm_server.py --host 0.0.0.0 --port 8080
        """
    )

    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help=f"Model path (default: {MODEL_NAME})"
    )

    parser.add_argument(
        "--host",
        type=str,
        default=HOST,
        help=f"Server host address (default: {HOST})"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=PORT,
        help=f"Server port (default: {PORT})"
    )

    args = parser.parse_args()

    # Check if vLLM is installed
    try:
        import vllm
        logger.info(f"vLLM version: {vllm.__version__}")
    except ImportError:
        logger.error("vLLM is not installed. Please install it with: pip install vllm")
        sys.exit(1)

    # Start the server
    start_vllm_server(
        model=args.model,
        host=args.host,
        port=args.port
    )

if __name__ == "__main__":
    main()
