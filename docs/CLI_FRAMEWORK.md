# Phase 18: CLI Framework (Reusable REPL)

## Overview

Phase 18 implements a **shared, extensible CLI/REPL framework** for Agent Engine that enables multi-turn conversational sessions with:

- **Profile-based configuration** via `cli_profiles.yaml`
- **Session history management** with optional JSONL persistence
- **10 built-in commands** (`/help`, `/mode`, `/attach`, `/history`, `/retry`, `/edit-last`, `/open`, `/diff`, `/apply_patch`, `/quit`)
- **Extensible command registry** via decorator-based API
- **File operations** (view, edit, diff, patch) with workspace safety
- **Telemetry integration** from Phase 8
- **Typed exception hierarchy** for CLI error handling

All CLI interactions map to canonical `Engine.run()` calls. The CLI layer does NOT introduce new routing semantics or modify DAG behavior.

---

## Quick Start

### Starting the REPL

```python
from agent_engine import Engine

# Load engine from config directory
engine = Engine.from_config_dir("./config")

# Create and run REPL
repl = engine.create_repl()
repl.run()
```

### Basic Usage

```
[default]> /help                    # List available commands
[default]> /help attach             # Show help for specific command
[default]> /mode                    # Show current profile
[default]> /attach myfile.txt       # Attach file to session
[default]> /history                 # View session history
[default]> /open myfile.txt         # View file contents
[default]> hello world              # Send input to engine
[default]> /quit                    # Exit REPL
```

---

## Architecture

### Module Structure

```
src/agent_engine/cli/
├── __init__.py              # Public API exports
├── exceptions.py            # CliError, CommandError
├── profile.py              # Profile loading and management
├── session.py              # Session state management
├── context.py              # CliContext with helper methods
├── registry.py             # Command registry and decorator
├── commands.py             # 10 built-in commands
├── file_ops.py            # File viewing/editing operations
└── repl.py                # Main REPL loop
```

### Key Components

#### 1. **Profile System** (`profile.py`)

Profiles control CLI behavior through `cli_profiles.yaml`:

```python
from agent_engine.cli import load_profiles, get_default_profile

# Load profiles from config directory
profiles = load_profiles("./config")

# Or use default profile when no yaml exists
default = get_default_profile()
```

**Profile Fields:**
- `id` (required): Unique identifier
- `label`: Human-friendly name
- `description`: Profile description
- `default_config_dir`: Workspace root for this profile
- `default_workflow_id`: Target workflow for Engine.run()
- `session_policies`: History persistence settings
- `input_mappings`: Engine.run() payload configuration
- `custom_commands`: List of custom command entrypoints
- `presentation_rules`: Output formatting rules
- `telemetry_overlays`: Event display configuration

#### 2. **Session Management** (`session.py`)

Sessions track history and state across turns:

```python
from agent_engine.cli import Session, SessionEntry

# Create session
session = Session("session_id_1", profile)

# Add entries
entry = SessionEntry(
    session_id="session_id_1",
    timestamp="2024-01-01T12:00:00",
    role="user",
    input="hello"
)
session.add_entry(entry)

# Attach files
session.attach_file("/path/to/file.txt")

# Persist to JSONL (if enabled in profile)
session.persist()

# Load from disk
session.load()
```

**SessionEntry Fields:**
- `session_id`: Unique session identifier
- `timestamp`: ISO-8601 timestamp
- `role`: "user" or "system"
- `input`: Any JSON-serializable data
- `command`: Optional command name
- `engine_run_metadata`: Optional metadata from Engine.run()
- `attached_files`: List of attached file paths

#### 3. **CLI Context** (`context.py`)

Context object passed to all command functions:

```python
from agent_engine.cli import CliContext

# Command functions receive context parameter
def my_command(ctx: CliContext, args: str) -> None:
    # Available methods and properties:
    ctx.run_engine(input_data)          # Execute Engine.run() and record
    ctx.attach_file(path)               # Attach file to session
    ctx.get_telemetry()                 # Get telemetry events
    ctx.get_current_profile()           # Get active profile
    ctx.switch_profile(profile_id)      # Change profile

    # Available properties:
    ctx.session_id                      # Current session ID
    ctx.active_profile                  # Active Profile object
    ctx.workspace_root                  # Workspace directory path
    ctx.attached_files                  # Set of attached file paths
    ctx.engine                          # Engine instance
    ctx.history                         # List of SessionEntry objects
```

#### 4. **Command Registry** (`registry.py`)

Register commands using decorator:

```python
from agent_engine.cli import register_command, CliContext

@register_command("mycommand", aliases=["mc"])
def my_command(ctx: CliContext, args: str) -> None:
    """Description of my command."""
    print(f"Executing with args: {args}")
```

---

## Built-in Commands

All 10 built-in commands are reserved and cannot be overridden:

### 1. `/help` - Show commands

```
/help                    # List all commands
/help attach             # Show detailed help for /attach
```

### 2. `/mode` - Show or switch profile

