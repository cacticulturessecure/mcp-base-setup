#!/usr/bin/env python3
"""
Configuration utilities for SimpleAnthropicCLI
"""

import os
import json
import logging
import re
from typing import Dict, Any

# Default configuration values
DEFAULT_CONFIG = {
    "model": "claude-3-7-sonnet-20250219",
    "temperature": 0.7,
    "max_tokens": 4000,
    "thinking_enabled": True,
    "thinking_budget": 16000,
    "use_tools": True,
    "extended_output": False,
    # Google credentials paths
    # Use the successful Drive path for both services
    "gmail_credentials_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/gcp-oauth.keys.json",
    "gmail_token_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/token.json",
    "drive_credentials_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/gcp-oauth.keys.json",
    "drive_token_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/token.json",
    # Brave API key
    "brave_api_key": os.environ.get("BRAVE_API_KEY", ""),
}

# Setup paths
CONFIG_DIR = os.path.expanduser("~/.simple_anthropic_cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def parse_env_file(env_file_path):
    """Parse .env file that may contain 'export' statements.
    
    Args:
        env_file_path: Path to the .env file
        
    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(env_file_path):
        return False
        
    try:
        with open(env_file_path, 'r') as f:
            lines = f.readlines()
            
        # Process each line
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Handle lines with export statements
            if line.startswith('export '):
                line = line[7:]  # Remove 'export ' prefix
                
            # Parse key-value pairs
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                    
                # Set environment variable
                os.environ[key] = value
                logging.debug(f"Set environment variable: {key}")
        
        return True
    except Exception as e:
        logging.error(f"Error parsing .env file: {e}")
        return False

def ensure_config_dirs():
    """Ensure all configuration directories exist."""
    dirs = [
        CONFIG_DIR,
        os.path.join(CONFIG_DIR, "credentials"),
        os.path.join(CONFIG_DIR, "conversations"),
        os.path.join(CONFIG_DIR, "exports")
    ]
    
    for directory in dirs:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                logging.info(f"Created directory: {directory}")
            except Exception as e:
                logging.error(f"Error creating directory {directory}: {e}")
                raise

def load_config() -> Dict[str, Any]:
    """Load configuration from file or create default if it doesn't exist.
    
    Returns:
        Dict containing configuration settings
    """
    # Ensure config directory exists
    ensure_config_dirs()
    
    if not os.path.exists(CONFIG_FILE):
        # Create default config
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            logging.info(f"Created default configuration at {CONFIG_FILE}")
            return DEFAULT_CONFIG
        except Exception as e:
            logging.error(f"Error creating default config: {e}")
            return DEFAULT_CONFIG
    
    # Load existing config
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Update with any missing default keys
            updated = False
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
                    updated = True
            
            # Save if we added any missing keys
            if updated:
                save_config(config)
                logging.info("Updated config with missing default values")
            
            return config
    except Exception as e:
        logging.error(f"Error loading config: {e}. Using defaults.")
        return DEFAULT_CONFIG

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file.
    
    Args:
        config: Dictionary containing configuration to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logging.info("Configuration saved successfully")
        return True
    except Exception as e:
        logging.error(f"Error saving config: {e}")
        return False

def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific config value.
    
    Args:
        key: Configuration key to retrieve
        default: Default value if key doesn't exist
        
    Returns:
        Configuration value or default
    """
    config = load_config()
    return config.get(key, default)