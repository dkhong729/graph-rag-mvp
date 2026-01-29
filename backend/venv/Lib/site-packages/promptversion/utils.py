"""
Utility functions for PromptVersion
"""

import re
from pathlib import Path
from typing import Dict, Any


def validate_prompt_name(name: str) -> bool:
    """Validate prompt name (alphanumeric, underscore, hyphen only)"""
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))


def find_repo_root(start_path: Path = None) -> Path:
    """Find repository root by looking for .promptversion directory"""
    current = start_path or Path.cwd()

    while current != current.parent:
        if (current / ".promptversion").exists():
            return current
        current = current.parent

    # If not found, return current directory
    return start_path or Path.cwd()


def safe_load_yaml(file_path: Path) -> Dict[str, Any]:
    """Safely load YAML file with error handling"""
    import yaml

    try:
        with open(file_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}")


def format_version_info(version_data: Dict[str, Any]) -> str:
    """Format version information for display"""
    lines = []
    lines.append(f"Version: {version_data.get('version', 'unknown')}")
    lines.append(f"Author: {version_data.get('author', 'unknown')}")
    lines.append(f"Created: {version_data.get('created', 'unknown')}")

    if version_data.get("message"):
        lines.append(f"Message: {version_data['message']}")

    return "\n".join(lines)
