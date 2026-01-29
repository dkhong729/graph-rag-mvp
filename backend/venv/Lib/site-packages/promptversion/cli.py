"""
CLI interface for PromptVersion
"""

import click
import yaml
from pathlib import Path
from .core import PromptVersion
from .version_manager import VersionManager


@click.group()
def cli():
    """PromptVersion - Simple prompt version control for AI development"""


@cli.command()
def init():
    """Initialize a prompt repository"""
    prompts_dir = Path("prompts")
    config_dir = Path(".promptversion")

    prompts_dir.mkdir(exist_ok=True)
    config_dir.mkdir(exist_ok=True)

    # Create example prompt if none exist
    if not list(prompts_dir.glob("*.yaml")):
        example_prompt = {
            "name": "example",
            "version": "0.1.0",
            "description": "Example prompt template",
            "variables": {
                "name": {
                    "default": "World",
                    "type": "string",
                    "description": "Name to greet",
                }
            },
            "template": "Hello {{name}}! How can I help you today?",
        }

        with open(prompts_dir / "example.yaml", "w") as f:
            yaml.dump(example_prompt, f, default_flow_style=False)

    click.echo("✓ Initialized prompt repository")
    click.echo(f"✓ Created {prompts_dir}")
    click.echo(f"✓ Created {config_dir}")
    if (prompts_dir / "example.yaml").exists():
        click.echo("✓ Added example.yaml")


@cli.command()
@click.argument("name")
@click.option("--description", "-d", default="", help="Prompt description")
def create(name, description):
    """Create a new prompt"""
    pv = PromptVersion()

    template = f"""# {name} prompt template
# Replace this with your actual prompt
You are a helpful assistant.

User input: {{{{user_input}}}}

Please respond helpfully."""

    variables = {
        "user_input": {
            "default": "",
            "type": "string",
            "description": "User input to process",
        }
    }

    try:
        prompt = pv.create_prompt(name, template, variables, description)
        click.echo(f"✓ Created prompt '{name}' v{prompt.version}")
        click.echo(f"  File: prompts/{name}.yaml")
        click.echo(f"  Edit with: promptversion edit {name}")
    except Exception as e:
        click.echo(f"✗ Error creating prompt: {e}", err=True)


@cli.command()
@click.argument("name")
def edit(name):
    """Edit a prompt (opens in default editor)"""
    prompt_path = Path(f"prompts/{name}.yaml")

    if not prompt_path.exists():
        click.echo(f"✗ Prompt '{name}' not found", err=True)
        return

    click.edit(filename=str(prompt_path))
    click.echo(f"✓ Edited {prompt_path}")


