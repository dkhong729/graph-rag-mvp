"""
Version management for prompts
"""

from pathlib import Path
import yaml
from datetime import datetime
from typing import Dict, List, Optional
import os


class VersionManager:
    """Manages prompt versions and tags"""

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path(".promptversion")
        self.versions_file = self.config_dir / "versions.yaml"
        self.tags_file = self.config_dir / "tags.yaml"
        self.config_file = self.config_dir / "config.yaml"

        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)

        # Initialize files if they don't exist
        self._init_files()

    def _init_files(self):
        """Initialize configuration files"""
        if not self.config_file.exists():
            config = {
                "version": "1.0.0",
                "default_author": os.getenv("USER", "unknown"),
                "created": datetime.now().isoformat(),
            }
            with open(self.config_file, "w") as f:
                yaml.dump(config, f)

        if not self.versions_file.exists():
            with open(self.versions_file, "w") as f:
                yaml.dump({}, f)

        if not self.tags_file.exists():
            with open(self.tags_file, "w") as f:
                yaml.dump({}, f)

    def bump_version(self, version_str: str, bump_type: str = "patch") -> str:
        """Bump semantic version"""
        try:
            major, minor, patch = map(int, version_str.split("."))
        except ValueError:
            raise ValueError(f"Invalid version format: {version_str}")

        if bump_type == "major":
            return f"{major + 1}.0.0"
        elif bump_type == "minor":
            return f"{major}.{minor + 1}.0"
        elif bump_type == "patch":
            return f"{major}.{minor}.{patch + 1}"
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")

    def record_version(
        self,
        prompt_name: str,
        version: str,
        message: str,
        author: str = None,
        prompt_hash: str = None,
        prompt_data: Dict = None,
    ):
        """Record a new version of a prompt"""
        # Load existing versions
        with open(self.versions_file) as f:
            versions_data = yaml.safe_load(f) or {}

        if prompt_name not in versions_data:
            versions_data[prompt_name] = {"versions": {}, "current": None}

        # Add new version
        versions_data[prompt_name]["versions"][version] = {
            "created": datetime.now().isoformat(),
            "author": author or os.getenv("USER", "unknown"),
            "message": message,
            "hash": prompt_hash or "unknown",
        }

        # Update current version
        versions_data[prompt_name]["current"] = version

        # Save back to file
        with open(self.versions_file, "w") as f:
            yaml.dump(versions_data, f, default_flow_style=False)

        # Store the actual prompt content for this version
        if prompt_data:
            self._store_version_content(prompt_name, version, prompt_data)

    def _store_version_content(self, prompt_name: str, version: str, prompt_data: Dict):
        """Store the actual prompt content for a specific version"""
        versions_dir = self.config_dir / "versions" / prompt_name
        versions_dir.mkdir(parents=True, exist_ok=True)

        version_file = versions_dir / f"{version}.yaml"
        with open(version_file, "w") as f:
            yaml.dump(prompt_data, f, default_flow_style=False)

    def get_versions(self, prompt_name: str) -> Dict:
        """Get version history for a prompt"""
        with open(self.versions_file) as f:
            versions_data = yaml.safe_load(f) or {}

        return versions_data.get(prompt_name, {"versions": {}, "current": None})

    def get_current_version(self, prompt_name: str) -> Optional[str]:
        """Get current version of a prompt"""
        versions = self.get_versions(prompt_name)
        return versions.get("current")

    def list_all_versions(self) -> Dict:
        """List all prompts and their versions"""
        with open(self.versions_file) as f:
            return yaml.safe_load(f) or {}

    def create_tag(self, tag_name: str, prompt_name: str, version: str):
        """Create a tag pointing to a specific version"""
        with open(self.tags_file) as f:
            tags_data = yaml.safe_load(f) or {}

        if prompt_name not in tags_data:
            tags_data[prompt_name] = {}

        tags_data[prompt_name][tag_name] = version

        with open(self.tags_file, "w") as f:
            yaml.dump(tags_data, f, default_flow_style=False)

    def get_tags(self, prompt_name: str) -> Dict[str, str]:
        """Get all tags for a prompt"""
        with open(self.tags_file) as f:
            tags_data = yaml.safe_load(f) or {}

        return tags_data.get(prompt_name, {})

    def resolve_version(self, prompt_name: str, version_or_tag: str) -> str:
        """Resolve a version or tag to actual version number"""
        # First check if it's already a version number
        if self._is_version_number(version_or_tag):
            return version_or_tag

        # Check if it's a tag
        tags = self.get_tags(prompt_name)
        if version_or_tag in tags:
            return tags[version_or_tag]

        raise ValueError(f"Unknown version or tag: {version_or_tag}")

    def _is_version_number(self, version_str: str) -> bool:
        """Check if string is a valid version number"""
        try:
            parts = version_str.split(".")
            return len(parts) == 3 and all(part.isdigit() for part in parts)
        except:
            return False
