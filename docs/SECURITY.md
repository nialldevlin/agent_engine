# Security & Credential Management

This document covers security practices and credential management for Agent Engine v1.

## Quick Pointer
- For first-time setup and credentials, start with `docs/DEVELOPER_GUIDE.md`.
- This document focuses on secure credential handling and deployment-grade practices (deployment details in `docs/DEPLOYMENT.md`).

## Phase 20: Secrets & Provider Credential Management

Agent Engine v1 supports loading provider credentials (API keys, tokens, etc.) from two sources:
1. Environment variables
2. Plain files on disk

### Design Principles

**No Encryption in v1**: Secrets are stored in plain text on disk or as environment variables. Encryption is deferred to Phase 22+.

**Secure by Default**: Credentials are loaded from carefully controlled sources and never logged in full in telemetry.

**Metadata-Only Telemetry**: Credential loading emits only metadata (ID, provider, source, success/failure), never the actual secret values.

### Environment Variables

#### Best Practices

1. **Use Strong Variable Names**: Prefix with a clear indicator
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   export OPENAI_API_KEY="sk-..."
   ```

2. **Keep Variables Out of Version Control**: Never commit .env files with secrets
   ```bash
   # .gitignore
   .env
   .env.local
   *.key
   ```

3. **Limit Process Access**: Use OS-level process isolation where possible
   - Use containerization (Docker) with secret volume mounts
   - Use systemd service user restrictions
   - Use cloud provider secret management (AWS Secrets Manager, etc.)

4. **Audit Access**: Monitor which processes access environment variables
   ```bash
   # On Linux, check /proc/[pid]/environ
   cat /proc/$$/environ | tr '\0' '\n' | grep API_KEY
   ```

#### Configuration

```yaml
# provider_credentials.yaml
provider_credentials:
  - id: "anthropic_sonnet"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"
    config:
      base_url: "https://api.anthropic.com"
      default_model: "claude-sonnet-4"
```

### Plain Files on Disk

#### File Permissions (CRITICAL)

Protect credential files with strict OS-level permissions:

```bash
# Create a secrets directory
mkdir -p /etc/agent-engine/secrets
chmod 700 /etc/agent-engine/secrets  # Only owner can read/write/execute

# Create credential file
echo "sk-ant-..." > /etc/agent-engine/secrets/anthropic.txt
chmod 600 /etc/agent-engine/secrets/anthropic.txt  # Only owner can read/write

# Verify permissions
ls -la /etc/agent-engine/secrets/
# drwx------  2 app-user app-group 4096 Dec 11 17:00 secrets/
# -rw-------  1 app-user app-group   30 Dec 11 17:00 anthropic.txt
```

#### Plain Text Files

Store API keys directly in plain text files:

```bash
# /etc/agent-engine/secrets/anthropic.txt
sk-ant-1234567890abcdefghijklmnopqrstuvwxyz

# /etc/agent-engine/secrets/openai.txt
sk-proj-1234567890abcdefghijklmnopqrstuvwxyz
```

Configuration:

```yaml
provider_credentials:
  - id: "anthropic_sonnet"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "file"
      file_path: "/etc/agent-engine/secrets/anthropic.txt"
```

#### JSON Files with Key Extraction

Store multiple credentials in a single JSON file:

```json
{
  "anthropic": {
    "api_key": "sk-ant-..."
  },
  "openai": {
    "api_key": "sk-..."
  }
}
```

Configuration:

```yaml
provider_credentials:
  - id: "anthropic_sonnet"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "file"
      file_path: "/etc/agent-engine/secrets/credentials.json"
      file_key: "anthropic.api_key"
```

#### YAML Files with Key Extraction

Store credentials in YAML format:

```yaml
anthropic:
  api_key: "sk-ant-..."
openai:
  api_key: "sk-..."
services:
  anthropic:
    credentials:
      key: "sk-ant-..."
```

Configuration:

```yaml
provider_credentials:
  - id: "anthropic_sonnet"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "file"
      file_path: "/etc/agent-engine/secrets/credentials.yaml"
      file_key: "anthropic.api_key"
```

### Deployment Patterns

#### Docker

Use Docker secrets and volume mounts:

```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -e .
```

```bash
# Store secret in file
echo "sk-ant-..." > /tmp/anthropic.txt

# Run container with secret mounted
docker run \
  --rm \
  -v /tmp/anthropic.txt:/etc/secrets/anthropic.txt:ro \
  -e ANTHROPIC_API_KEY_FILE=/etc/secrets/anthropic.txt \
  my-agent-engine-image