@cli.command()
@click.argument("name")
@click.option("--message", "-m", required=True, help="Commit message")
@click.option(
    "--bump",
    type=click.Choice(["patch", "minor", "major"]),
    default="patch",
    help="Version bump type",
)
def commit(name, message, bump):
    """Commit changes to a prompt"""
    pv = PromptVersion()
    vm = VersionManager()

    try:
        # Get current prompt
        prompt = pv.get(name)

        # Bump version
        new_version = vm.bump_version(prompt.version, bump)

        # Update prompt version in file
        prompt_path = Path(f"prompts/{name}.yaml")
        with open(prompt_path) as f:
            data = yaml.safe_load(f)

        data["version"] = new_version

        with open(prompt_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        # Record version
        vm.record_version(
            name, new_version, message, prompt_hash=prompt.hash(), prompt_data=data
        )

        # Clear cache
        pv._cache.clear()

        click.echo(f"✓ Committed {name} v{new_version}: {message}")

    except Exception as e:
        click.echo(f"✗ Error committing: {e}", err=True)


@cli.command()
@click.argument("name")
@click.argument("tag_name")
@click.argument("version", required=False)
def tag(name, tag_name, version):
    """Create a tag for a prompt version"""
    vm = VersionManager()

    if not version:
        version = vm.get_current_version(name)
        if not version:
            click.echo(f"✗ No current version found for '{name}'", err=True)
            return

    try:
        vm.create_tag(tag_name, name, version)
        click.echo(f"✓ Tagged {name} v{version} as '{tag_name}'")
    except Exception as e:
        click.echo(f"✗ Error creating tag: {e}", err=True)


@cli.command("list")
def list_prompts():
    """List all prompts"""
    pv = PromptVersion()
    vm = VersionManager()

    prompts = pv.list_prompts()

    if not prompts:
        click.echo("No prompts found. Create one with: promptversion create <name>")
        return

    click.echo("Available prompts:")
    for prompt_name in prompts:
        try:
            prompt = pv.get(prompt_name)
            current_version = vm.get_current_version(prompt_name)
            tags = vm.get_tags(prompt_name)

            click.echo(f"  {prompt_name}")
            click.echo(f"    Version: {current_version or prompt.version}")
            if prompt.description:
                click.echo(f"    Description: {prompt.description}")
            if tags:
                tag_list = ", ".join([f"{k}:{v}" for k, v in tags.items()])
                click.echo(f"    Tags: {tag_list}")
        except Exception as e:
            click.echo(f"    Error loading: {e}")


@cli.command()
@click.argument("name")
def versions(name):
    """Show version history for a prompt"""
    vm = VersionManager()

    versions_data = vm.get_versions(name)

    if not versions_data["versions"]:
        click.echo(f"No version history for '{name}'")
        return

    click.echo(f"Version history for '{name}':")
    for version, info in sorted(
        versions_data["versions"].items(), key=lambda x: x[0], reverse=True
    ):
        current_marker = " (current)" if version == versions_data["current"] else ""
        click.echo(f"  {version}{current_marker}")
        click.echo(f"    Author: {info['author']}")
        click.echo(f"    Date: {info['created']}")
        click.echo(f"    Message: {info['message']}")
        if info.get("hash"):
            click.echo(f"    Hash: {info['hash']}")


@cli.command()
@click.argument("name")
@click.option("--version", "-v", help="Specific version to show")
@click.option("--vars", is_flag=True, help="Show available variables")
def show(name, version, vars):
    """Show prompt content"""
    pv = PromptVersion()

    try:
        prompt = pv.get(name, version)

        click.echo(f"Prompt: {prompt.name}")
        click.echo(f"Version: {prompt.version}")
        if prompt.description:
            click.echo(f"Description: {prompt.description}")

        if vars:
            click.echo("\nVariables:")
            for var_name, var_config in prompt.variables.items():
                if isinstance(var_config, dict):
                    default = var_config.get("default", "None")
                    var_type = var_config.get("type", "unknown")
                    desc = var_config.get("description", "")
                    click.echo(f"  {var_name}: {default} ({var_type})")
                    if desc:
                        click.echo(f"    {desc}")
                else:
                    click.echo(f"  {var_name}: {var_config}")

        click.echo("\nTemplate:")
        click.echo("-" * 40)
        click.echo(prompt.template)

    except Exception as e:
        click.echo(f"✗ Error showing prompt: {e}", err=True)


@cli.command()
@click.argument("name")
@click.option("--var", "-v", multiple=True, help="Variable in format key=value")
@click.option("--version", help="Specific version to test")
def test(name, var, version):
    """Test prompt rendering with variables"""
    pv = PromptVersion()

    # Parse variables
    variables = {}
    for var_pair in var:
        if "=" not in var_pair:
            click.echo(
                f"✗ Invalid variable format: {var_pair}. Use key=value", err=True
            )
            return
        key, value = var_pair.split("=", 1)
        variables[key] = value

    try:
        rendered = pv.render(name, variables, version)

        click.echo(f"Rendered prompt '{name}':")
        if variables:
            click.echo(f"Variables: {variables}")
        click.echo("-" * 40)
        click.echo(rendered)

    except Exception as e:
        click.echo(f"✗ Error rendering prompt: {e}", err=True)


if __name__ == "__main__":
    cli()
