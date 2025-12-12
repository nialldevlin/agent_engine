# Agent Engine Project Template

This is a canonical project structure for Agent Engine - a configuration-first orchestration framework for LLM-powered agent workflows.

## Project Structure

```
.
├── config/                          # Configuration directory
│   ├── workflow.yaml                # DAG workflow definition
│   ├── agents.yaml                  # Agent definitions
│   ├── tools.yaml                   # Tool definitions
│   ├── memory.yaml                  # Memory configuration
│   ├── plugins.yaml                 # Plugin configuration
│   ├── scheduler.yaml               # Scheduler configuration
│   ├── provider_credentials.yaml    # Credentials (generated from template)
│   └── schemas/                     # Custom data schemas
├── scripts/                         # Helper scripts
│   ├── bootstrap.sh                 # Initialization script
│   └── healthcheck.py               # Health check script
├── docs/                            # Documentation
│   ├── README.md                    # Project documentation
│   ├── SETUP.md                     # Setup instructions
│   └── API.md                       # API documentation
├── tests/                           # Test suite
├── .env                             # Environment variables (local)
├── .env.template                    # Environment template
├── pyproject.toml                   # Project metadata
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
└── README.md                        # This file
```

## Quick Start

### 1. Setup Environment

```bash
# Clone or copy this template
cp -r templates/project_template my-agent-project
cd my-agent-project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.template .env

# Edit configuration
vim .env
vim config/provider_credentials.yaml
```

### 2. Verify Configuration

```bash
# Run health check
python scripts/healthcheck.py

# Validate manifests
python -c "
from agent_engine import Engine
engine = Engine.from_config_dir('config')
print('Configuration loaded successfully')
print(f'Nodes: {len(engine.dag.nodes)}')
print(f'Edges: {len(engine.dag.edges)}')
"
```

### 3. Run Workflow

```python
from agent_engine import Engine

# Load engine
engine = Engine.from_config_dir("config")

# Execute workflow
result = engine.run({
    "request": "your_workflow_request"
})

print(result)
```

## Configuration Files

### workflow.yaml

Defines the DAG structure:
- Nodes: deterministic, agent, or custom types
- Edges: connections between nodes
- Context: data flow between tasks

Example:
```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true

  - id: "analyze"
    kind: "agent"
    role: "linear"
    context: "global"
    tools: ["text_analyzer"]

edges:
  - from: "start"
    to: "analyze"
```

### agents.yaml

Defines LLM agents:
- Agent ID and type
- LLM model selection
- Configuration parameters
- System prompts

Example:
```yaml
agents:
  - id: "default_agent"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config:
      temperature: 0.7
      max_tokens: 2048
```

### tools.yaml

Defines tools agents can use:
- File system tools
- API tools
- Custom tools
- Tool permissions and limits

Example:
```yaml
tools:
  - id: "read_file"
    type: "filesystem"
    entrypoint: "agent_engine.tools.filesystem:read_file"
    permissions:
      allow_network: false
      allow_shell: false
```

### memory.yaml

Configures memory backends:
- In-memory storage
- Redis caching
- Database persistence
- Context isolation

### plugins.yaml

Enables optional plugins:
- Telemetry collection
- Logging
- Caching
- Monitoring
- Custom plugins

### scheduler.yaml

Configures task execution:
- Parallelism settings
- Retry policies
- Resource allocation
- Load balancing

## Environment Setup

### Using .env File

```bash
# Copy template
cp .env.template .env

# Edit with your configuration
vim .env

# Verify loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('ANTHROPIC_API_KEY')[:10])"
```

### Credential Management

```bash
# Copy credential template
cp config/provider_credentials.yaml.template config/provider_credentials.yaml

# Edit with actual credentials
vim config/provider_credentials.yaml

# Never commit this file
echo "config/provider_credentials.yaml" >> .gitignore
```

## Testing

```bash
# Run test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src

# Run specific test
pytest tests/test_workflow.py::test_basic_flow
```

## Deployment

### Docker

```bash
# Build image
docker build -f docker/Dockerfile -t agent-engine .

# Run container
docker run -v $(pwd)/config:/app/config agent-engine
```

### Kubernetes

```bash
# Apply configuration
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods -n agent-engine
kubectl logs -n agent-engine -l app=agent-engine
```

### Systemd

```bash
# Copy service file
sudo cp systemd/agent-engine.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable agent-engine
sudo systemctl start agent-engine

# Check status
sudo systemctl status agent-engine
```

## Development

### Installing from Source

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Code quality
ruff check src/
mypy src/
```

### Code Style

This project uses:
- **Ruff**: Code linting and formatting
- **MyPy**: Type checking
- **Pytest**: Testing framework

Run checks:
```bash
ruff check src/
ruff format src/
mypy src/
pytest tests/
```

## Monitoring and Observability

### Health Checks

```bash
# Run health check
python scripts/healthcheck.py

# Output:
# {
#   "status": "healthy",
#   "timestamp": "2025-01-01T00:00:00Z",
#   "checks": {...}
# }
```

### Logging

Configure logging in `.env`:
```
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_DIR=logs
```

View logs:
```bash
tail -f logs/engine.log
```

### Metrics

Metrics available at `/metrics` endpoint:
```bash
curl http://localhost:8000/metrics
```

## Customization

### Adding Custom Tools

Create tool file:
```python
# project/tools/custom.py
def my_tool(input: str) -> str:
    """Custom tool implementation."""
    return f"Processed: {input}"
```

Register in `config/tools.yaml`:
```yaml
- id: "my_tool"
  type: "custom"
  entrypoint: "project.tools.custom:my_tool"
```

### Adding Custom Agents

Define in `config/agents.yaml`:
```yaml
- id: "custom_agent"
  kind: "agent"
  llm: "anthropic/claude-3-5-sonnet"
  config:
    system_prompt: "Custom system prompt..."
```

### Adding Custom Plugins

Implement plugin interface:
```python
# project/plugins/custom.py
class CustomPlugin:
    def on_workflow_start(self, workflow): pass
    def on_node_execute(self, node): pass
    def on_workflow_end(self, result): pass
```

Register in `config/plugins.yaml`:
```yaml
- id: "custom_plugin"
  type: "custom"
  entrypoint: "project.plugins.custom:CustomPlugin"
```

## Troubleshooting

### Configuration Load Failures

```bash
# Validate YAML syntax
python -c "
import yaml
for f in ['workflow.yaml', 'agents.yaml', 'tools.yaml']:
    with open(f'config/{f}') as file:
        yaml.safe_load(file)
    print(f'{f}: OK')
"
```

### Import Errors

```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Add to path if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Missing Dependencies

```bash
# Reinstall requirements
pip install -r requirements.txt

# Check versions
pip show agent-engine
```

## Next Steps

1. Customize `config/workflow.yaml` for your use case
2. Define agents in `config/agents.yaml`
3. Implement custom tools
4. Add test cases
5. Configure deployment method
6. Set up monitoring and logging
7. Implement CI/CD pipeline

## Documentation

- `docs/README.md` - Project documentation
- `docs/SETUP.md` - Detailed setup instructions
- `docs/API.md` - API documentation
- Main repo: [Agent Engine](https://github.com/example/agent-engine)

## License

See LICENSE file for details.

## Support

For issues and questions:
1. Check troubleshooting section
2. Review Agent Engine documentation
3. Open issue on GitHub repository

## Additional Resources

- Agent Engine Overview: See main repository README
- Deployment Guide: `docs/DEPLOYMENT.md` in main repo
- Packaging Guide: `docs/PACKAGING.md` in main repo
- Template Examples: `templates/` in main repo