```

#### Kubernetes

Use Kubernetes Secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-engine-secrets
type: Opaque
stringData:
  anthropic-api-key: "sk-ant-..."
  openai-api-key: "sk-..."
---
apiVersion: v1
kind: Pod
metadata:
  name: agent-engine
spec:
  containers:
  - name: agent-engine
    image: my-agent-engine:latest
    volumeMounts:
    - name: secrets
      mountPath: /etc/secrets
      readOnly: true
    env:
    - name: ANTHROPIC_API_KEY
      valueFrom:
        secretKeyRef:
          name: agent-engine-secrets
          key: anthropic-api-key
  volumes:
  - name: secrets
    secret:
      secretName: agent-engine-secrets
```

#### AWS Lambda / Managed Services

Use AWS Secrets Manager or Parameter Store:

```python
import boto3

client = boto3.client('secretsmanager')
response = client.get_secret_value(SecretId='agent-engine/anthropic-key')
api_key = response['SecretString']

# Set as environment variable
os.environ['ANTHROPIC_API_KEY'] = api_key
```

### Accessing Credentials in Code

#### Example: Getting a Credential

```python
from agent_engine import Engine

engine = Engine.from_config_dir("./config")

# Get credential provider
cred_provider = engine.get_credential_provider()

# Check if credential is loaded
if cred_provider.has_credential("anthropic_sonnet"):
    # Get the actual credential
    api_key = cred_provider.get_credential("anthropic_sonnet")
    # Use api_key to initialize client
else:
    # Handle missing credential
    raise RuntimeError("Anthropic API key not configured")
```

#### Example: Checking Credential Status

```python
# Get metadata (safe for logging)
metadata = cred_provider.get_credential_metadata("anthropic_sonnet")
print(f"Credential {metadata.credential_id} loaded: {metadata.loaded}")

# List all credentials
for cred_id in cred_provider.list_credential_ids():
    meta = cred_provider.get_credential_metadata(cred_id)
    print(f"{cred_id}: {'loaded' if meta.loaded else 'failed'}")
```

### Telemetry & Logging

#### Safe for Telemetry

Credential metadata is safe to emit in telemetry:

```python
# Get metadata (NO SECRET VALUES)
metadata = cred_provider.get_credential_metadata("my_credential")
# {
#   "credential_id": "my_credential",
#   "provider": "anthropic",
#   "source": "env",
#   "loaded": true,
#   "error": null
# }

# Safe to emit in events/logs
engine.telemetry.emit(Event(
    type=EventType.CREDENTIAL_LOADED,
    payload=metadata.to_dict()  # Safe!
))
```

#### Dangerous (DO NOT DO)

```python
# WRONG: Never log the credential value
api_key = cred_provider.get_credential("my_credential")
logger.info(f"Using API key: {api_key}")  # SECRET LEAKED!

# WRONG: Never emit full config
logger.info(f"Credential config: {credential.to_dict()}")  # Secret might be included

# WRONG: Never stringify credentials
print(f"Credentials: {cred_provider}")  # Might include secrets
```

### Error Handling

Credential loading errors are non-fatal by default:

```python
# Provider loads what it can
provider = CredentialProvider(manifest)

# Check what failed
failed_ids = provider.list_failed_credential_ids()
if failed_ids:
    print(f"Warning: Failed to load {len(failed_ids)} credentials")
    for cred_id in failed_ids:
        meta = provider.get_credential_metadata(cred_id)
        print(f"  {cred_id}: {meta.error}")

# Try to access failed credential
try:
    key = provider.get_credential("missing_credential")
except CredentialNotFoundError as e:
    # Handle gracefully
    logger.warning(f"Credential not available: {e}")
```

### Audit Trail

Monitor credential access:

```python
# Log only metadata
metadata = cred_provider.get_all_metadata()
for cred_id, meta in metadata.items():
    if meta.loaded:
        logger.info(f"Credential loaded: {cred_id} from {meta.source}")
    else:
        logger.warning(f"Failed to load credential {cred_id}: {meta.error}")
```

### Future Work (Phase 22+)

Planned enhancements:

1. **Encryption at Rest**: Encrypt credential files with AES-256
2. **Secret Rotation**: Automatic secret rotation and versioning
3. **Audit Logging**: Detailed access logs for all credential operations
4. **Hardware Security Modules (HSM)**: Integration with TPM/HSM
5. **Cloud Provider Integration**: Direct integration with AWS/Azure/GCP secret services
6. **Certificate Management**: Support for client certificates and mTLS

### Security Checklist

Before deploying to production:

- [ ] All credential files have mode 600 (owner read/write only)
- [ ] All credential directories have mode 700 (owner only)
- [ ] Credentials are not in version control (check .gitignore)
- [ ] Environment variables are not logged or exposed
- [ ] Telemetry only emits metadata, not secret values
- [ ] Credential files are on encrypted filesystems
- [ ] Access logs are monitored for unauthorized credential access
- [ ] Credentials are rotated regularly
- [ ] Backup and disaster recovery procedures are in place
- [ ] Team members understand credential security practices

### References

- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [CWE-798: Use of Hard-Coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [Linux File Permissions](https://linux.die.net/man/1/chmod)
