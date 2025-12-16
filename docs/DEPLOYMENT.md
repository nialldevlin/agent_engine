# Deployment Guide

This document provides guidance for deploying and managing Agent Engine in production environments. It covers repository layout, environment setup, configuration, secret management, and operational monitoring.

## Table of Contents

1. [Recommended Repository Layout](#recommended-repository-layout)
2. [Manifest Versioning Strategy](#manifest-versioning-strategy)
3. [Environment Setup Instructions](#environment-setup-instructions)
4. [Dependency Management](#dependency-management)
5. [Configuration Management](#configuration-management)
6. [Secret Management](#secret-management)
7. [Health Checks and Monitoring](#health-checks-and-monitoring)
8. [Deployment Methods](#deployment-methods)
9. [Best Practices](#best-practices)

---

## Recommended Repository Layout

Agent Engine projects should follow a canonical directory structure for consistency and clarity:

```
my-agent-project/
├── config/                          # All configuration files
│   ├── workflow.yaml                # DAG workflow definition (required)
│   ├── agents.yaml                  # Agent definitions (required)
│   ├── tools.yaml                   # Tool definitions (required)
│   ├── memory.yaml                  # Memory store configuration (optional)
│   ├── plugins.yaml                 # Plugin configuration (optional)
│   ├── scheduler.yaml               # Task scheduler configuration (optional)
│   ├── cli_profiles.yaml            # CLI execution profiles (optional)
│   ├── provider_credentials.yaml    # Provider API credentials (DO NOT commit)
│   ├── provider_credentials.yaml.template  # Template for credentials
│   ├── policies.yaml                # Security policies (optional)
│   ├── metrics.yaml                 # Metrics configuration (optional)
│   └── schemas/                     # Custom data schemas (optional)
│       ├── schema1.yaml
│       └── schema2.yaml
├── .env                             # Environment variables (DO NOT commit)
├── .env.template                    # Environment variable template
├── .env.production                  # Production-specific variables
├── .env.staging                     # Staging-specific variables
├── scripts/                         # Helper scripts
│   ├── bootstrap.sh                 # Initialization and setup script
│   ├── healthcheck.py               # Health check endpoint
│   ├── deploy.sh                    # Deployment script
│   └── cleanup.sh                   # Cleanup and teardown script
├── docker/                          # Docker deployment files
│   ├── Dockerfile                   # Container image definition
│   ├── docker-compose.yml           # Multi-service orchestration
│   └── .dockerignore                # Docker build excludes
├── k8s/                             # Kubernetes deployment files
│   ├── deployment.yaml              # K8s deployment manifest
│   ├── configmap.yaml               # Configuration management
│   ├── secret.yaml                  # Secret management
│   └── service.yaml                 # Service exposure
├── systemd/                         # Systemd service files
│   ├── agent-engine.service         # Systemd service unit
│   └── agent-engine.environment     # Service environment variables
├── docs/                            # Project documentation
│   ├── README.md                    # Project overview
│   ├── SETUP.md                     # Setup instructions
│   ├── DEPLOYMENT.md                # Deployment guide
│   └── API.md                       # API documentation (if applicable)
├── tests/                           # Test suite
│   ├── unit/                        # Unit tests
│   ├── integration/                 # Integration tests
│   └── e2e/                         # End-to-end tests
├── logs/                            # Runtime logs (gitignored)
├── data/                            # Runtime data/state (gitignored)
├── artifacts/                       # Generated artifacts (gitignored)
├── pyproject.toml                   # Project metadata and dependencies
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── setup.py                         # Setup configuration (optional)
├── README.md                        # Project README
├── LICENSE                          # License file
└── .gitignore                       # Git ignore rules
```

### Key Directory Patterns

- **config/**: All declarative configuration (manifests, schemas, credentials)
- **scripts/**: Operational scripts for deployment, health checks, cleanup
- **docker/**: Container-based deployment templates
- **k8s/**: Kubernetes-native deployment manifests
- **systemd/**: Linux systemd service management
- **tests/**: Organized test suites by testing scope
- **docs/**: Complete documentation with deployment guides

### Gitignore Best Practices

Never commit sensitive files:

```gitignore
# Credentials and secrets
config/provider_credentials.yaml
.env
.env.production
.env.staging
*.secret
*.pem
*.key

# Runtime data
logs/
data/
artifacts/
*.db
*.sqlite

# Cache and build artifacts
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
build/
dist/
*.egg-info/

# IDE and OS files
.vscode/
.idea/
*.swp
.DS_Store
```

---

## Manifest Versioning Strategy

Agent Engine manifests should follow semantic versioning to track configuration changes:

### Version Format

Use `MAJOR.MINOR.PATCH` format in manifest headers:

```yaml
# workflow.yaml
version: "1.0.0"
description: "Production workflow v1.0.0"
nodes:
  - id: "start"
    kind: "deterministic"
    # ...
```

### Version Management Practices

1. **Major**: Incompatible schema changes, breaking modifications to DAG structure
2. **Minor**: New features, new nodes/edges, backward-compatible additions
3. **Patch**: Bug fixes, optimizations, non-breaking improvements

### Manifest Hash Tracking

Agent Engine records SHA256 hashes of all manifest files at load time. Use these hashes for:

- Verifying configuration consistency across deployments
- Detecting unexpected configuration drift
- Auditing configuration changes
- Correlating execution issues with configuration versions

Access manifest hashes via engine metadata:

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")
metadata = engine.metadata

# Access manifest hashes
print(metadata.manifest_hashes)
# Output: {"workflow.yaml": "abc123...", "agents.yaml": "def456...", ...}
```

### Version Validation

Always validate configuration versions before deployment:

```bash
# Check workflow version
grep "^version:" config/workflow.yaml

# Verify manifest hashes
python -c "
from agent_engine import Engine
engine = Engine.from_config_dir('config')
import json
print(json.dumps(engine.metadata.manifest_hashes, indent=2))
"
```

---

## Environment Setup Instructions

### Prerequisites

- Python >= 3.10
- pip or poetry (for dependency management)
- Docker (optional, for containerized deployment)
- Docker Compose (optional, for multi-service setup)

### Installation from Source

```bash
# Clone repository
git clone <repository-url>
cd my-agent-project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install agent-engine
pip install agent-engine>=0.0.1

# Install project dependencies
pip install -r requirements.txt
```

### Installation from PyPI

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install from PyPI
pip install agent-engine>=0.0.1

# Install project-specific dependencies
pip install -r requirements.txt
```

### Configuration Initialization

```bash
# Copy environment template
cp .env.template .env

# Copy credential template
cp config/provider_credentials.yaml.template config/provider_credentials.yaml

# Edit credentials and environment variables
vim .env
vim config/provider_credentials.yaml

# Verify configuration loads correctly
python -c "
from agent_engine import Engine
engine = Engine.from_config_dir('config')
print('Configuration loaded successfully')
print(f'Engine version: {engine.metadata.engine_version}')
"
```

### Local Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests to verify setup
pytest tests/ -v

# Run linting
ruff check src/

# Format code
ruff format src/
```

---

## Dependency Management

### Production Dependencies

Use `requirements.txt` for production deployments:

```
# requirements.txt
agent-engine>=0.0.1
pydantic>=2.6
pyyaml>=6.0
# Add project-specific dependencies below
requests>=2.28
python-dotenv>=0.21
```

### Development Dependencies

Use `requirements-dev.txt` for development environments:

```
# requirements-dev.txt
-r requirements.txt
pytest>=7.4
pytest-cov>=4.1
pytest-asyncio>=0.21
ruff>=0.4
mypy>=1.9
ipython>=8.0
black>=23.0
```

### pyproject.toml Configuration

For standardized project metadata:

```toml
[build-system]
requires = ["setuptools>=69.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-agent-project"
version = "1.0.0"
description = "Production agent workflow"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Your Team" }]
dependencies = [
    "agent-engine>=0.0.1",
    "pydantic>=2.6",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-cov>=4.1",
    "ruff>=0.4",
]

[tool.setuptools]
package-dir = { "" = "src" }

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
target-version = "py310"
line-length = 100
```

### Dependency Pinning

For production stability, pin all dependency versions:

```
# requirements.txt (production)
agent-engine==0.0.1
pydantic==2.6.0
pyyaml==6.0.1
requests==2.31.0
python-dotenv==0.21.0
```

### Dependency Updates

Update dependencies safely:

```bash
# Check for outdated packages
pip list --outdated

# Update single package with tests
pip install --upgrade pydantic
pytest tests/

# For major version updates, test thoroughly
pip install 'pydantic>=3.0'
pytest tests/ -v
```

---

## Configuration Management

### Environment-Specific Configuration

Manage different configurations per environment:

```bash
# Use environment variable to select config
export AGENT_ENGINE_ENV=production
export AGENT_ENGINE_CONFIG_DIR=config

# Or use environment-specific files
AGENT_ENGINE_CONFIG_DIR=config/production python main.py
```

### Loading Configuration

```python
import os
from agent_engine import Engine

# Load from environment variable
config_dir = os.getenv("AGENT_ENGINE_CONFIG_DIR", "config")
engine = Engine.from_config_dir(config_dir)

# Or explicitly specify
engine = Engine.from_config_dir("config/production")
```

### Runtime Configuration Validation

```python
from agent_engine import Engine
from agent_engine.schema_validator import SchemaValidator

engine = Engine.from_config_dir("config")
validator = SchemaValidator()

# Validate all manifests
errors = validator.validate_all(engine)
if errors:
    print("Configuration errors found:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Configuration valid")
```

### Configuration Hot-Reloading

For long-running processes, implement configuration reloading:

```python
import time
import os
from agent_engine import Engine
from agent_engine.runtime.metadata_collector import compute_file_hash

class ConfigManager:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.engine = Engine.from_config_dir(config_dir)
        self.manifest_hashes = self._compute_hashes()

    def _compute_hashes(self) -> dict:
        """Compute hashes of all manifest files."""
        hashes = {}
        for fname in ["workflow.yaml", "agents.yaml", "tools.yaml"]:
            path = os.path.join(self.config_dir, fname)
            hashes[fname] = compute_file_hash(path)
        return hashes

    def check_for_changes(self) -> bool:
        """Check if any manifest file has changed."""
        current_hashes = self._compute_hashes()
        return current_hashes != self.manifest_hashes

    def reload_if_changed(self):
        """Reload engine if configuration changed."""
        if self.check_for_changes():
            print("Configuration changed, reloading...")
            self.engine = Engine.from_config_dir(self.config_dir)
            self.manifest_hashes = self._compute_hashes()
            return True
        return False

# Usage in long-running process
config_mgr = ConfigManager("config")
while True:
    config_mgr.reload_if_changed()
    # ... process workflow ...
    time.sleep(5)
```

---

## Secret Management

### Best Practices

1. **Never commit secrets** to version control
2. **Use environment variables** for sensitive data
3. **Use secret management systems** for production (Vault, AWS Secrets Manager, etc.)
4. **Rotate credentials regularly**
5. **Log minimal information** containing sensitive data

### Environment Variable Template

Create `.env.template` with all required variables (no real secrets):

```bash
# .env.template
PYTHONPATH=.
LOG_LEVEL=INFO
DEPLOYMENT_ENV=development

# API Keys (replace with actual values in .env)
ANTHROPIC_API_KEY=your-api-key-here
OPENAI_API_KEY=your-api-key-here

# Database
DATABASE_URL=postgresql://user:password@localhost/dbname

# Monitoring
TELEMETRY_ENABLED=true
METRICS_PORT=8000
```

### Loading Secrets from Environment

```python
import os
from dotenv import load_dotenv

# Load from .env file (development only)
load_dotenv()

# Access secrets from environment
api_key = os.getenv("ANTHROPIC_API_KEY")
db_url = os.getenv("DATABASE_URL")

if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not set")
```

### Using Credential Files

For more complex credential management:

```yaml
# config/provider_credentials.yaml (DO NOT COMMIT)
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    max_retries: 3
  openai:
    api_key: ${OPENAI_API_KEY}
    timeout: 30
  database:
    connection_string: ${DATABASE_URL}
```

Load in Python:

```python
import os
import yaml

def load_credentials(cred_file: str) -> dict:
    """Load credentials with environment variable substitution."""
    with open(cred_file) as f:
        content = f.read()

    # Substitute environment variables
    for key, value in os.environ.items():
        content = content.replace(f"${{{key}}}", value)

    return yaml.safe_load(content)

creds = load_credentials("config/provider_credentials.yaml")
```

### Kubernetes Secrets Integration

For Kubernetes deployments, use native secret management:

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-credentials
  namespace: agent-engine
type: Opaque
stringData:
  ANTHROPIC_API_KEY: "your-api-key"
  DATABASE_URL: "postgresql://user:password@host/db"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-config
  namespace: agent-engine
data:
  .env: |
    LOG_LEVEL=INFO
    DEPLOYMENT_ENV=production
```

---

## Health Checks and Monitoring

### Health Check Endpoint

Implement a health check endpoint for probes:

```python
# scripts/healthcheck.py
#!/usr/bin/env python3
import sys
import json
from datetime import datetime
from agent_engine import Engine
from agent_engine.runtime.metadata_collector import compute_file_hash

def check_health() -> dict:
    """Perform comprehensive health check."""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    try:
        # Check engine loads
        engine = Engine.from_config_dir("config")
        health["checks"]["engine_load"] = {"status": "ok"}
        health["checks"]["engine_version"] = {"version": engine.metadata.engine_version}

        # Check manifests
        manifest_hashes = engine.metadata.manifest_hashes
        if manifest_hashes:
            health["checks"]["manifests"] = {"status": "ok", "count": len(manifest_hashes)}
        else:
            health["checks"]["manifests"] = {"status": "warning", "message": "No manifests found"}

        # Check DAG validation
        if engine.dag.validate():
            health["checks"]["dag_validation"] = {"status": "ok"}
        else:
            health["checks"]["dag_validation"] = {"status": "error"}
            health["status"] = "unhealthy"

        # Check config file timestamps
        import os
        for fname in ["workflow.yaml", "agents.yaml", "tools.yaml"]:
            path = f"config/{fname}"
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                health["checks"][fname] = {"status": "ok", "modified": mtime}

    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)

    return health

if __name__ == "__main__":
    result = check_health()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "healthy" else 1)
```

### Liveness Probe (Kubernetes)

```yaml
# k8s/deployment.yaml (excerpt)
livenessProbe:
  exec:
    command:
      - /app/scripts/healthcheck.py
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Readiness Probe

```yaml
readinessProbe:
  exec:
    command:
      - /app/scripts/healthcheck.py
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

### Monitoring Integration

Collect and export metrics:

```python
# Monitor execution metrics
from agent_engine.runtime.metrics_collector import MetricsCollector

collector = MetricsCollector()
engine.run({"request": "test"})

metrics = collector.collect()
print(f"Execution time: {metrics.execution_time_ms}ms")
print(f"Nodes executed: {metrics.nodes_executed}")
print(f"Tasks completed: {metrics.tasks_completed}")
```

### Logging Configuration

Configure structured logging:

```python
import logging
import json

# Configure JSON logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Structured logging helper
def log_structured(level: str, message: str, **context):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        **context
    }
    print(json.dumps(log_entry))

# Usage
log_structured("INFO", "Workflow started", workflow_id="wf_123", user="alice")
```

---

## Deployment Methods

Agent Engine projects support multiple deployment approaches:

### 1. Docker Containerization

See `templates/deployment/docker/Dockerfile` and `docker-compose.yml` for container-based deployment.

### 2. Kubernetes Native

See `templates/deployment/kubernetes/deployment.yaml` for K8s manifests.

### 3. Systemd Service

See `templates/deployment/systemd/agent-engine.service` for Linux systemd integration.

### 4. Direct Python Execution

For development and testing:

```bash
# Direct execution
export AGENT_ENGINE_CONFIG_DIR=config
python -m agent_engine.cli run

# Or use provided scripts
scripts/bootstrap.sh
python main.py
```

### 5. Cloud Deployment

Deploy to major cloud providers:

- **AWS EC2**: Use systemd or container approach
- **AWS Lambda**: Wrap engine in Lambda handler
- **Google Cloud Run**: Containerize with Dockerfile
- **Azure Container Instances**: Use Docker deployment
- **Heroku**: Containerize with Dockerfile

---

## Best Practices

### 1. Version Control

```bash
# Track configuration versions
git tag -a v1.0.0 -m "Production release v1.0.0"

# Always tag before major deployments
git tag -a deployment-2025-01-15 -m "Production deployment"
```

### 2. Pre-Deployment Checklist

- [ ] All dependencies pinned in `requirements.txt`
- [ ] Configuration validated with `SchemaValidator`
- [ ] Secrets not committed to git
- [ ] Health checks passing
- [ ] Tests passing
- [ ] Manifest versions updated
- [ ] Documentation updated
- [ ] Deployment manifest reviewed
- [ ] Rollback plan documented

### 3. Gradual Rollout

```bash
# Stage 1: Deploy to development
AGENT_ENGINE_ENV=development python main.py

# Stage 2: Deploy to staging
AGENT_ENGINE_ENV=staging python main.py

# Stage 3: Deploy to production
AGENT_ENGINE_ENV=production python main.py
```

### 4. Monitoring and Logging

- Centralize logs (ELK, CloudWatch, Datadog)
- Monitor key metrics (latency, error rate, throughput)
- Set up alerts for failures
- Regular health check verification

### 5. Disaster Recovery

- Regular configuration backups
- Maintain manifest history
- Document rollback procedures
- Test recovery procedures regularly

---

## Troubleshooting

### Configuration Load Failures

```bash
# Validate configuration syntax
python -c "
import yaml
with open('config/workflow.yaml') as f:
    yaml.safe_load(f)
print('YAML syntax valid')
"

# Check for missing files
ls -la config/*.yaml
```

### Dependency Issues

```bash
# Check installed versions
pip show agent-engine
pip list | grep -i agent

# Verify imports work
python -c "from agent_engine import Engine; print('OK')"
```

### Permission Issues

```bash
# Make scripts executable
chmod +x scripts/*.sh
chmod +x scripts/*.py

# Check file permissions
ls -la config/
ls -la scripts/
```

### Secret Access Issues

```bash
# Verify environment variables set
env | grep -i api
env | grep -i key

# Check .env file loaded
python -c "
from dotenv import load_dotenv; import os
load_dotenv(); print(os.getenv('ANTHROPIC_API_KEY')[:10])
"
```

---

## Next Steps

1. Clone the project template from `templates/project_template/`
2. Configure manifests for your specific use case
3. Set up environment variables
4. Choose deployment method (Docker, Kubernetes, Systemd)
5. Run health checks before production deployment
6. Implement monitoring and alerting
7. Document your deployment process

For more information, see:
- Packaging guidance is consolidated in `docs/DEVELOPER_GUIDE.md` when needed
- `templates/deployment/` - Deployment templates
- `templates/project_template/` - Example project structure
