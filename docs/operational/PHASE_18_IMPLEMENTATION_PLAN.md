# PHASE_18_IMPLEMENTATION_PLAN.md

## SECTION 1 — Phase Summary

**Phase 18: CLI Framework (Reusable REPL)**

Implement a shared, extensible CLI/REPL framework under `src/agent_engine/cli/` that provides:
- Multi-turn conversational sessions with history management
- Profile-based configuration via `cli_profiles.yaml`
- Built-in command set (`/help`, `/mode`, `/attach`, `/history`, `/retry`, `/edit-last`, `/open`, `/diff`, `/apply_patch`, `/quit`)
- Extensible command registry via decorator-based API
- File operations (view, edit, diff, patch) within workspace boundaries
- Session state persistence (optional JSONL format)
- Telemetry event surfacing from Phase 8
- Typed exception hierarchy (`CliError`, `CommandError`)

All CLI interactions map to canonical `Engine.run()` calls. The CLI layer does NOT introduce new routing semantics or modify DAG behavior.

---

## SECTION 2 — Requirements & Invariants

### 2.1 Architecture Constraints

1. **CLI code location**: All CLI code MUST reside under `src/agent_engine/cli/`
2. **Engine interaction**: CLI interacts with engine ONLY via `Engine.run()` and public Engine APIs
3. **No routing changes**: CLI MUST NOT modify DAG semantics, routing rules, or node behaviors
4. **Declarative profiles**: All profile configuration via `cli_profiles.yaml` with no embedded executable code
5. **Command isolation**: Built-in commands are reserved and cannot be overridden by profiles
6. **Workspace safety**: File operations MUST operate only within configured workspace root with path validation

### 2.2 cli_profiles.yaml Schema

**Required fields**:
- `profiles[]` (list of profile objects)
  - `id` (string): Unique profile identifier

**Optional fields per profile**:
- `label` (string): Human-friendly name
- `description` (string): Profile description
- `default_config_dir` (string): Project/workspace root for this profile
- `default_workflow_id` (string): Workflow to target for Engine.run
- `session_policies` (object):
  - `persist_history` (bool, default: true)
  - `persist_attachments` (bool, default: true)
  - `history_file` (string): Path for JSONL history
  - `max_history_items` (int): History size limit
- `input_mappings` (object):
  - `default` (object):
    - `mode` (string): "chat" | "raw"
    - `attach_files_as_context` (bool)
    - `include_profile_id` (bool)
    - `include_session_id` (bool)
- `custom_commands` (list):
  - `name` (string): Command name WITHOUT leading slash
  - `entrypoint` (string): Python import path (e.g., "my_app.cli:test_command")
  - `description` (string)
  - `aliases` (list of strings)
  - `help` (string)
- `presentation_rules` (object):
  - `show_system_messages` (bool, default: false)
  - `show_telemetry_inline` (bool, default: true)
  - `truncate_output_lines` (int)
- `telemetry_overlays` (object):
  - `enabled` (bool, default: true)
  - `level` (string): "summary" | "verbose"

### 2.3 Built-in Commands (Reserved, Non-Overridable)

1. `/help` - List all commands or show detailed help for specific command
2. `/mode` - Show current profile or switch profiles
3. `/attach <path...>` - Attach files to session context
4. `/history` - Show session history
5. `/retry` - Re-run last Engine.run() with same input
6. `/edit-last` - Edit and re-run last user prompt
7. `/open <path>` - View file in read-only terminal viewer
8. `/diff` - Show diff between on-disk file and session artifacts
9. `/apply_patch` - Apply patch artifact with confirmation
10. `/quit` (alias `/exit`) - Exit REPL

### 2.4 Session State

**In-memory storage** (required):
- List of history entries: `{timestamp, role, input, result_metadata}`
- Set of attached file paths
- Last user prompt
- Current profile

**Optional disk persistence** (if `session_policies.persist_history=true`):
- Format: JSON Lines (JSONL)
- Location: `<config_dir>/.agent_engine/sessions/` or `~/.agent_engine/sessions/`
- Content per line: `{session_id, timestamp, role, input, command, engine_run_metadata, attached_files}`

### 2.5 File Operations

**Workspace safety**:
- All file paths MUST be resolved and validated against workspace root
- Reject paths outside workspace (absolute paths, `..` traversal)
- Confirmation prompts for destructive operations (write, patch)

