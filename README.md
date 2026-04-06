# Self-Editing Narrative Hypergraph (SENH)

A real-time narrative hypergraph prototype where LLM-driven scene agents can mutate graph
topology while preserving global story coherence.

## Features

- **Python 3.12+** - Modern Python version with latest features
- **UV Package Manager** - Fast, reliable Python package management
- **Pydantic Settings** - Type-safe configuration from environment variables
- **Pre-commit Hooks** - Automated code quality checks with Ruff
- **Configurable Logging** - Flexible logging with multiple formatters
- **Environment Management** - Dotenv support for local development

## Engineering Governance

- Project constitution: `.specify/memory/constitution.md`
- Runtime engineering rules: `AGENTS.md`
- Product requirements baseline: `docs/prd.md`

## Quick Start

### Prerequisites

- Python 3.12 or higher
- [UV](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd palimpsest

# Install dependencies and set up pre-commit hooks
make install
```

This will:
- Install all dependencies with UV
- Install pre-commit hooks
- Update hooks to latest versions

### Development

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run your application
python -m your_module
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Available settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FORMATTER` | `standard` | Log format style (`standard` or `detailed`) |

### Logging

The template includes a flexible logging setup:

```python
from config.logging_config import setup_logging
import logging

# Initialize logging
setup_logging()

# Use the logger
logger = logging.getLogger("app")
logger.info("Application started")
```

**Formatter Options:**
- `standard`: `2024-01-15 10:30:45 [INFO] app: Message`
- `detailed`: `2024-01-15 10:30:45 [INFO] app:42 - Message` (includes line numbers)

## Project Structure

```
.
├── config/
│   ├── env.py              # Pydantic settings configuration
│   └── logging_config.py   # Logging setup
├── .env.example            # Example environment variables
├── .gitignore             # Git ignore patterns
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── .python-version        # Python version specification
├── Makefile              # Common development tasks
├── pyproject.toml        # Project metadata and dependencies
├── README.md             # This file
└── uv.lock               # Locked dependency versions
```

## Development Tools

### Pre-commit Hooks

The following hooks run automatically on commit:

- **Ruff** - Fast Python linter and formatter
- **Check AST** - Validates Python syntax
- **End of File Fixer** - Ensures files end with a newline
- **Trailing Whitespace** - Removes trailing whitespace

Manual run:
```bash
pre-commit run --all-files
```

### Code Quality

```bash
# Format code
ruff format .

# Check and auto-fix issues
ruff check . --fix
```

## Adding Dependencies

```bash
# Add runtime dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Sync dependencies
uv sync
```

## Customization

To use this template for your project:

1. **Update `pyproject.toml`**:
   - Change `name` to your project name
   - Update `description`
   - Add your dependencies

2. **Update `.env.example`**:
   - Add your application-specific environment variables

3. **Update `config/env.py`**:
   - Add Pydantic fields for your environment variables

4. **Create your application code**:
   - Add your modules and packages
   - Import and use the settings/logging configuration

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
