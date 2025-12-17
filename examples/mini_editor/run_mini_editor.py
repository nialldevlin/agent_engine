#!/usr/bin/env python3
"""Mini-Editor: Interactive document creation and editing tool.

This example demonstrates Agent Engine integration with the CLI framework,
showing how to build an interactive document editor using:
- Workflow DAGs for complex logic
- Agent nodes for creative work
- Memory stores for context
- CLI profiles for user interaction

Optional: Set ANTHROPIC_API_KEY environment variable to enable real LLM calls
instead of mock agents:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 run_mini_editor.py
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any

# Ensure the repo root and examples are in sys.path for custom command loading
_script_dir = Path(__file__).parent
_repo_root = _script_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from agent_engine import Engine
from agent_engine.cli import REPL, CliContext, CommandError


def setup_config_dir() -> str:
    """Ensure config directory exists and return its path."""
    config_dir = Path(__file__).parent / "config"

    if not config_dir.exists():
        raise RuntimeError(
            f"Config directory not found at {config_dir}. "
            "Please run this script from the examples/mini_editor directory."
        )

    return str(config_dir)


def initialize_engine(config_dir: str) -> Engine:
    """Initialize the Engine from config directory.

    Args:
        config_dir: Path to configuration directory

    Returns:
        Initialized Engine instance
    """
    try:
        engine = Engine.from_config_dir(config_dir)
        print(f"✓ Engine initialized from {config_dir}")

        if engine.agent_runtime.llm_client is None:
            print("  Using mock agents (set ANTHROPIC_API_KEY and unset AGENT_ENGINE_USE_MOCK_LLM to enable real LLM calls)")

        # Register custom normalize_request handler
        engine.deterministic_registry.register("normalize_request", normalize_request_handler)

        return engine
    except Exception as e:
        print(f"✗ Failed to initialize engine: {e}", file=sys.stderr)
        sys.exit(1)


def normalize_request_handler(task, node, context_package):
    """Parse free-form user input into structured request.

    Extracts action and filename from natural language requests like:
    - "Create a file test.md with instructions"
    - "Edit document.md"
    """
    import re
    from agent_engine.schemas import EngineError

    payload = task.current_output

    # If already structured, pass through
    if isinstance(payload, dict) and "action" in payload:
        return payload, None

    # Extract text from REPL-wrapped input
    input_text = ""
    if isinstance(payload, dict) and "input" in payload:
        input_text = payload.get("input", "")
        attached_files = payload.get("attached_files", [])
    elif isinstance(payload, str):
        input_text = payload
        attached_files = []
    else:
        input_text = str(payload)
        attached_files = []

    # Parse action and filename from text
    action = "create"  # default
    title = None

    # Look for action keywords
    lower_text = input_text.lower()
    if "edit" in lower_text or "update" in lower_text or "modify" in lower_text:
        action = "edit"

    # Extract filename (anything ending in .md, .txt, .py, etc.)
    filename_match = re.search(r'(\S+\.\w+)', input_text)
    if filename_match:
        title = filename_match.group(1)

    # Build structured output
    result = {
        "action": action,
        "title": title,
        "user_input": input_text,
        "attached_files": attached_files
    }
    return result, None


def create_document_example(engine: Engine) -> None:
    """Example: Create a new document programmatically.

    This demonstrates direct engine.run() calls without the REPL.
    """
    print("\n" + "="*60)
    print("Example: Create a Document")
    print("="*60)

    result = engine.run({
        "action": "create",
        "title": "Getting Started with Agent Engine",
        "user_input": "Create a brief guide to Agent Engine fundamentals"
    })

    print(f"Task ID: {result.get('task_id')}")
    print(f"Status: {result.get('status')}")

    # Show telemetry
    events = engine.get_events()
    print(f"Events emitted: {len(events)}")


def interactive_session(engine: Engine) -> None:
    """Run interactive REPL session.

    This demonstrates the full CLI framework with:
    - Profile-based configuration
    - Session history
    - Built-in commands
    - Custom commands
    - Real LLM calls (if ANTHROPIC_API_KEY is set)
    """
    print("\n" + "="*60)
    print("Interactive Mini-Editor Session")
    print("="*60)

    # Check if real LLM calls are enabled
    has_real_llm = engine.agent_runtime.llm_client is not None
    if has_real_llm:
        model_name = "Unknown"
        if hasattr(engine.agent_runtime, 'llm_client') and engine.agent_runtime.llm_client:
            if hasattr(engine.agent_runtime.llm_client, 'model'):
                model_name = engine.agent_runtime.llm_client.model
        print(f"\n✓ REAL LLM CALLS ENABLED ({model_name})")
    else:
        print("\n⚠ Using mock agents (no ANTHROPIC_API_KEY set)")

    print("\nTry these commands:")
    print("  /help                        - Show all commands")
    print("  /create 'Document Title'     - Create a new document")
    print("  /edit /path/to/document.md   - Edit an existing document")
    print("  /summary /path/to/document   - Show document summary")
    print("  /history                     - View session history")
    print("  /quit                        - Exit the REPL")
    print("")

    repl = engine.create_repl()
    repl.run()


def main() -> None:
    """Main entry point for mini-editor."""
    print("\n" + "="*60)
    print("Agent Engine Mini-Editor Example")
    print("="*60)
    print("\nThis example demonstrates:")
    print("  • DAG-based document workflows")
    print("  • Agent nodes for content creation")
    print("  • Memory stores for context")
    print("  • CLI framework with profiles")
    print("  • Interactive REPL sessions")
    print()

    # Setup and initialize
    try:
        config_dir = setup_config_dir()
        engine = initialize_engine(config_dir)
    except Exception as e:
        print(f"Setup failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Check command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "example":
            # Run example programmatically
            create_document_example(engine)
        elif sys.argv[1] == "interactive":
            # Run interactive session
            interactive_session(engine)
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("\nUsage:")
            print("  python run_mini_editor.py example       # Run example")
            print("  python run_mini_editor.py interactive   # Interactive REPL")
            print("  python run_mini_editor.py               # Same as interactive")
            sys.exit(1)
    else:
        # Default: interactive mode
        interactive_session(engine)


if __name__ == "__main__":
    main()