**Implementation constraints**:
- v1: Simple in-process text viewer/editor
- Plain text display with optional line numbers
- Scroll via keybindings or paging
- Edit mode: line-based input buffer (not full-screen editor)
- NO requirement for syntax highlighting in v1
- NO requirement for external editors (nano/vim) in v1

### 2.6 Telemetry Integration

**Required telemetry surfacing**:
- Display telemetry events before/after each `Engine.run()` invocation
- Show task start/end events
- Show node start/end events
- Show tool invocation events
- Show errors and failures

**Display mode** (controlled by profile):
- `summary`: Show only high-level events (task start/end, errors)
- `verbose`: Show all telemetry events inline

### 2.7 Exception Hierarchy

**CliError** (base exception):
- Raised for general CLI errors
- Fields: `message` (string)

**CommandError** (subclass of CliError):
- Raised for command execution errors
- Fields: `message` (string), `command_name` (string), `args` (optional string)

Both exceptions MUST be structured and JSON-serializable for logging.

### 2.8 Command Extension API

**Decorator-based registration**:
```
@register_command(name: str, aliases: Optional[List[str]] = None)
def command_function(ctx: CliContext, args: str) -> None:
    ...
```

**CliContext interface** (required fields):
- `session_id` (string): Current session ID
- `active_profile` (Profile object): Current profile
- `workspace_root` (string): Workspace directory path
- `attached_files` (Set[str]): Currently attached files
- `engine` (Engine): Engine instance
- `history` (List): Session history
- Helper methods:
  - `run_engine(input: Any) -> Dict`: Execute Engine.run() and record in history
  - `attach_file(path: str) -> None`: Add file to attached set
  - `get_telemetry() -> List[Event]`: Get telemetry events

---

## SECTION 3 — LLM Implementation Plan

### Step 1: Create CLI Module Structure

Create directory structure:
```
src/agent_engine/cli/
├── __init__.py
├── repl.py          # Main REPL loop
├── commands.py      # Built-in command implementations
├── context.py       # CliContext class
├── exceptions.py    # CliError, CommandError
├── profile.py       # Profile loading and management
├── session.py       # Session state management
├── file_ops.py      # File viewing/editing operations
└── registry.py      # Command registry and decorator
```

Export public API from `src/agent_engine/cli/__init__.py`:
- `REPL` (main entry point class)
- `register_command` (decorator)
- `CliContext` (context object)
- `CliError`, `CommandError` (exceptions)

### Step 2: Implement Exception Hierarchy

File: `src/agent_engine/cli/exceptions.py`

Define:
- `CliError` base exception with `message` field
- `CommandError` subclass with `message`, `command_name`, `args` fields
- Both exceptions must be dataclass-based for JSON serialization
- Add `__str__` methods for human-readable output

### Step 3: Implement Profile Management

File: `src/agent_engine/cli/profile.py`

Define:
- `Profile` dataclass matching cli_profiles.yaml schema (Section 2.2)
- `SessionPolicies` dataclass for session_policies section
- `InputMappings` dataclass for input_mappings section
- `PresentationRules` dataclass for presentation_rules section
- `TelemetryOverlays` dataclass for telemetry_overlays section
- `CustomCommand` dataclass for custom_commands entries

Implement:
- `load_profiles(config_dir: str) -> List[Profile]`:
  - Load cli_profiles.yaml from config_dir
  - Parse YAML into Profile objects
  - Validate required fields
  - Return list of profiles
  - Raise `CliError` on validation failures

- `get_default_profile() -> Profile`:
  - Return sensible default profile when no cli_profiles.yaml exists
  - Use default values from Section 2.2

### Step 4: Implement Session Management

File: `src/agent_engine/cli/session.py`

Define:
- `SessionEntry` dataclass:
  - `session_id` (str)
  - `timestamp` (str, ISO-8601)
  - `role` (str: "user" or "system")
  - `input` (Any)
  - `command` (Optional[str])
  - `engine_run_metadata` (Optional[Dict])
  - `attached_files` (List[str])

- `Session` class with methods:
  - `__init__(session_id: str, profile: Profile)`
  - `add_entry(entry: SessionEntry) -> None`: Add to in-memory history
  - `get_history() -> List[SessionEntry]`: Return history list
  - `get_last_user_prompt() -> Optional[str]`: Return last user input
  - `attach_file(path: str) -> None`: Add to attached files set
  - `get_attached_files() -> Set[str]`: Return attached files
  - `persist() -> None`: Write history to disk (JSONL format) if enabled
  - `load() -> None`: Load history from disk if exists
  - `clear_completed_tasks() -> None`: Optional cleanup

