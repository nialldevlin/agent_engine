"""Custom CLI commands for mini-editor example app.

This module provides custom commands integrated with the CLI framework:
- /create - Create a new document
- /edit - Edit an existing document
- /summary - Show document summary
"""

from typing import Optional
from agent_engine.cli import CliContext, CommandError


def create_document(ctx: CliContext, args: str) -> None:
    """Create a new document.

    Usage:
        /create <title>

    Example:
        /create "My First Document"
    """
    if not args.strip():
        raise CommandError("Please provide a document title: /create <title>")

    title = args.strip()

    # Run engine to create document
    result = ctx.run_engine({
        "action": "create",
        "title": title,
        "user_input": ""  # Empty input for /create command - just creates the file
    })
    output = result.get("output") or {}
    path = output.get("path") or output.get("relative_path")

    print(f"\n[Document Created]")
    print(f"Title: {title}")
    if path:
        print(f"Path: {path}")
    print(f"Status: {result.get('status', 'unknown')}")


def edit_document(ctx: CliContext, args: str) -> None:
    """Edit an existing document.

    Usage:
        /edit <path>

    Example:
        /edit /tmp/my_document.md
    """
    if not args.strip():
        raise CommandError("Please provide document path: /edit <path>")

    path = args.strip()

    # Run engine to edit document
    result = ctx.run_engine({
        "action": "edit",
        "path": path,
        "user_input": "Review and improve the document at the provided path"
    })
    output = result.get("output") or {}

    print(f"\n[Document Edited]")
    print(f"Path: {path}")
    if output.get("summary"):
        print(output["summary"])
    print(f"Status: {result.get('status', 'unknown')}")


def show_summary(ctx: CliContext, args: str) -> None:
    """Show document summary.

    Usage:
        /summary <path>

    Example:
        /summary /tmp/my_document.md
    """
    if not args.strip():
        raise CommandError("Please provide document path: /summary <path>")

    path = args.strip()

    # Run engine to generate summary
    result = ctx.run_engine({
        "action": "edit",  # reuse edit branch to reach summary node
        "path": path,
        "summary_only": True,
        "user_input": "Generate a concise summary of the document"
    })
    output = result.get("output") or {}

    print(f"\n[Document Summary]")
    print(f"Path: {path}")
    if "summary" in output:
        print(output["summary"])
    elif "summary" in result:
        print(result["summary"])
    print(f"Status: {result.get('status', 'unknown')}")
