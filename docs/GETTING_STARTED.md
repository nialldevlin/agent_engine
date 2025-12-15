# Getting Started with Agent Engine

A practical guide to setting up and developing your first agent engine project.

## Table of Contents
1. [Quick Setup (5 minutes)](#quick-setup-5-minutes)
2. [API Key Configuration](#api-key-configuration)
3. [Defining Agents & Models](#defining-agents--models)
4. [Understanding Data Flow](#understanding-data-flow)
5. [Your First Workflow](#your-first-workflow)
6. [Troubleshooting](#troubleshooting)

---

## Quick Setup (5 minutes)

### Create Project Structure

```bash
mkdir my_agent_project
cd my_agent_project
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install agent-engine
```

### Create Minimal Configuration

Create `config/` directory:

```bash
mkdir config
```

Create `config/workflow.yaml`:
```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"

  - id: "analyze"
    kind: "agent"
    role: "linear"
    context: "global"
    agent_id: "default"

  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"

edges:
  - from: "start"
    to: "analyze"
  - from: "analyze"
    to: "exit"
```

Create `config/agents.yaml`:
```yaml
agents:
  - id: "default"
    kind: "agent"
    llm: "anthropic/claude-3-5-haiku"
    config: {}
```

Create `config/tools.yaml`:
```yaml
tools: []
```

Create `config/provider_credentials.yaml`:
```yaml
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"
```

### Create Entry Point

Create `run.py`:
```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")
result = engine.run({"request": "Hello, who are you?"})
print(result)
```

### Run It

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python run.py
```

Done! You now have a working agent engine project.

---

## API Key Configuration

### Overview

Agent Engine loads API keys via `provider_credentials.yaml`, a configuration file that specifies where credentials come from. This allows flexible credential management without hardcoding secrets.

### Setup (3 methods)

#### Method 1: Environment Variables (Recommended)

**Simplest approach. Credentials live in shell environment.**

1. Create `config/provider_credentials.yaml`:

```yaml
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"
```

2. Set the environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-v7V..."
```

3. Verify it's set:

```bash
echo $ANTHROPIC_API_KEY  # Should print your key
```

**Best for:**
- Local development
- CI/CD pipelines (secrets injected at runtime)
- Docker containers (passed via --env flag)

#### Method 2: Plain Text Files

**Store credentials in a file on disk.**

1. Create a secure directory:

```bash
mkdir -p /etc/agent-engine/secrets
chmod 700 /etc/agent-engine/secrets
```

2. Create credential file:

```bash
echo "sk-ant-v7V..." > /etc/agent-engine/secrets/anthropic.txt
chmod 600 /etc/agent-engine/secrets/anthropic.txt
```

3. Configure in `provider_credentials.yaml`:

```yaml
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "file"
      file_path: "/etc/agent-engine/secrets/anthropic.txt"
```

**Best for:**
- Production deployments
- Systemd services
- Docker containers with secret volumes

#### Method 3: Structured Files (JSON/YAML)

**Extract credentials from larger configuration files.**

1. Create config file:

```json
// secrets.json
{
  "providers": {
    "anthropic": {
      "api_key": "sk-ant-v7V..."
    }
  }
}
```

2. Configure with key extraction:

```yaml
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "file"
      file_path: "/path/to/secrets.json"
      file_key: "providers.anthropic.api_key"
```

**Best for:**
- Multiple credentials in one file
- Secrets managed by a secrets manager

### Multiple Providers

Configure multiple LLM providers:

```yaml
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"

  - id: "openai"
    provider: "openai"
    auth:
      type: "api_key"
      source: "env"
      env_var: "OPENAI_API_KEY"

  - id: "ollama"
    provider: "ollama"
    auth:
      type: "api_key"
      source: "env"
      env_var: "OLLAMA_API_KEY"
```

### Security Checklist

- [ ] **Never commit `provider_credentials.yaml` with real keys** - Use `.gitignore`
- [ ] **Never hardcode keys in code** - Always load from environment or files
- [ ] **File permissions** - Use `chmod 600` for credential files
- [ ] **Access control** - Only the app user should read credential files
- [ ] **Rotation** - Plan to rotate keys periodically

See [SECURITY.md](./SECURITY.md) for detailed security practices.

---

## Defining Agents & Models

### Agents Overview

An **agent** is an LLM-powered component that can think, reason, and call tools. You define agents in `config/agents.yaml`, then reference them in your workflow.

### Format: agents.yaml

```yaml
version: "1.0"
agents:
  - id: "analyzer"           # Unique identifier
    kind: "agent"            # Always "agent" for LLM agents
    llm: "anthropic/claude-3-5-haiku"  # provider/model-name
    config:
      temperature: 0.7       # Creativity (0-1, default 0.7)
      max_tokens: 2000       # Max response length
```

### Supported Models

**Anthropic:**
- `anthropic/claude-3-5-haiku` - Fast, cheap, good for simple tasks
- `anthropic/claude-3-5-sonnet` - Balanced, best for most tasks
- `anthropic/claude-opus-4-5` - Smartest, best for complex reasoning

**OpenAI:**
- `openai/gpt-4` - (extensible, requires OPENAI_API_KEY)

**Local/Self-Hosted:**
- `ollama/llama2` - Run locally without API keys

### Model Format

Format: `provider/model-name`

```yaml
llm: "anthropic/claude-3-5-haiku"
#    ^^^^^^^^^^^ provider (must match credential id provider)
#                ^^^^^^^^^^^^^^^^^^^ model name (without version suffix)
```

### Configuration Options

```yaml
agents:
  - id: "fast_agent"
    kind: "agent"
    llm: "anthropic/claude-3-5-haiku"
    config:
      temperature: 0.3      # Conservative (closer to 0)
      max_tokens: 512       # Shorter responses

  - id: "creative_agent"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config:
      temperature: 1.0      # Creative (closer to 1)
      max_tokens: 4000      # Longer responses

  - id: "local_agent"
    kind: "agent"
    llm: "ollama/llama2"
    config:
      base_url: "http://localhost:11434/api/generate"
```

### Using Agents in Workflow

Reference agents in `config/workflow.yaml`:

```yaml
nodes:
  - id: "analyze"
    kind: "agent"           # Node type is AGENT
    agent_id: "analyzer"    # References agents.yaml id
    tools: ["search_codebase"]
    context: "global"
```

### Common Issues

**Q: Model not recognized?**
- Check format: `provider/model-name` (not `model-name` alone)
- Verify credential provider matches (e.g., anthropic credentials for anthropic models)

**Q: Temperature vs max_tokens?**
- `temperature` (0-1): How creative/random the response is
  - 0.0: Always same response (deterministic)
  - 0.7: Balanced (default)
  - 1.0: Very creative/random
- `max_tokens`: Maximum length of response in tokens
  - Longer responses need more tokens
  - Truncated if max_tokens reached

---

## Understanding Data Flow

### Overview

Data flows through your workflow as tasks move from node to node. Each node receives input, processes it, and produces output. The next node receives the previous node's output as input.

### Simple Linear Flow

```yaml
nodes:
  - id: "search"      # Step 1
    kind: "agent"
    tools: ["search_codebase"]

  - id: "summarize"   # Step 2 (receives search output)
    kind: "agent"
    tools: ["format_response"]

edges:
  - from: "search"
    to: "summarize"
```

**Data flow:**
1. `search` runs, calls tool → produces `{result: "code found", tool_calls: [...]}`
2. `summarize` receives that output as input → can reference search results

### Context & Memory Tiers

Agent Engine has three memory tiers:

| Tier | Scope | Persistence | Use Case |
|------|-------|-------------|----------|
| **Task** | Single workflow run | Cleared when task ends | Temporary data within one execution |
| **Project** | Whole project | Persists across runs | Shared project state |
| **Global** | Entire system | Persists across projects | System-wide knowledge |

### Specifying Context Access

Each node specifies which memory tiers it can see:

```yaml
nodes:
  - id: "search"
    kind: "agent"
    context: "none"     # Can't see any memory

  - id: "analyze"
    kind: "agent"
    context: "global"   # Can see task + project + global memory
```

### Tool Outputs & Context

Tools produce outputs that are automatically captured:

```yaml
nodes:
  - id: "search"
    kind: "agent"
    tools: ["search_codebase"]  # Tool executes, output captured
    context: "global"
```

Tool output becomes part of the node's output:
```json
{
  "result": "Found 5 matching files",
  "tool_calls": [
    {
      "call_id": "call-123",
      "tool_id": "search_codebase",
      "inputs": {"query": "authentication"},
      "output": ["auth.py", "login.py", ...]
    }
  ]
}
```

The next node receives this output and can see the tool results in its context.

### Multi-Step Workflow Example

```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    context: "none"

  - id: "search_codebase"      # Step 1: Search for code
    kind: "agent"
    role: "linear"
    agent_id: "analyzer"
    tools: ["search_codebase"]
    context: "global"

  - id: "read_files"           # Step 2: Read found files
    kind: "agent"
    role: "linear"
    agent_id: "analyzer"
    tools: ["read_file"]
    context: "global"           # Can see search results

  - id: "generate_summary"     # Step 3: Summarize findings
    kind: "agent"
    role: "linear"
    agent_id: "summarizer"
    tools: []
    context: "global"           # Can see all previous outputs

  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"

edges:
  - from: "start"
    to: "search_codebase"
  - from: "search_codebase"
    to: "read_files"
  - from: "read_files"
    to: "generate_summary"
  - from: "generate_summary"
    to: "exit"
```

**Data flow:**
1. `search_codebase` finds files → output: `["auth.py", "login.py"]`
2. `read_files` receives that list → reads each file → output: `{files: {auth.py: "...", ...}}`
3. `generate_summary` receives file contents → creates summary → output: `"Auth system allows...""`
4. `exit` receives summary → workflow ends

### Decision Nodes

Route to different paths based on output:

```yaml
nodes:
  - id: "decide"
    kind: "agent"
    role: "decision"  # Can route based on output
    agent_id: "classifier"

edges:
  - from: "decide"
    to: "create"
    label: "is_new"           # Route if output contains "is_new"
  - from: "decide"
    to: "update"
    label: "is_existing"      # Route if output contains "is_existing"
```

See [DATA_FLOW.md](./DATA_FLOW.md) for detailed diagrams and examples.

---

## Your First Workflow

### Build a Code Analyzer

Let's build a workflow that analyzes a codebase:

**Project structure:**
```
code_analyzer/
├── config/
│   ├── workflow.yaml
│   ├── agents.yaml
│   ├── tools.yaml
│   └── provider_credentials.yaml
└── run.py
```

**config/provider_credentials.yaml:**
```yaml
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"
```

**config/agents.yaml:**
```yaml
agents:
  - id: "analyzer"
    kind: "agent"
    llm: "anthropic/claude-3-5-haiku"
    config:
      temperature: 0.3
      max_tokens: 2000
```

**config/tools.yaml:**
```yaml
tools:
  - id: "read_file"
    type: "filesystem"
    entrypoint: "agent_engine.tools.filesystem:read_file"
    permissions:
      allow_shell: false
      allow_network: false
```

**config/workflow.yaml:**
```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"

  - id: "analyze"
    kind: "agent"
    role: "linear"
    agent_id: "analyzer"
    tools: ["read_file"]
    context: "global"

  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"

edges:
  - from: "start"
    to: "analyze"
  - from: "analyze"
    to: "exit"
```

**run.py:**
```python
from agent_engine import Engine

# Load engine from config
engine = Engine.from_config_dir("config")

# Run analysis
result = engine.run({
    "request": "Analyze the authentication system in this codebase"
})

print("Result:", result)
```

**Run it:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python run.py
```

---

## Troubleshooting

### LLM Call Fails Silently

**Check these in order:**

1. **API key set?**
   ```bash
   echo $ANTHROPIC_API_KEY  # Should print your key, not empty
   ```

2. **provider_credentials.yaml exists?**
   ```bash
   ls -la config/provider_credentials.yaml
   ```

3. **Credential format correct?**
   ```yaml
   provider_credentials:
     - id: "anthropic"  # Must match provider name
       provider: "anthropic"
       auth:
         type: "api_key"
         source: "env"
         env_var: "ANTHROPIC_API_KEY"
   ```

4. **Agent ID matches workflow?**
   - agents.yaml: `id: "analyzer"`
   - workflow.yaml: `agent_id: "analyzer"` (must match)

5. **Model format correct?**
   - ✅ `anthropic/claude-3-5-haiku`
   - ❌ `claude-3-5-haiku` (missing provider)
   - ❌ `anthropic/claude-3.5-haiku` (wrong format)

### Memory/Data Not Flowing Between Steps

**Check context configuration:**

```yaml
nodes:
  - id: "step1"
    context: "global"  # Needed to see memory

  - id: "step2"
    context: "global"  # Needed to see step1 output
```

**If context is "none"**, the node can't see previous data.

### Tool Not Found

**Error:** "Tool 'search_codebase' not found"

**Solutions:**
1. Check tools.yaml has the tool defined
2. Check workflow.yaml references the tool id correctly
3. Verify entrypoint is a real function

### Workflow DAG Invalid

**Error:** "DAG validation failed"

**Check:**
- All `from` and `to` node IDs exist
- No circular references
- At least one START node marked `default_start: true`
- At least one EXIT node

---

## Next Steps

- Read [ARCHITECTURE.md](./ARCHITECTURE.md) - Understanding DAGs, roles, nodes
- Read [DATA_FLOW.md](./DATA_FLOW.md) - Deep dive into context and memory
- Read [API_REFERENCE.md](./API_REFERENCE.md) - Full API documentation
- Read [SECURITY.md](./SECURITY.md) - Production security practices
- Explore [examples/mini_editor/](../examples/mini_editor/) - Full working example

---

## FAQ

**Q: Can I use OpenAI models?**
A: Yes, set up OPENAI_API_KEY and use `openai/gpt-4`.

**Q: How do I store data between workflow runs?**
A: Use Project or Global memory stores. See DATA_FLOW.md.

**Q: Can tools call other tools?**
A: Not directly. Tools are leaf operations. Use multiple nodes to chain operations.

**Q: Can I run locally without API keys?**
A: Yes, use `ollama/llama2` with a local Ollama instance.