Persistence implementation:
- If `profile.session_policies.persist_history` is True:
  - Write each entry as one JSON line to history_file path
  - Create parent directories if needed
  - Use append mode for incremental writes
- If False: keep in-memory only

### Step 5: Implement CliContext

File: `src/agent_engine/cli/context.py`

Define:
- `CliContext` class with required fields from Section 2.8
- Constructor: `__init__(session: Session, engine: Engine, profile: Profile, workspace_root: str)`
- Methods:
  - `run_engine(input: Any, start_node_id: Optional[str] = None) -> Dict`:
    - Call `self.engine.run(input, start_node_id)`
    - Record in session history
    - Surface telemetry if enabled
    - Return result dict
  - `attach_file(path: str) -> None`:
    - Validate path is within workspace_root
    - Call `self.session.attach_file(path)`
  - `get_telemetry() -> List[Event]`:
    - Return `self.engine.telemetry.events`
  - `get_current_profile() -> Profile`:
    - Return active profile
  - `switch_profile(profile_id: str) -> None`:
    - Change active profile if valid

### Step 6: Implement Command Registry

File: `src/agent_engine/cli/registry.py`

Define:
- `CommandRegistry` class:
  - `_commands`: Dict[str, Callable] (command name -> function)
  - `_aliases`: Dict[str, str] (alias -> command name)
  - `register(name: str, func: Callable, aliases: Optional[List[str]] = None) -> None`
  - `get_command(name: str) -> Optional[Callable]`
  - `list_commands() -> List[Tuple[str, str]]`: Return (name, description) pairs
  - `get_help(command_name: str) -> str`: Return detailed help

- Global registry instance: `_global_registry`

- Decorator function:
  ```
  def register_command(name: str, aliases: Optional[List[str]] = None):
      def decorator(func: Callable):
          _global_registry.register(name, func, aliases)
          return func
      return decorator
  ```

### Step 7: Implement Built-in Commands

File: `src/agent_engine/cli/commands.py`

Implement each built-in command as a function with signature:
`def command_name(ctx: CliContext, args: str) -> None`

Commands to implement:

1. **help_command**:
   - No args: Print list of all commands (built-in + custom) with descriptions
   - With arg: Print detailed help for specified command
   - Use registry to discover all registered commands

2. **mode_command**:
   - No args: Print current profile ID and label
   - With arg: Switch to specified profile using `ctx.switch_profile(profile_id)`
   - Validate profile exists, raise `CommandError` if not

3. **attach_command**:
   - Parse space-separated paths from args
   - For each path: call `ctx.attach_file(path)`
   - Print confirmation message with list of attached files
   - Handle path validation errors

4. **history_command**:
   - Retrieve session history via `ctx.history`
   - Format and print recent entries (timestamp, role, input summary, result status)
   - Respect `max_history_items` from profile

5. **retry_command**:
   - Get last user prompt from session
   - Re-run `ctx.run_engine(last_prompt)`
   - Print result

6. **edit_last_command**:
   - Get last user prompt from session
   - Enter simple line-based edit mode:
     - Display current prompt
     - Accept multi-line input (end with blank line or EOF)
     - Re-run with edited prompt via `ctx.run_engine(edited_prompt)`

7. **open_command**:
   - Parse file path from args
   - Validate path within workspace
   - Read file contents
   - Display in simple pager (see file_ops.py)

8. **diff_command**:
   - Find recent artifacts for current session
   - Compare on-disk file with artifact version
   - Display unified diff format

9. **apply_patch_command**:
   - Find patch artifacts for session
   - Display patch preview
   - Prompt for confirmation
   - Apply patch if confirmed
   - Report success/failure

10. **quit_command**:
    - Persist session if enabled
    - Exit REPL cleanly

Register all built-in commands in module initialization:
```
register_command("help")(help_command)
register_command("mode")(mode_command)
register_command("attach")(attach_command)
# ... etc
register_command("quit", aliases=["exit"])(quit_command)
```

### Step 8: Implement File Operations

File: `src/agent_engine/cli/file_ops.py`

Implement:

1. **validate_path(path: str, workspace_root: str) -> str**:
   - Resolve path relative to workspace_root
   - Check for `..` traversal
   - Check absolute paths outside workspace
   - Return validated absolute path or raise `CliError`

