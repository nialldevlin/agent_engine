#!/bin/bash
# Bootstrap script for Agent Engine deployment
# Performs initialization and setup tasks before main process starts
# Exit on error, undefined variables, and pipe failures
set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="${AGENT_ENGINE_CONFIG_DIR:-$PROJECT_ROOT/config}"
DATA_DIR="${PROJECT_ROOT}/data"
LOGS_DIR="${PROJECT_ROOT}/logs"
ARTIFACTS_DIR="${PROJECT_ROOT}/artifacts"

# Logging configuration
LOG_LEVEL="${LOG_LEVEL:-INFO}"
LOG_FILE="${LOGS_DIR}/bootstrap.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Ensure directories exist
log_info "Creating required directories..."
mkdir -p "$DATA_DIR" "$LOGS_DIR" "$ARTIFACTS_DIR"
chmod 755 "$DATA_DIR" "$LOGS_DIR" "$ARTIFACTS_DIR"
log_info "Directories created: data, logs, artifacts"

# Validate configuration directory exists
if [ ! -d "$CONFIG_DIR" ]; then
    log_error "Configuration directory not found: $CONFIG_DIR"
    exit 1
fi
log_info "Configuration directory verified: $CONFIG_DIR"

# Check for required manifest files
log_info "Validating manifest files..."
required_files=("workflow.yaml" "agents.yaml" "tools.yaml")
for file in "${required_files[@]}"; do
    if [ ! -f "$CONFIG_DIR/$file" ]; then
        log_error "Required manifest file not found: $CONFIG_DIR/$file"
        exit 1
    fi
    log_info "  ✓ $file"
done

# Load environment variables if .env exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    log_info "Loading environment variables from .env"
    # shellcheck source=/dev/null
    set +a
    source "$PROJECT_ROOT/.env"
    set -a
fi

# Export environment variables for subprocess
export AGENT_ENGINE_CONFIG_DIR="$CONFIG_DIR"
export PYTHONUNBUFFERED=1

# Validate Python version
log_info "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
    log_info "Python version valid: $PYTHON_VERSION"
else
    log_error "Python 3.10+ required, found: $PYTHON_VERSION"
    exit 1
fi

# Validate agent-engine is installed
log_info "Checking agent-engine installation..."
if ! python3 -c "import agent_engine; print(agent_engine.__version__)" > /dev/null 2>&1; then
    log_error "agent-engine package not installed"
    exit 1
fi
AGENT_VERSION=$(python3 -c "import agent_engine; print(agent_engine.__version__)")
log_info "agent-engine version: $AGENT_VERSION"

# Validate configuration with Python
log_info "Validating configuration with agent-engine..."
python3 << 'EOF'
import sys
import os
from agent_engine import Engine

config_dir = os.getenv("AGENT_ENGINE_CONFIG_DIR")
try:
    engine = Engine.from_config_dir(config_dir)
    print(f"✓ Configuration valid")
    print(f"✓ Engine version: {engine.metadata.engine_version}")
    print(f"✓ Manifests loaded: {len(engine.metadata.manifest_hashes)} files")
    print(f"✓ DAG validation: {'passed' if engine.dag.validate() else 'failed'}")
except Exception as e:
    print(f"✗ Configuration validation failed: {e}", file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    log_error "Configuration validation failed"
    exit 1
fi

# Create bootstrap record
log_info "Recording bootstrap metadata..."
BOOTSTRAP_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BOOTSTRAP_HASH=$(sha256sum "$CONFIG_DIR/workflow.yaml" 2>/dev/null | awk '{print $1}')

cat > "$DATA_DIR/bootstrap.json" << EOF
{
  "bootstrap_timestamp": "$BOOTSTRAP_TIME",
  "config_hash": "$BOOTSTRAP_HASH",
  "deployment_env": "${AGENT_ENGINE_ENV:-development}",
  "agent_version": "$AGENT_VERSION",
  "python_version": "$PYTHON_VERSION"
}
EOF

log_info "Bootstrap metadata recorded"

# Set up signal handlers for graceful shutdown
log_info "Setting up signal handlers..."
trap 'log_info "Shutdown signal received"; exit 0' SIGTERM SIGINT

# Wait for dependencies (optional)
if [ "${WAIT_FOR_POSTGRES:-false}" = "true" ]; then
    log_info "Waiting for PostgreSQL..."
    max_attempts=30
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if python3 -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null; then
            log_info "PostgreSQL is ready"
            break
        fi
        log_warn "Attempt $attempt/$max_attempts: PostgreSQL not ready yet..."
        sleep 2
        ((attempt++))
    done
    if [ $attempt -gt $max_attempts ]; then
        log_error "PostgreSQL failed to start within timeout"
        exit 1
    fi
fi

# Run optional pre-start script
if [ -f "$PROJECT_ROOT/scripts/pre-start.sh" ]; then
    log_info "Running pre-start script..."
    bash "$PROJECT_ROOT/scripts/pre-start.sh" || {
        log_error "Pre-start script failed"
        exit 1
    }
fi

log_info "Bootstrap completed successfully"
log_info "Ready to start Agent Engine"

# Return success
exit 0
