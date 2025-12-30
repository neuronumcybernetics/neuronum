#!/usr/bin/env python3
"""vLLM Server Startup Script"""

import subprocess
import sys
import logging
import argparse

from config import VLLM_MODEL_NAME, VLLM_HOST, VLLM_PORT

MODEL_NAME = VLLM_MODEL_NAME
HOST = VLLM_HOST
PORT = VLLM_PORT

# Logging Setup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Server Startup

def start_vllm_server(model: str, host: str, port: int):
    """Start vLLM server using simplified vllm serve command"""

    logger.info("=" * 70)
    logger.info("Starting vLLM Server")
    logger.info("=" * 70)
    logger.info(f"Model: {model}")
    logger.info(f"Server: http://{host}:{port}")
    logger.info(f"API Endpoint: http://{host}:{port}/v1")
    logger.info("=" * 70)

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
        import os
        os.execvp("vllm", cmd)
    except FileNotFoundError:
        logger.error("vLLM command not found. Make sure vLLM is installed:")
        logger.error("  pip install vllm")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)

def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Start vLLM OpenAI-compatible API server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_vllm_server.py
  nohup python start_vllm_server.py > vllm_server.log 2>&1 &
  python start_vllm_server.py --model bartowski/Llama-3.2-3B-Instruct-GGUF
  python start_vllm_server.py --model mistralai/Mistral-7B-Instruct-v0.2
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

    try:
        import vllm
        logger.info(f"vLLM version: {vllm.__version__}")
    except ImportError:
        logger.error("vLLM is not installed. Please install it with: pip install vllm")
        sys.exit(1)

    start_vllm_server(
        model=args.model,
        host=args.host,
        port=args.port
    )

if __name__ == "__main__":
    main()