2. **view_file(path: str, workspace_root: str) -> None**:
   - Validate path
   - Read file contents
   - Display with simple pager:
     - Print line numbers
     - Paginate if > terminal height
     - Support basic navigation (space for next page, q to quit)

3. **edit_buffer(initial_text: str) -> str**:
   - Display current text with line numbers
   - Prompt for multi-line input
   - Accept input until blank line or EOF
   - Return edited text

4. **compute_diff(file_path: str, artifact_content: str) -> str**:
   - Read current file contents
   - Use difflib.unified_diff to generate diff
   - Return formatted diff string

5. **apply_patch_safe(file_path: str, patch_content: str, workspace_root: str) -> None**:
   - Validate path
   - Parse patch format
   - Create backup of original file
   - Apply patch
   - Verify result
   - Rollback on error

### Step 9: Implement Main REPL Loop

File: `src/agent_engine/cli/repl.py`

Define:
- `REPL` class with methods:
  - `__init__(engine: Engine, config_dir: str, profile_id: Optional[str] = None)`
    - Load profiles from config_dir
    - Select initial profile (specified or default)
    - Initialize session
    - Initialize context
    - Load custom commands from profile

  - `run() -> None`:
    - Main REPL loop:
      - Display prompt
      - Read user input (support readline history navigation)
      - Parse input:
        - If starts with `/`: execute command
        - Otherwise: treat as Engine.run() input
      - Handle command execution:
        - Look up command in registry
        - Call command function with context and args
        - Catch `CliError`/`CommandError` and display
        - Surface telemetry if enabled
      - Record in session history
      - Persist session if enabled
      - Loop until quit command

  - `_execute_command(command: str, args: str) -> None`:
    - Retrieve command function from registry
    - Call with context
    - Handle exceptions
    - Display results

  - `_execute_engine_input(user_input: str) -> None`:
    - Apply input mappings from profile
    - Build Engine.run() payload:
      - Include user_input
      - Attach files if `attach_files_as_context` is True
      - Include profile_id/session_id if configured
    - Call `ctx.run_engine(payload)`
    - Display result based on presentation_rules
    - Display telemetry based on telemetry_overlays

  - `_load_custom_commands(profile: Profile) -> None`:
    - For each custom command in profile.custom_commands:
      - Dynamically import entrypoint module
      - Register function with command registry
      - Handle import errors gracefully

  - `_display_telemetry(events: List[Event], level: str) -> None`:
    - Filter events based on level ("summary" or "verbose")
    - Format and print events
    - For summary: show only task/error events
    - For verbose: show all events with details

### Step 10: Integration with Engine

Modifications to `src/agent_engine/engine.py`:

Add method:
- `create_repl(config_dir: str, profile_id: Optional[str] = None) -> REPL`:
  - Import REPL class
  - Instantiate with self and config_dir
  - Return REPL instance

This allows: `engine.create_repl().run()`

### Step 11: Tests

File: `tests/test_phase18_cli.py`

Implement comprehensive test suite (minimum 40 tests):

**Profile Loading Tests (5 tests)**:
- Load valid cli_profiles.yaml
- Handle missing file (use default profile)
- Validate required fields
- Parse optional fields correctly
- Handle malformed YAML

**Session Management Tests (8 tests)**:
- Create session with ID
- Add entries to history
- Retrieve history
- Get last user prompt
- Attach files to session
- Persist session to disk (JSONL format)
- Load session from disk
- Honor max_history_items limit

**Command Registry Tests (5 tests)**:
- Register command via decorator
- Register with aliases
- Retrieve registered command
- List all commands
- Get help for command

**Built-in Commands Tests (12 tests)**:
- /help with no args
- /help with command arg
- /mode show current
- /mode switch profile
- /attach single file
- /attach multiple files
- /history display
- /retry execution
- /edit-last workflow
- /open file viewer
- /quit exits cleanly
- Command error handling

**File Operations Tests (6 tests)**:
- validate_path success
- validate_path reject outside workspace
- validate_path reject traversal
- view_file displays content
- compute_diff generates diff
- apply_patch_safe with confirmation

**CliContext Tests (4 tests)**:
- run_engine records history
- attach_file validates path
- get_telemetry returns events
- switch_profile changes active profile

**Telemetry Display Tests (3 tests)**:
- Summary level shows task events only
- Verbose level shows all events
- Telemetry disabled shows nothing

