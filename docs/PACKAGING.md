# Phase 22: Packaging & Distribution Guide

This document describes how to build, package, and distribute Agent Engine as a PyPI package or as a standalone distribution.

## Table of Contents

1. [PyPI Package Structure](#pypi-package-structure)
2. [Version Management](#version-management)
3. [Build Process](#build-process)
4. [Distribution Formats](#distribution-formats)
5. [Installation Methods](#installation-methods)
6. [Release Workflow](#release-workflow)
7. [Development Installation](#development-installation)

---

## PyPI Package Structure

Agent Engine follows standard Python packaging conventions.

### Directory Layout

```
agent-engine/
├── src/
│   └── agent_engine/
│       ├── __init__.py
│       ├── engine.py
│       ├── dag.py
│       ├── schemas/
│       ├── runtime/
│       ├── cli/
│       └── ...
├── tests/
│   ├── test_*.py
│   └── ...
├── docs/
│   ├── DEPLOYMENT.md
│   ├── PACKAGING.md
│   └── ...
├── scripts/
├── examples/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
└── MANIFEST.in
```

### Package Metadata (pyproject.toml)

```toml
[build-system]
requires = ["setuptools>=69.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-engine"
version = "0.0.1"
description = "Modular multi-agent LLM orchestration engine"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Agent Engine Team", email = "team@example.com" }]
keywords = ["agent", "llm", "orchestration", "workflow", "dag"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Topic :: Software Development :: Libraries",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "pydantic>=2.6",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-cov>=4.1",
    "ruff>=0.4",
    "mypy>=1.9",
]
docs = [
    "sphinx>=6.0",
    "sphinx-rtd-theme>=1.0",
]

[project.urls]
Homepage = "https://github.com/example/agent-engine"
Documentation = "https://agent-engine.readthedocs.io"
Repository = "https://github.com/example/agent-engine.git"
Issues = "https://github.com/example/agent-engine/issues"

[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
agent_engine = ["py.typed"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
src = ["src", "tests"]
target-version = "py310"
line-length = 100

[tool.mypy]
python_version = "3.10"
check_untyped_defs = true
ignore_missing_imports = true
```

### MANIFEST.in

Include additional files in distribution:

```
include README.md
include LICENSE
include pyproject.toml
recursive-include src/agent_engine py.typed
recursive-include docs *.md
recursive-include examples *.yaml *.py
```

---

## Version Management

### Semantic Versioning

Agent Engine follows semantic versioning:

- **MAJOR**: Breaking changes (incompatible API changes)
- **MINOR**: New features (backward-compatible)
- **PATCH**: Bug fixes (backward-compatible)

Format: `MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`

Examples:
- `0.0.1` - Initial release
- `0.1.0` - First minor release with features
- `1.0.0` - Stable release
- `1.1.0` - Feature release
- `1.1.1` - Patch release
- `2.0.0-alpha.1` - Pre-release version
- `2.0.0-rc.1` - Release candidate

### Version Storage

Store version in single location:

```python
# src/agent_engine/__init__.py
__version__ = "0.0.1"

# Import in pyproject.toml (using dynamic versioning)
# version is read from src/agent_engine/__init__.py
```

### Version Consistency

Ensure version consistency:

```bash
# Check version in all locations
grep -r "__version__" src/agent_engine/__init__.py
grep "^version" pyproject.toml

# Update version
sed -i 's/__version__ = ".*"/__version__ = "0.1.0"/' src/agent_engine/__init__.py
```

---

## Build Process

### Prerequisites

```bash
# Install build tools
pip install build twine

# Verify tools are installed
python -m build --version
twine --version
```

### Building Distribution

```bash
# Build both wheel and source distribution
python -m build

# Output:
# dist/agent-engine-0.0.1.tar.gz      (source distribution)
# dist/agent-engine-0.0.1-py3-none-any.whl  (wheel)

# List built distributions
ls -lh dist/
```

### Building Wheel Only

```bash
# Wheel is faster for installation
python -m build --wheel

# Output: dist/agent-engine-0.0.1-py3-none-any.whl
```

### Building Source Distribution Only

```bash
# Source distribution includes all files
python -m build --sdist

# Output: dist/agent-engine-0.0.1.tar.gz
```

### Build Verification

```bash
# Check distribution contents
tar -tzf dist/agent-engine-0.0.1.tar.gz | head -20

# Or for wheel (ZIP format)
unzip -l dist/agent-engine-0.0.1-py3-none-any.whl | head -20
```

---

## Distribution Formats

### Wheel Format (.whl)

Fast, pre-built binary distribution:

- **Advantages**: Fast installation, no compilation needed
- **File size**: Smaller
- **Compatibility**: Platform-specific (pure Python wheels work everywhere)
- **Contents**: Pre-packaged bytecode

```bash
# Install from wheel
pip install dist/agent-engine-0.0.1-py3-none-any.whl

# Wheel naming convention
# {package}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
# agent_engine-0.0.1-py3-none-any.whl
#   py3: Python 3.x (any minor version)
#   none: No ABI compatibility
#   any: Any platform (pure Python)
```

### Source Distribution (.tar.gz / .zip)

Original source code format:

- **Advantages**: Portable, includes all source
- **File size**: Larger
- **Installation**: Requires compilation/processing
- **Contents**: Raw Python source files

```bash
# Install from source distribution
pip install dist/agent-engine-0.0.1.tar.gz

# Extract and inspect
tar -xzf dist/agent-engine-0.0.1.tar.gz
cd agent-engine-0.0.1
cat PKG-INFO
```

### Choosing Distribution Format

| Scenario | Format | Reason |
|----------|--------|--------|
| PyPI release | Both wheel + sdist | Flexibility and compatibility |
| Internal distribution | Wheel | Speed and simplicity |
| Offline installation | Wheel | No compilation needed |
| Platform-specific | Wheel | C extensions pre-compiled |
| Source inspection | sdist | Full source available |
| CI/CD builds | Wheel | Faster builds |

---

## Installation Methods

### From PyPI (Recommended)

```bash
# Install latest version
pip install agent-engine

# Install specific version
pip install agent-engine==0.0.1

# Install with version constraint
pip install 'agent-engine>=0.0.1,<1.0.0'

# Install with optional dependencies
pip install agent-engine[dev]
pip install agent-engine[docs]
pip install agent-engine[dev,docs]
```

### From Source (Development)

```bash
# Clone repository
git clone https://github.com/example/agent-engine.git
cd agent-engine

# Install in editable mode
pip install -e .

# Install with development dependencies
pip install -e .[dev]

# Changes to source immediately reflected (no reinstall needed)
```

### From GitHub

```bash
# Install directly from GitHub (latest main)
pip install git+https://github.com/example/agent-engine.git

# Install from specific branch
pip install git+https://github.com/example/agent-engine.git@develop

# Install specific release tag
pip install git+https://github.com/example/agent-engine.git@v0.0.1
```

### From Local Distribution

```bash
# Install from local wheel
pip install dist/agent-engine-0.0.1-py3-none-any.whl

# Install from local source distribution
pip install dist/agent-engine-0.0.1.tar.gz

# Useful for offline installation or internal distribution
```

### Using requirements.txt

```
# requirements.txt
agent-engine==0.0.1
pydantic>=2.6
pyyaml>=6.0
```

```bash
# Install from requirements
pip install -r requirements.txt
```

### Using Poetry

```bash
# pyproject.toml (Poetry format)
[tool.poetry.dependencies]
python = "^3.10"
agent-engine = "^0.0.1"

# Install with poetry
poetry install
```

---

## Release Workflow

### Step 1: Prepare Release

```bash
# Update version
vim src/agent_engine/__init__.py
# Change __version__ = "0.0.1" to "0.1.0"

# Update changelog
vim CHANGELOG.md
# Add changes for v0.1.0

# Commit version bump
git add src/agent_engine/__init__.py CHANGELOG.md
git commit -m "chore: bump version to 0.1.0"
```

### Step 2: Run Tests

```bash
# Run test suite
pytest tests/ -v

# Check coverage
pytest tests/ --cov=src/agent_engine

# Lint code
ruff check src/

# Type check
mypy src/agent_engine
```

### Step 3: Build Distribution

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build distributions
python -m build

# Verify builds
ls -lh dist/
twine check dist/*
```

### Step 4: Tag Release

```bash
# Create git tag
git tag -a v0.1.0 -m "Release version 0.1.0"

# Verify tag
git tag -l
git show v0.1.0
```

### Step 5: Upload to PyPI

```bash
# Create PyPI credentials
# 1. Generate API token at https://pypi.org/manage/account/tokens/
# 2. Store in ~/.pypirc or use environment variable

# Upload to PyPI (production)
twine upload dist/*

# Or upload to TestPyPI first (recommended)
twine upload --repository testpypi dist/*

# Verify upload
pip install --index-url https://test.pypi.org/simple/ agent-engine==0.1.0
```

### Step 6: Push to Repository

```bash
# Push commits and tags
git push origin main
git push origin --tags

# Create GitHub release
# Use GitHub web interface or:
# gh release create v0.1.0 --title "v0.1.0" --generate-notes
```

### Complete Release Checklist

```bash
# 1. Update version
# 2. Run tests: pytest tests/
# 3. Check lint: ruff check src/
# 4. Update CHANGELOG.md
# 5. Commit: git commit -am "chore: v0.1.0"
# 6. Tag: git tag -a v0.1.0 -m "Release v0.1.0"
# 7. Build: python -m build
# 8. Verify: twine check dist/*
# 9. Upload: twine upload dist/*
# 10. Push: git push origin main --tags
```

---

## Development Installation

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/example/agent-engine.git
cd agent-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with all dependencies
pip install -e ".[dev]"

# Verify installation
python -c "from agent_engine import Engine; print(Engine.__doc__)"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_engine_initialization.py

# Run specific test function
pytest tests/test_engine_initialization.py::test_engine_loads_from_config

# Run with coverage
pytest --cov=src/agent_engine tests/

# Run tests matching pattern
pytest -k "metadata" -v
```

### Code Quality

```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check src/ tests/

# Type checking
mypy src/agent_engine

# Full pre-commit checks
pre-commit run --all-files
```

### Building Documentation

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Build HTML documentation
cd docs
sphinx-build -b html . _build/html

# View documentation
open _build/html/index.html
```

---

## Python Version Support

Agent Engine targets Python 3.10+:

```toml
requires-python = ">=3.10"

[project.classifiers]
"Programming Language :: Python :: 3.10",
"Programming Language :: Python :: 3.11",
"Programming Language :: Python :: 3.12",
```

### Version Testing

```bash
# Test with multiple Python versions using tox
pip install tox

# Create tox.ini
[tox]
envlist = py310,py311,py312

[testenv]
deps = -e .[dev]
commands = pytest

# Run tests
tox
```

---

## Troubleshooting

### Build Failures

```bash
# Clean build artifacts
rm -rf build/ dist/ *.egg-info .eggs/

# Check build dependencies
python -m build --help

# Try verbose build
python -m build -v
```

### Upload Issues

```bash
# Check PyPI credentials
cat ~/.pypirc

# Validate package before upload
twine check dist/*

# Check package metadata
python -c "
from setuptools.config import read_configuration
config = read_configuration('pyproject.toml')
print(config)
"
```

### Installation Issues

```bash
# Check Python version
python --version  # Should be >= 3.10

# Verify package installed
pip show agent-engine

# Check import path
python -c "import sys; print(sys.path)"

# Try installing in clean environment
python -m venv testenv
source testenv/bin/activate
pip install agent-engine
```

---

## Next Steps

1. Review `docs/DEPLOYMENT.md` for deployment guidance
2. Use templates in `templates/deployment/` for your environment
3. Configure `pyproject.toml` with your project metadata
4. Follow release workflow for stable distributions
5. Monitor PyPI package statistics and issues

For more information:
- [Python Packaging Guide](https://packaging.python.org/)
- [setuptools Documentation](https://setuptools.pypa.io/)
- [PyPI Help](https://pypi.org/help/)
