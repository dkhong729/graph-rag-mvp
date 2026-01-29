"""
PromptVersion: Simple Prompt Version Control for AI Development

A lightweight tool for managing AI prompts with version control,
templating, and variable injection.
"""

from .core import PromptVersion, Prompt
from .version_manager import VersionManager

__version__ = "0.1.0"
__author__ = "Nagarjun Srinivasan"
__email__ = "nag@example.com"  # Update with your real email

__all__ = ["PromptVersion", "Prompt", "VersionManager"]