**Exception Tests (3 tests)**:
- CliError raised and caught
- CommandError with command details
- Exceptions are JSON-serializable

**Integration Tests (5 tests)**:
- REPL initialization
- Execute user input calls Engine.run()
- Execute command calls command function
- Session persistence end-to-end
- Custom command loading from profile

**Edge Cases Tests (4 tests)**:
- Empty input handling
- Unknown command error
- Invalid profile switch
- Malformed command args

### Step 12: Documentation

Create or update:

1. **docs/CLI_FRAMEWORK.md**:
   - Overview of CLI architecture
   - Built-in commands reference
   - How to create custom commands
   - Profile configuration guide
   - Session management details
   - File operations guide
   - Extension API examples

2. **examples/minimal_config/cli_profiles.yaml**:
   - Example profile configuration
   - Comments explaining each field
   - Multiple profile examples (default, advanced)

3. **Update README.md**:
   - Add CLI Framework section
   - Quick start with REPL
   - Link to detailed CLI documentation

---

## SECTION 4 — Acceptance Criteria

### 4.1 Core REPL Functionality

✅ REPL starts successfully with `Engine.create_repl().run()`

✅ REPL loads profiles from cli_profiles.yaml

✅ REPL uses default profile when no config file exists

✅ REPL supports multi-turn conversations with persistent state

✅ User input (non-command) calls Engine.run() with correct payload

✅ Session history records all turns with timestamps and metadata

✅ Readline-style history navigation works (up/down arrows)

### 4.2 Built-in Commands

✅ All 10 built-in commands implemented and functional

✅ `/help` lists all commands (built-in + custom)

✅ `/help <command>` shows detailed help

✅ `/mode` displays current profile

✅ `/mode <profile_id>` switches profiles

✅ `/attach` validates and adds files to session

✅ `/history` displays recent session entries

✅ `/retry` re-runs last Engine.run()

✅ `/edit-last` allows editing and re-running last prompt

✅ `/open` displays file contents in terminal viewer

✅ `/diff` and `/apply_patch` work with artifacts

✅ `/quit` exits cleanly with optional persistence

### 4.3 Profile System

✅ cli_profiles.yaml schema matches Section 2.2

✅ Profiles support all optional fields with correct defaults

✅ Custom commands loaded from profile entrypoints

✅ Input mappings applied to Engine.run() payload

✅ Presentation rules control output display

✅ Telemetry overlays control event display

✅ Session policies control persistence behavior

### 4.4 Command Extension

✅ `@register_command` decorator works

✅ Custom commands registered from profiles

✅ CliContext provides all required fields and methods

✅ Custom commands can call Engine.run() via context

✅ Command errors handled with CommandError exception

### 4.5 File Operations

✅ All file paths validated against workspace root

✅ Paths outside workspace rejected

✅ Path traversal (`..`) rejected

✅ File viewer displays plain text with line numbers

✅ Simple edit buffer accepts multi-line input

✅ Diff generation works with unified diff format

✅ Patch application requires confirmation

### 4.6 Session Management

✅ Session state persists to JSONL when enabled

✅ Session loads from disk on restart

✅ History respects max_history_items limit

✅ Attached files tracked across turns

✅ Last prompt retrievable for /edit-last

### 4.7 Telemetry Integration

✅ Telemetry events displayed inline during Engine.run()

✅ Summary mode shows task/error events only

✅ Verbose mode shows all events

✅ Telemetry can be disabled via profile

✅ Events sourced from Phase 8 TelemetryBus

### 4.8 Error Handling

✅ CliError and CommandError exceptions defined

✅ Exceptions are JSON-serializable

✅ Command errors display helpful messages

✅ Unknown commands show error with suggestion

✅ Invalid arguments handled gracefully

### 4.9 Testing

✅ Minimum 40 comprehensive tests implemented

✅ All test categories covered (profile, session, commands, file ops, context, telemetry, exceptions, integration, edge cases)

✅ All tests passing

✅ No regressions in existing tests (917+ tests still passing)

### 4.10 Documentation

✅ CLI_FRAMEWORK.md created with complete reference

✅ Example cli_profiles.yaml in examples/minimal_config/

✅ README.md updated with CLI section

✅ Custom command extension documented with examples

---

## SECTION 5 — Clarifying Questions

**None.** All required information has been provided in the user's clarifications.
