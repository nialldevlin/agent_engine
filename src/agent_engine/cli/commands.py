"""
Built-in commands for Phase 18 CLI Framework.

Implements 10 reserved built-in commands.
"""

from typing import Optional, List
from datetime import datetime
import sys

from .registry import register_command, get_global_registry
from .context import CliContext
from .exceptions import CommandError, CliError
from .file_ops import validate_path, view_file, edit_buffer, compute_diff, apply_patch_safe


@register_command(
    "help",
    help_text="List commands or show detailed help for a specific command",
)
def help_command(ctx: CliContext, args: str) -> None:
    """List all commands or show detailed help for specific command."""
    registry = get_global_registry()

    if not args or not args.strip():
        # List all commands
        print("Available commands:")
        print("-" * 50)
        commands = registry.list_commands()
        for name, help_text in commands:
            help_preview = help_text.split("\n")[0] if help_text else "No help"
            print(f"  /{name:<20} {help_preview}")
        print("-" * 50)
    else:
        # Show detailed help for specific command
        command_name = args.strip().lstrip("/")
        help_text = registry.get_help(command_name)
        print(f"Help for /{command_name}:")
        print(help_text)


@register_command(
    "mode",
    help_text="Show current profile or switch profiles",
)
def mode_command(ctx: CliContext, args: str) -> None:
    """Show current profile or switch to specified profile."""
    profile = ctx.get_current_profile()

    if not args or not args.strip():
        # Show current profile
        print(f"Current profile: {profile.id}")
        if profile.label:
            print(f"Label: {profile.label}")
        if profile.description:
            print(f"Description: {profile.description}")
    else:
        # Switch profile - requires profile list from REPL
        # This will be called from REPL with available_profiles
        raise CommandError(
            message="Profile switching requires REPL integration",
            command_name="mode",
            args=args,
        )


@register_command(
    "attach",
    help_text="Attach files to session context",
)
def attach_command(ctx: CliContext, args: str) -> None:
    """Attach files to session context."""
    if not args or not args.strip():
        raise CommandError(
            message="At least one file path required",
            command_name="attach",
        )

    paths = args.split()
    attached_count = 0

    for path in paths:
        try:
            ctx.attach_file(path)
            attached_count += 1
        except CliError as e:
            print(f"Warning: Failed to attach {path}: {e}")

    print(f"Attached {attached_count} file(s)")
    current_attached = ctx.attached_files
    if current_attached:
        print("Currently attached files:")
        for f in sorted(current_attached):
            print(f"  - {f}")


@register_command(
    "history",
    help_text="Show session history",
)
def history_command(ctx: CliContext, args: str) -> None:
    """Display session history."""
    history = ctx.history
    max_items = ctx.active_profile.session_policies.max_history_items

    if not history:
        print("No history")
        return

    # Show recent entries
    display_count = min(len(history), 10)  # Show last 10
    print(f"Session history (showing {display_count} of {len(history)} entries):")
    print("-" * 80)

    for entry in history[-display_count:]:
        print(f"[{entry.timestamp}] {entry.role.upper()}")
        input_str = str(entry.input)[:100]  # Truncate long inputs
        print(f"  Input: {input_str}")
        if entry.command:
            print(f"  Command: {entry.command}")
        if entry.engine_run_metadata:
            status = entry.engine_run_metadata.get("status", "unknown")
            print(f"  Status: {status}")
        print()


@register_command(
    "retry",
    help_text="Re-run last Engine.run() with same input",
)
def retry_command(ctx: CliContext, args: str) -> None:
    """Re-run last user prompt."""
    last_prompt = ctx.session.get_last_user_prompt()

    if not last_prompt:
        raise CommandError(
            message="No previous user input to retry",
            command_name="retry",
        )

    print(f"Retrying with: {last_prompt}")
    result = ctx.run_engine(last_prompt)
    print(f"Result: {result}")


@register_command(
    "edit-last",
    help_text="Edit and re-run last user prompt",
)
def edit_last_command(ctx: CliContext, args: str) -> None:
    """Edit and re-run last user prompt."""
    last_prompt = ctx.session.get_last_user_prompt()

    if not last_prompt:
        raise CommandError(
            message="No previous user input to edit",
            command_name="edit-last",
        )

    print("Current prompt:")
    print(last_prompt)
    edited_prompt = edit_buffer(last_prompt)

    if edited_prompt != last_prompt:
        print("Running edited prompt...")
        result = ctx.run_engine(edited_prompt)
        print(f"Result: {result}")
    else:
        print("No changes made")


@register_command(
    "open",
    help_text="View file in read-only terminal viewer",
)
def open_command(ctx: CliContext, args: str) -> None:
    """View file contents."""
    if not args or not args.strip():
        raise CommandError(
            message="File path required",
            command_name="open",
        )

    try:
        view_file(args.strip(), ctx.workspace_root)
    except CliError as e:
        raise CommandError(
            message=str(e),
            command_name="open",
            args=args,
        )


