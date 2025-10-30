"""
Configuration loader utility to centralize LLM config loading
"""
import yaml
import os
from pathlib import Path

def load_llm_config():
    """Load LLM configuration from config file"""
    # Get project root
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent
    config_path = project_root / "config" / "llm" / "openai.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config

def get_model_name():
    """Get the configured model name"""
    config = load_llm_config()
    return config.get('model', 'gpt-3.5-turbo')

def get_temperature():
    """Get the configured temperature"""
    config = load_llm_config()
    return config.get('temperature', 0.7)

def get_max_tokens():
    """Get the configured max tokens"""
    config = load_llm_config()
    return config.get('max_tokens', 4000)

def get_timeout():
    """Get the configured timeout"""
    config = load_llm_config()
    return config.get('timeout', 60)
