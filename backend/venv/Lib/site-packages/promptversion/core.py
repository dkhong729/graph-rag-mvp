"""
Core PromptVersion classes and functionality
"""

from pathlib import Path
import yaml
from jinja2 import Template, Environment, meta
from typing import Dict, Any, Optional, List
import hashlib
from datetime import datetime
from .version_manager import VersionManager


class Prompt:
    """A single prompt with templating and variable management"""

    def __init__(
        self,
        name: str,
        version: str,
        template: str,
        variables: Dict[str, Any],
        description: str = "",
    ):
        self.name = name
        self.version = version
        self.template = template
        self.variables = variables
        self.description = description

        # Setup Jinja2 environment
        self.env = Environment()
        self._jinja_template = self.env.from_string(template)

        # Extract template variables
        ast = self.env.parse(template)
        self.template_vars = meta.find_undeclared_variables(ast)

    def render(self, variables: Dict[str, Any] = None) -> str:
        """Render prompt with provided variables"""
        # Start with defaults from prompt definition
        render_vars = {}

        # Add default values from variables definition
        for var_name, var_config in self.variables.items():
            if isinstance(var_config, dict) and "default" in var_config:
                render_vars[var_name] = var_config["default"]
            else:
                render_vars[var_name] = var_config

        # Override with provided variables
        if variables:
            render_vars.update(variables)

        # Validate required variables
        missing_vars = self.template_vars - set(render_vars.keys())
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")

        return self._jinja_template.render(**render_vars)

    def get_variables(self) -> Dict[str, Any]:
        """Get prompt variable definitions"""
        return self.variables.copy()

    def get_template_variables(self) -> set:
        """Get variables used in template"""
        return self.template_vars.copy()

    def hash(self) -> str:
        """Generate hash of prompt content for version tracking"""
        content = f"{self.template}{self.variables}"
        return hashlib.sha256(content.encode()).hexdigest()[:8]


class PromptVersion:
    """Main entry point for PromptVersion functionality"""

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.config_dir = Path(".promptversion")
        self._cache = {}

        # Ensure directories exist
        self.prompts_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)

    def get(self, name: str, version: Optional[str] = None) -> Prompt:
        """Get a prompt by name and optional version"""
        cache_key = f"{name}:{version or 'current'}"

        if cache_key not in self._cache:
            if version:
                self._cache[cache_key] = self._get_versioned_prompt(name, version)
            else:
                self._cache[cache_key] = self._get_current_prompt(name)

        return self._cache[cache_key]

    def render(
        self, name: str, variables: Dict[str, Any] = None, version: Optional[str] = None
    ) -> str:
        """Render a prompt with variables"""
        prompt = self.get(name, version)
        return prompt.render(variables)

    def list_prompts(self) -> List[str]:
        """List all available prompts"""
        prompts = []
        for prompt_file in self.prompts_dir.glob("*.yaml"):
            prompts.append(prompt_file.stem)
        return sorted(prompts)

    def create_prompt(
        self,
        name: str,
        template: str,
        variables: Dict[str, Any] = None,
        description: str = "",
    ) -> Prompt:
        """Create a new prompt"""
        variables = variables or {}

        prompt_data = {
            "name": name,
            "version": "0.1.0",
            "description": description,
            "variables": variables,
            "template": template,
        }

        prompt_path = self.prompts_dir / f"{name}.yaml"
        with open(prompt_path, "w") as f:
            yaml.dump(prompt_data, f, default_flow_style=False)

        # Clear cache
        self._cache.clear()

        return self.get(name)

    def _get_current_prompt(self, name: str) -> Prompt:
        """Load current version of prompt from file"""
        prompt_path = self.prompts_dir / f"{name}.yaml"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt '{name}' not found at {prompt_path}")

        with open(prompt_path) as f:
            data = yaml.safe_load(f)

        return Prompt(
            name=data["name"],
            version=data["version"],
            template=data["template"],
            variables=data.get("variables", {}),
            description=data.get("description", ""),
        )

    def _get_versioned_prompt(self, name: str, version: str) -> Prompt:
        """Load specific version of prompt from version history"""
        vm = VersionManager(self.config_dir)

        # Check if version exists
        versions_data = vm.get_versions(name)
        if version not in versions_data["versions"]:
            available = list(versions_data["versions"].keys())
            raise ValueError(
                f"Version {version} not found for '{name}'. Available: {available}"
            )

        # Load versioned content from storage
        version_file = self.config_dir / "versions" / name / f"{version}.yaml"

        if not version_file.exists():
            # Fallback: if version content not stored, return current with version metadata
            current = self._get_current_prompt(name)
            current.version = version
            return current

        with open(version_file) as f:
            data = yaml.safe_load(f)

        return Prompt(
            name=data["name"],
            version=data["version"],
            template=data["template"],
            variables=data.get("variables", {}),
            description=data.get("description", ""),
        )

    def _find_repo_root(self) -> Path:
        """Find the repository root by looking for .promptversion directory"""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".promptversion").exists():
                return current
            current = current.parent
        return Path.cwd()