@register_command(
    "diff",
    help_text="Show diff between on-disk file and session artifacts",
)
def diff_command(ctx: CliContext, args: str) -> None:
    """Show diff between file and artifact."""
    if not args or not args.strip():
        raise CommandError(
            message="File path required",
            command_name="diff",
        )

    # For now, show a simple message
    # In a full implementation, this would find artifacts from recent runs
    print(f"Diff for: {args}")
    print("(Artifact integration would be implemented in full version)")


@register_command(
    "apply_patch",
    help_text="Apply patch artifact with confirmation",
)
def apply_patch_command(ctx: CliContext, args: str) -> None:
    """Apply patch to file."""
    if not args or not args.strip():
        raise CommandError(
            message="File path required",
            command_name="apply_patch",
        )

    # For now, show a simple message
    # In a full implementation, this would apply patches with confirmation
    print(f"Apply patch to: {args}")
    print("(Patch application would be implemented in full version)")


@register_command(
    "queue",
    help_text="Queue a task for later execution",
)
def queue_command(ctx: CliContext, args: str) -> None:
    """Queue a task for execution (Phase 21).

    Usage: /queue <input_expression> [start_node]

    Examples:
        /queue {"text": "hello"}
        /queue {"text": "hello"} custom_start_node
    """
    if not args or not args.strip():
        raise CommandError(
            message="Input expression required. Format: /queue <input> [start_node]",
            command_name="queue",
        )

    parts = args.strip().split(maxsplit=1)
    input_expr = parts[0]
    start_node = parts[1] if len(parts) > 1 else None

    try:
        # Parse input as JSON
        import json
        input_data = json.loads(input_expr)
    except json.JSONDecodeError as e:
        raise CommandError(
            message=f"Invalid JSON input: {e}",
            command_name="queue",
            args=args,
        )

    try:
        task_id = ctx.engine.enqueue(input_data, start_node)
        print(f"Task queued: {task_id}")
        print(f"Queue size: {ctx.engine.get_queue_status()['queue_size']}")
    except Exception as e:
        raise CommandError(
            message=f"Failed to queue task: {e}",
            command_name="queue",
            args=args,
        )


@register_command(
    "run-queue",
    help_text="Execute all queued tasks sequentially",
)
def run_queue_command(ctx: CliContext, args: str) -> None:
    """Execute all queued tasks (Phase 21)."""
    try:
        print("Executing queued tasks...")
        results = ctx.engine.run_queued()

        print(f"\nCompleted {len(results)} task(s):")
        for result in results:
            status = result.get("status", "unknown")
            task_id = result.get("task_id", "unknown")
            symbol = "✓" if status == "completed" else "✗"
            print(f"  {symbol} {task_id}: {status}")
            if result.get("error"):
                print(f"      Error: {result['error']}")

        # Show final queue status
        status = ctx.engine.get_queue_status()
        print(f"\nQueue status:")
        print(f"  Remaining: {status['queue_size']}")
        print(f"  Running: {status['running_count']}")
        print(f"  Completed: {status['completed_count']}")

    except Exception as e:
        raise CommandError(
            message=f"Failed to run queued tasks: {e}",
            command_name="run-queue",
        )


@register_command(
    "queue-status",
    help_text="Show queue status and task states",
)
def queue_status_command(ctx: CliContext, args: str) -> None:
    """Show scheduler and queue status (Phase 21)."""
    try:
        status = ctx.engine.get_queue_status()

        print("Scheduler Status:")
        print(f"  Enabled: {status.get('scheduler_enabled', False)}")
        print(f"  Max Concurrency: {status.get('max_concurrency', 'N/A')}")
        print(f"  Queue Policy: {status.get('queue_policy', 'N/A')}")
        print(f"  Max Queue Size: {status.get('max_queue_size', 'Unlimited')}")

        print("\nQueue Statistics:")
        print(f"  Queued: {status.get('queue_size', 0)}")
        print(f"  Running: {status.get('running_count', 0)}")
        print(f"  Completed: {status.get('completed_count', 0)}")

        # Show task details if requested
        if args and args.strip() == "-v":
            tasks = status.get('tasks', {})
            if tasks:
                print("\nTask Details:")
                for task_id, task_info in tasks.items():
                    state = task_info.get('state', 'unknown')
                    print(f"  [{state}] {task_id}")
                    if 'enqueued_at' in task_info:
                        print(f"      Enqueued: {task_info['enqueued_at']}")
                    if 'started_at' in task_info:
                        print(f"      Started: {task_info['started_at']}")
                    if 'completed_at' in task_info:
                        print(f"      Completed: {task_info['completed_at']}")
                    if 'error' in task_info and task_info['error']:
                        print(f"      Error: {task_info['error']}")
            else:
                print("\nNo tasks in scheduler")

    except Exception as e:
        raise CommandError(
            message=f"Failed to get queue status: {e}",
            command_name="queue-status",
        )


@register_command(
    "quit",
    aliases=["exit"],
    help_text="Exit REPL",
)
def quit_command(ctx: CliContext, args: str) -> None:
    """Exit the REPL cleanly."""
    # Persist session if enabled
    try:
        ctx.session.persist()
        print("Session saved")
    except CliError as e:
        print(f"Warning: Could not save session: {e}")

    print("Goodbye!")
    sys.exit(0)
