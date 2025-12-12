# Mini-Editor Example Application

The Mini-Editor is a complete example of Agent Engine integration, demonstrating:

- **DAG-based Workflows**: Document creation and editing flows
- **Agent Nodes**: LLM-driven content generation
- **Memory Stores**: Context management for documents
- **CLI Framework**: Interactive REPL with custom commands
- **Profile System**: Configuration-driven behavior

## Quick Start

### Prerequisites

```bash
# Install Agent Engine
pip install -e ../..
```

### Run Interactive Session

```bash
# Start the interactive REPL
python run_mini_editor.py interactive

# Or just run with no arguments
python run_mini_editor.py
```

### Run Programmatic Example

```bash
# Execute a document creation example
python run_mini_editor.py example
```

## Architecture

### Workflow Structure

The mini-editor uses a decision-based workflow:

```
START → normalize_request → decide_operation → [create|edit] → summarize → EXIT
```

**Nodes:**

- `start` - Initialization (START role)
- `normalize_request` - Input validation (LINEAR deterministic)
- `decide_operation` - Route based on action (DECISION agent)
- `draft_document` - Create new document (LINEAR agent)
- `edit_document` - Edit existing document (LINEAR agent)
- `generate_summary` - Create summary (LINEAR agent)
- `exit` - Final output (EXIT role)

### Configuration Files

```
config/
├── workflow.yaml           # DAG definition with 7 nodes
├── agents.yaml            # Claude 3.5 Sonnet agent
├── tools.yaml             # File read/write tools
├── memory.yaml            # Memory stores and profiles
├── cli_profiles.yaml      # CLI behavior and custom commands
└── schemas/
    └── document.json      # Document validation schema
```

### CLI Commands

**Built-in Commands:**
- `/help` - Show command help
- `/attach <file>` - Attach file to session
- `/history` - View session history
- `/open <file>` - View file contents
- `/diff` - Compare artifacts with files
- `/quit` - Exit REPL

**Custom Commands:**
- `/create <title>` - Create a new document
- `/edit <path>` - Edit existing document
- `/summary <path>` - Show document summary

## Example Usage

### Creating a Document

```bash
[default]> /create "My Project Plan"

[Document Created]
Title: My Project Plan
Status: success
```

### Editing a Document

```bash
[default]> /edit /tmp/project_plan.md

Please provide feedback to improve the document...
> Add more detail to the timeline section

[Document Edited]
Path: /tmp/project_plan.md
Status: success
```

### Viewing Summary

```bash
[default]> /summary /tmp/project_plan.md

[Document Summary]
Path: /tmp/project_plan.md
Executive Summary:
- Project scope and objectives
- Timeline with key milestones
- Resource requirements
...
```

## Memory Management

The mini-editor uses three memory stores:

1. **Task Store** - Per-document context (document history)
2. **Project Store** - Shared across documents in session
3. **Global Store** - Cross-session knowledge (style guides)

**Context Profiles:**

- `default` - 4000 tokens, recency-based retrieval
- `compact` - 2000 tokens for quick operations

## Implementation Details

### Workflow Execution

When a user runs `/create "Title"`:

1. **Engine.run()** is called with action="create"
2. **Normalize** node validates input
3. **Decide** node routes to draft_document (because action="create")
4. **Draft** node uses Claude to create document
5. **Summary** node generates overview
6. **Exit** node returns final output
7. Events emitted at each step for observability

### Session Persistence

Session history persists to:
```
~/.agent_engine/mini_editor/history.jsonl
```

Each entry includes:
- User input
- Command executed
- Engine run metadata
- Attached files
- Timestamp

### Custom Command Integration

Custom commands are defined in `cli_commands.py`:

```python
def create_document(ctx: CliContext, args: str) -> None:
    """Create a new document."""
    result = ctx.run_engine({
        "action": "create",
        "title": args,
        "user_input": "Create comprehensive document"
    })
```

## Testing

Run the mini-editor tests:

```bash
pytest ../../tests/test_phase23_mini_editor.py
```

## Advanced Usage

### Using Different Context Profiles

Modify `config/memory.yaml` to change retrieval policies:

```yaml
context_profiles:
  - id: "semantic"
    max_tokens: 8000
    retrieval_policy: "semantic"  # Uses embeddings
```

### Custom Document Schemas

Add schema validation in `config/schemas/document.json`:

```json
{
  "properties": {
    "custom_field": {"type": "string"}
  }
}
```

### Adding New Agents

Define new agents in `config/agents.yaml`:

```yaml
agents:
  - id: "claude_opus"
    kind: "agent"
    llm: "anthropic/claude-opus-4"
    config:
      temperature: 0.8
```

## See Also

- [Agent Engine Documentation](../../docs/ARCHITECTURE.md)
- [CLI Framework Guide](../../docs/CLI_FRAMEWORK.md)
- [Tutorial](../../docs/TUTORIAL.md)
- [API Reference](../../docs/API_REFERENCE.md)