```
/mode                    # Show current profile
/mode advanced_profile   # Switch to different profile
```

### 3. `/attach` - Attach files

```
/attach file1.txt file2.py    # Attach multiple files
# Files are validated within workspace boundaries
```

### 4. `/history` - Show session history

```
/history                       # Display last 10 entries
# Shows timestamp, role, input summary, and status
```

### 5. `/retry` - Re-run last input

```
/retry                   # Re-execute last user input with same parameters
```

### 6. `/edit-last` - Edit and re-run

```
/edit-last              # Opens editor for last input, then re-runs
```

### 7. `/open` - View file

```
/open config/workflow.yaml    # Display file with line numbers
# Validates path within workspace
```

### 8. `/diff` - Show file differences

```
/diff myfile.txt               # Compare with artifact version
```

### 9. `/apply_patch` - Apply patch

```
/apply_patch myfile.txt        # Apply patch with confirmation
```

### 10. `/quit` - Exit REPL

```
/quit                          # Save session and exit
/exit                          # Alias for /quit
```

---

## Custom Commands

### Creating Custom Commands

Define a function and configure in `cli_profiles.yaml`:

**my_app/cli.py:**
```python
from agent_engine.cli import CliContext, CommandError

def my_custom_command(ctx: CliContext, args: str) -> None:
    """Custom command that does something special."""
    try:
        result = ctx.run_engine(f"process: {args}")
        print(f"Result: {result}")
    except Exception as e:
        raise CommandError(
            message=str(e),
            command_name="mycommand",
            args=args
        )
```

**cli_profiles.yaml:**
```yaml
profiles:
  - id: default
    custom_commands:
      - name: mycommand
        entrypoint: my_app.cli:my_custom_command
        description: "My custom command"
        aliases: ["mc"]
        help: "Detailed help text for my command"
```

### Using Custom Commands

```
[default]> /mycommand some_args
[default]> /mc some_args                # Via alias
```

---

## Profile Configuration

### Minimal Profile

```yaml
profiles:
  - id: default
```

### Complete Profile Example

```yaml
profiles:
  - id: production
    label: Production Profile
    description: For production workflow execution
    default_config_dir: /var/agent_engine
    default_workflow_id: main_workflow

    session_policies:
      persist_history: true
      persist_attachments: true
      history_file: /var/log/agent_engine/history.jsonl
      max_history_items: 10000

    input_mappings:
      default:
        mode: chat                           # "chat" or "raw"
        attach_files_as_context: true
        include_profile_id: true
        include_session_id: true

    custom_commands:
      - name: analyze
        entrypoint: myapp.commands:analyze_command
        description: Analyze input data
        aliases: ["az", "analyze"]
        help: Performs analysis on provided input

    presentation_rules:
      show_system_messages: false
      show_telemetry_inline: true
      truncate_output_lines: 100

    telemetry_overlays:
      enabled: true
      level: verbose              # "summary" or "verbose"
```

---

## Session Persistence

### JSONL Format

Sessions persist to JSONL (JSON Lines) format when enabled:

```jsonl
{"session_id": "uuid", "timestamp": "2024-01-01T12:00:00", "role": "user", "input": "hello", "attached_files": []}
{"session_id": "uuid", "timestamp": "2024-01-01T12:00:01", "role": "system", "input": {...}, "engine_run_metadata": {...}, "attached_files": ["file.txt"]}
```

### Enabling Persistence

```yaml
profiles:
  - id: default
    session_policies:
      persist_history: true
      history_file: ./.agent_engine/sessions/history.jsonl
      max_history_items: 1000
```

### Default Location

If `history_file` is not specified:
```
./.agent_engine/sessions/history.jsonl  (under the active config directory)
```

---

## File Operations

### Workspace Safety

All file operations are validated against workspace boundaries:

```python
# Valid - within workspace
ctx.attach_file("config/workflow.yaml")
ctx.attach_file("./data/input.json")

# Invalid - outside workspace
ctx.attach_file("../../../etc/passwd")     # Raises CliError
ctx.attach_file("/etc/passwd")              # Raises CliError
```

### Viewing Files

```
/open config/workflow.yaml          # View with line numbers
/open ../outside/file.txt           # Error: outside workspace
```

### Editing

```
/edit-last                          # Edit last prompt and re-run
```

### Diffing

```
/diff myfile.txt                    # Compare with artifact
```

### Applying Patches

```
/apply_patch myfile.txt             # Apply patch with confirmation
```

---

## Telemetry Integration

### Telemetry Display

The CLI automatically surfaces telemetry events from Phase 8:

```
Result: {'task_id': 'task-123', 'status': 'success', ...}

=== Telemetry ===
[task_start] TaskStartEvent(task_id='task-123', workflow_id='main')
[task_end] TaskEndEvent(task_id='task-123', status='completed')
```

### Display Modes

**Summary Mode** (shows high-level events only):
```yaml
telemetry_overlays:
  level: summary
  # Shows: task_start, task_end, errors only
```

