#!/usr/bin/env python3
"""
History management utilities for SimpleAnthropicCLI
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional

# History file path
CONFIG_DIR = os.path.expanduser("~/.simple_anthropic_cli")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")
CONVERSATIONS_DIR = os.path.join(CONFIG_DIR, "conversations")

def ensure_history_dirs():
    """Ensure all history-related directories exist."""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        logging.info(f"Created directory: {CONFIG_DIR}")
    
    if not os.path.exists(CONVERSATIONS_DIR):
        os.makedirs(CONVERSATIONS_DIR)
        logging.info(f"Created directory: {CONVERSATIONS_DIR}")

def load_history() -> List[Dict[str, Any]]:
    """Load chat history from file.
    
    Returns:
        List of history entries
    """
    ensure_history_dirs()
    
    if not os.path.exists(HISTORY_FILE):
        return []
    
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading history: {e}")
        return []

def save_history(history: List[Dict[str, Any]]) -> bool:
    """Save chat history to file.
    
    Args:
        history: List of history entries to save
        
    Returns:
        True if successful, False otherwise
    """
    ensure_history_dirs()
    
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        logging.info("History saved successfully")
        return True
    except Exception as e:
        logging.error(f"Error saving history: {e}")
        return False

def add_history_entry(user_message: str, assistant_message: str, model: str) -> bool:
    """Add a new entry to the history.
    
    Args:
        user_message: User's message
        assistant_message: Assistant's response
        model: Model used for this interaction
        
    Returns:
        True if successful, False otherwise
    """
    history = load_history()
    
    entry = {
        "user": user_message,
        "assistant": assistant_message,
        "model": model,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    history.append(entry)
    return save_history(history)

def save_conversation(messages: List[Dict[str, Any]], model: str, filename: Optional[str] = None) -> str:
    """Save a conversation to a file.
    
    Args:
        messages: List of message objects
        model: Model used for this conversation
        filename: Optional filename, generated if not provided
        
    Returns:
        Path to the saved file
    """
    ensure_history_dirs()
    
    if not filename:
        filename = f"conversation_{int(time.time())}.json"
    
    if not filename.endswith('.json'):
        filename += '.json'
    
    filepath = os.path.join(CONVERSATIONS_DIR, filename)
    
    try:
        # Include conversation metadata
        save_data = {
            "model": model,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": messages
        }
        
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)
            
        logging.info(f"Conversation saved to {filepath}")
        return filepath
    except Exception as e:
        logging.error(f"Error saving conversation: {e}")
        raise

def load_conversation(filename: str) -> Dict[str, Any]:
    """Load a conversation from a file.
    
    Args:
        filename: Name of the file to load
        
    Returns:
        Dictionary containing conversation data
    """
    ensure_history_dirs()
    
    if not filename.endswith('.json'):
        filename += '.json'
        
    filepath = os.path.join(CONVERSATIONS_DIR, filename)
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Conversation file not found: {filename}")
        
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading conversation: {e}")
        raise

def list_conversations() -> List[Dict[str, Any]]:
    """List all saved conversations.
    
    Returns:
        List of conversation metadata
    """
    ensure_history_dirs()
    
    conversations = []
    
    for filename in os.listdir(CONVERSATIONS_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(CONVERSATIONS_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    conversations.append({
                        "filename": filename,
                        "timestamp": data.get("timestamp", "Unknown"),
                        "model": data.get("model", "Unknown"),
                        "message_count": len(data.get("messages", [])),
                    })
            except Exception as e:
                logging.error(f"Error loading metadata for {filename}: {e}")
                conversations.append({
                    "filename": filename,
                    "timestamp": "Error loading metadata",
                    "model": "Unknown",
                    "message_count": 0,
                })
    
    # Sort by timestamp (newest first)
    return sorted(conversations, key=lambda x: x.get("timestamp", ""), reverse=True)