**Verbose Mode** (shows all events):
```yaml
telemetry_overlays:
  level: verbose
  # Shows: all events with full details
```

### Disabling Telemetry

```yaml
telemetry_overlays:
  enabled: false
```

---

## Exception Handling

### CliError

Raised for general CLI errors:

```python
from agent_engine.cli import CliError

raise CliError("Something went wrong")
```

### CommandError

Raised for command execution errors:

```python
from agent_engine.cli import CommandError

raise CommandError(
    message="Invalid argument",
    command_name="mycommand",
    args="bad_arg"
)
```

### JSON Serialization

Both exceptions support JSON serialization:

```python
error = CliError("test error")
error_dict = error.to_dict()
# {'message': 'test error'}
```

---

## Engine Integration

### Creating REPL from Engine

```python
from agent_engine import Engine

engine = Engine.from_config_dir("./config")

# Create REPL with default settings
repl = engine.create_repl()

# Or with specific profile
repl = engine.create_repl(profile_id="advanced")

# Or with custom config directory
repl = engine.create_repl(config_dir="/etc/agent_engine")

# Run the REPL
repl.run()
```

### Engine.run() Integration

Each user input (non-command) calls `engine.run()`:

```
[default]> hello world

# Internally calls:
engine.run(
    input="hello world",
    start_node_id=None
)
```

With input mappings applied:

```yaml
input_mappings:
  default:
    attach_files_as_context: true
    include_profile_id: true
    include_session_id: true

# Payload becomes:
{
    "input": "hello world",
    "profile_id": "default",
    "session_id": "uuid",
    "attached_files": ["file.txt"]
}
```

---

## Advanced Usage

### Custom Command with Engine Integration

```python
# my_app/commands.py
from agent_engine.cli import CliContext, CommandError

def process_command(ctx: CliContext, args: str) -> None:
    """Process data through engine workflow."""
    try:
        # Attach input file
        ctx.attach_file(f"input/{args}")

        # Run engine with attached files
        result = ctx.run_engine({
            "operation": "process",
            "file": args
        })

        # Display result
        print(f"Processing complete: {result['output']}")

    except Exception as e:
        raise CommandError(
            message=f"Processing failed: {str(e)}",
            command_name="process",
            args=args
        )
```

### Profile-Specific Workflows

```yaml
profiles:
  - id: development
    default_workflow_id: dev_workflow
    telemetry_overlays:
      level: verbose
      enabled: true

  - id: production
    default_workflow_id: prod_workflow
    telemetry_overlays:
      level: summary
      enabled: true
```

### History Management

```python
# From custom command
session = ctx.session
history = session.get_history()

for entry in history[-10:]:  # Last 10 entries
    print(f"[{entry.timestamp}] {entry.role}: {entry.input}")

# Get last user input for retry logic
last_input = session.get_last_user_prompt()
```

---

## Testing

The CLI framework includes comprehensive tests:

```bash
# Run all CLI tests
pytest tests/test_phase18_cli.py -v

# Run specific test class
pytest tests/test_phase18_cli.py::TestProfileLoading -v

# Run with coverage
pytest tests/test_phase18_cli.py --cov=agent_engine.cli
```

**Test Coverage (54+ tests):**
- Profile loading (5 tests)
- Session management (8 tests)
- Command registry (5 tests)
- File operations (6 tests)
- CLI context (4 tests)
- Built-in commands (12 tests)
- Exceptions (3 tests)
- Telemetry display (3 tests)
- Integration (5 tests)
- Edge cases (4 tests)

---

## Troubleshooting

### Profile Not Found

```
Error: Profile 'unknown' not found
```

**Solution:** Check `cli_profiles.yaml` and verify profile ID exists.

### File Outside Workspace

```
Error: Path is outside workspace: ../../../etc/passwd
```

**Solution:** Use relative paths from workspace root only.

### Session Persistence Failed

```
Warning: Could not save session: Failed to persist session
```

**Solution:** Check `history_file` path permissions and directory exists.

### Custom Command Not Loaded

```
Warning: Failed to load custom command 'mycommand': ...
```

**Solution:** Verify entrypoint format: `module.path:function_name`

---

## Performance Considerations

- **Session size**: Large histories (10k+ entries) may slow startup
- **File operations**: Very large files (>100MB) may be slow to display
- **Telemetry verbose mode**: High event volume impacts display performance
- **Custom commands**: Slow commands block REPL during execution

---

## Security Notes

- **Workspace boundaries:** File operations strictly validate paths
- **No code execution:** Profiles are declarative (no executable code)
- **Command isolation:** Built-in commands cannot be overridden
- **Path traversal:** `..` and absolute paths outside workspace rejected

---

## See Also

- `src/agent_engine/cli/` - CLI framework implementation
- `tests/test_phase18_cli.py` - Comprehensive test suite
- `examples/minimal_config/cli_profiles.yaml` - Example configuration
- `AGENT_ENGINE_SPEC.md §3` - Engine.run() specification
- `TELEMETRY.md` - Phase 8 telemetry events
