#!/usr/bin/env python3
"""
Setup-related command handlers for SimpleAnthropicCLI
"""

import os
import json
import time
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from utils.logging_utils import log_exception
from utils.security_utils import mask_api_key

class SetupCommands:
    """Setup and configuration commands for the SimpleAnthropicCLI."""
    
    def __init__(self, cli_instance):
        """Initialize with a reference to the CLI instance.
        
        Args:
            cli_instance: The AnthropicCLI instance
        """
        self.cli = cli_instance
    
    def handle_setup(self, arg):
        """Run setup wizard for various services"""
        args = arg.split()
        
        if args and args[0] == 'anthropic':
            self._setup_anthropic()
        elif args and args[0] == 'gmail':
            self._setup_gmail()
        elif args and args[0] == 'drive':
            self._setup_drive()
        elif args and args[0] == 'brave':
            self._setup_brave()
        else:
            self._setup_all()
    
    def _setup_all(self):
        """Run complete setup wizard"""
        print("\n\033[1;36m===== SimpleAnthropicCLI Setup Wizard =====\033[0m\n")
        print("This wizard will help you configure all services.")
        print("You can skip any section by pressing Enter at the prompts.\n")
        
        # Setup each service
        self._setup_anthropic()
        self._setup_gmail()
        self._setup_drive()
        self._setup_brave()
        
        # Reinitialize services with new configuration
        self.cli._initialize_services()
        
        print("\n\033[1;36m===== Setup Complete =====\033[0m\n")
        print("You can check the status of all services with the 'status' command.")
        print("You can re-run setup for individual services with 'setup <service>'.")
        print("  Example: setup gmail\n")
    
    def _setup_anthropic(self):
        """Setup Anthropic API"""
        print("\n\033[1;36m----- Anthropic API Setup -----\033[0m\n")
        
        # Check if API key is already set
        current_key = os.environ.get("ANTHROPIC_API_KEY")
        masked_key = mask_api_key(current_key) if current_key else "Not set"
        
        print(f"Current API Key: {masked_key}")
        
        # Prompt for new API key
        new_key = input("\nEnter your Anthropic API key (press Enter to keep current): ").strip()
        
        if new_key:
            # Set environment variable
            os.environ["ANTHROPIC_API_KEY"] = new_key
            
            # Update client
            self.cli.anthropic.api_key = new_key
            
            # Add to .env file
            self._update_env_file("ANTHROPIC_API_KEY", new_key)
            
            self.cli.print_message("Anthropic API key updated", "success")
        
        # Model selection
        print("\n\033[1;36mSelect Claude Model:\033[0m")
        for i, model in enumerate(self.cli.MODELS, 1):
            if model == self.cli.config['model']:
                print(f"  {i}. \033[1m{model}\033[0m (current)")
            else:
                print(f"  {i}. {model}")
        
        model_choice = input("\nEnter model number (press Enter to keep current): ").strip()
        
        if model_choice and model_choice.isdigit():
            idx = int(model_choice) - 1
            if 0 <= idx < len(self.cli.MODELS):
                self.cli.config["model"] = self.cli.MODELS[idx]
                self.cli.anthropic.model = self.cli.MODELS[idx]
                self.cli._save_config()
                self.cli.print_message(f"Model set to {self.cli.MODELS[idx]}", "success")
            else:
                self.cli.print_message("Invalid model selection", "error")
        
        # Extended thinking
        thinking_setting = self.cli.config.get("thinking_enabled", True)
        print(f"\n\033[1;36mExtended Thinking:\033[0m Currently {'enabled' if thinking_setting else 'disabled'}")
        thinking_choice = input("Enable extended thinking? (y/n, press Enter to keep current): ").strip().lower()
        
        if thinking_choice in ['y', 'yes']:
            self.cli.config["thinking_enabled"] = True
            self.cli.anthropic.thinking_enabled = True
            
            # Thinking budget
            current_budget = self.cli.config.get("thinking_budget", 16000)
            print(f"\nCurrent thinking budget: {current_budget} tokens")
            budget_input = input("Enter new thinking budget (press Enter to keep current): ").strip()
            
            if budget_input and budget_input.isdigit():
                budget = int(budget_input)
                self.cli.config["thinking_budget"] = budget
                self.cli.anthropic.thinking_budget = budget
                self.cli.print_message(f"Thinking budget set to {budget} tokens", "success")
                
        elif thinking_choice in ['n', 'no']:
            self.cli.config["thinking_enabled"] = False
            self.cli.anthropic.thinking_enabled = False
            self.cli.print_message("Extended thinking disabled", "success")
        
        # Tool use
        tools_setting = self.cli.config.get("use_tools", True)
        print(f"\n\033[1;36mTool Use (Function Calling):\033[0m Currently {'enabled' if tools_setting else 'disabled'}")
        tools_choice = input("Enable tool use? (y/n, press Enter to keep current): ").strip().lower()
        
        if tools_choice in ['y', 'yes']:
            self.cli.config["use_tools"] = True
            self.cli.print_message("Tool use enabled", "success")
        elif tools_choice in ['n', 'no']:
            self.cli.config["use_tools"] = False
            self.cli.print_message("Tool use disabled", "success")
        
        # Extended output (Claude 3.7 only)
        if "claude-3-7" in self.cli.config["model"]:
            extended_setting = self.cli.config.get("extended_output", False)
            print(f"\n\033[1;36mExtended Output (128k tokens):\033[0m Currently {'enabled' if extended_setting else 'disabled'}")
            extended_choice = input("Enable extended output? (y/n, press Enter to keep current): ").strip().lower()
            
            if extended_choice in ['y', 'yes']:
                self.cli.config["extended_output"] = True
                self.cli.anthropic.extended_output = True
                self.cli.print_message("Extended output enabled", "success")
            elif extended_choice in ['n', 'no']:
                self.cli.config["extended_output"] = False
                self.cli.anthropic.extended_output = False
                self.cli.print_message("Extended output disabled", "success")
        
        # Save configuration
        self.cli._save_config()
    
    def _setup_gmail(self):
        """Setup Gmail API"""
        print("\n\033[1;36m----- Gmail API Setup -----\033[0m\n")
        
        # Check if the Drive credentials path exists and use that if available
        drive_creds_path = self.cli.config.get("drive_credentials_path")
        if drive_creds_path and os.path.exists(os.path.expanduser(drive_creds_path)):
            # Use the same credentials as Drive since they can share OAuth credentials
            self.cli.config["gmail_credentials_path"] = drive_creds_path
            self.cli.print_message(f"Using existing Drive credentials: {drive_creds_path}", "success")
        
        # Current paths
        current_creds = self.cli.config.get("gmail_credentials_path", "~/.simple_anthropic_cli/credentials/gmail_credentials.json")
        current_token = self.cli.config.get("gmail_token_path", "~/.simple_anthropic_cli/credentials/gmail_token.json")
        
        print(f"Current credentials path: {current_creds}")
        print(f"Current token path: {current_token}")
        
        # Prompt for credentials file
        print("\nTo use Gmail, you need to set up OAuth credentials from Google Cloud Console.")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create an OAuth 2.0 Client ID")
        print("3. Download the credentials JSON file")
        print("4. Provide the path to the downloaded file below")
        
        new_creds = input("\nEnter path to Gmail credentials.json file (press Enter to keep current): ").strip()
        
        if new_creds:
            # Expand path and normalize
            new_creds = os.path.expanduser(new_creds)
            
            if not os.path.exists(new_creds):
                self.cli.print_message(f"File not found: {new_creds}", "error")
            else:
                # Update config to use the provided file directly
                self.cli.config["gmail_credentials_path"] = new_creds
                self.cli.print_message(f"Using Gmail credentials from: {new_creds}", "success")
        
        # Ask if they want to reset token
        reset_token = input("\nReset Gmail authentication token? (y/n): ").strip().lower()
        
        if reset_token in ['y', 'yes']:
            token_path = os.path.expanduser(self.cli.config["gmail_token_path"])
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                    self.cli.print_message("Gmail token deleted. You'll need to re-authenticate.", "success")
                except Exception as e:
                    log_exception(e, "Error deleting token")
                    self.cli.print_message(f"Error deleting token: {e}", "error")
            else:
                self.cli.print_message("Gmail token file not found. No action needed.", "success")
                
        # Save configuration
        self.cli._save_config()
        
        # Force authentication by initializing the Gmail service
        if os.path.exists(os.path.expanduser(self.cli.config["gmail_credentials_path"])):
            try:
                # Reinitialize Gmail service to trigger authentication flow
                from gmail_service import GmailService
                
                print(f"\n\033[1;36mInitializing Gmail service with authentication...\033[0m")
                gmail_service = GmailService(
                    credentials_path=os.path.expanduser(self.cli.config["gmail_credentials_path"]),
                    token_path=os.path.expanduser(self.cli.config["gmail_token_path"]),
                    force_refresh=True
                )
                
                # Update CLI's gmail service
                self.cli.gmail = gmail_service
                print(f"\033[32m✓\033[0m Gmail service initialized")
            except Exception as e:
                log_exception(e, "Error initializing Gmail service")
                self.cli.print_message(f"Error initializing Gmail service: {e}", "error")
    
    def _setup_drive(self):
        """Setup Google Drive API"""
        print("\n\033[1;36m----- Google Drive API Setup -----\033[0m\n")
        
        # Current paths
        current_creds = self.cli.config.get("drive_credentials_path", "~/.simple_anthropic_cli/credentials/drive_credentials.json")
        current_token = self.cli.config.get("drive_token_path", "~/.simple_anthropic_cli/credentials/drive_token.json")
        
        print(f"Current credentials path: {current_creds}")
        print(f"Current token path: {current_token}")
        
        # Prompt for credentials file
        print("\nTo use Google Drive, you need to set up OAuth credentials from Google Cloud Console.")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create an OAuth 2.0 Client ID")
        print("3. Download the credentials JSON file")
        print("4. Provide the path to the downloaded file below")
        
        new_creds = input("\nEnter path to Drive credentials.json file (press Enter to keep current): ").strip()
        
        if new_creds:
            # Expand path and normalize
            new_creds = os.path.expanduser(new_creds)
            
            if not os.path.exists(new_creds):
                self.cli.print_message(f"File not found: {new_creds}", "error")
            else:
                # Ensure credentials directory exists
                creds_dir = os.path.expanduser("~/.simple_anthropic_cli/credentials")
                os.makedirs(creds_dir, exist_ok=True)
                
                # Copy credentials to default location
                destination = os.path.join(creds_dir, "drive_credentials.json")
                try:
                    shutil.copy2(new_creds, destination)
                    self.cli.config["drive_credentials_path"] = destination
                    self.cli.print_message(f"Drive credentials copied to {destination}", "success")
                except Exception as e:
                    log_exception(e, "Error copying credentials")
                    self.cli.print_message(f"Error copying credentials: {e}", "error")
        
        # Ask if they want to reset token
        reset_token = input("\nReset Drive authentication token? (y/n): ").strip().lower()
        
        if reset_token in ['y', 'yes']:
            token_path = os.path.expanduser(self.cli.config["drive_token_path"])
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                    self.cli.print_message("Drive token deleted. You'll need to re-authenticate.", "success")
                except Exception as e:
                    log_exception(e, "Error deleting token")
                    self.cli.print_message(f"Error deleting token: {e}", "error")
            else:
                self.cli.print_message("Drive token file not found. No action needed.", "success")
        
        # Save configuration
        self.cli._save_config()
    
    def _setup_brave(self):
        """Setup Brave Search API"""
        print("\n\033[1;36m----- Brave Search API Setup -----\033[0m\n")
        
        # Check if API key is already set
        current_key = self.cli.config.get("brave_api_key") or os.environ.get("BRAVE_API_KEY")
        masked_key = mask_api_key(current_key) if current_key else "Not set"
        
        print(f"Current API Key: {masked_key}")
        print("\nTo use Brave Search, you need an API key from https://brave.com/api/")
        
        # Prompt for new API key
        new_key = input("\nEnter your Brave Search API key (press Enter to keep current): ").strip()
        
        if new_key:
            # Update config
            self.cli.config["brave_api_key"] = new_key
            
            # Update environment variable
            os.environ["BRAVE_API_KEY"] = new_key
            
            # Add to .env file
            self._update_env_file("BRAVE_API_KEY", new_key)
            
            self.cli.print_message("Brave Search API key updated", "success")
        
        # Save configuration
        self.cli._save_config()
    
    def handle_refresh(self, arg):
        """Refresh authentication tokens: refresh [gmail|drive] [--reset]"""
        args = arg.split()
        
        service = None
        reset = False
        
        # Parse arguments
        if args:
            service = args[0].lower()
            if len(args) > 1 and args[1] == '--reset':
                reset = True
        
        if service == 'gmail':
            self._refresh_gmail(reset)
        elif service == 'drive':
            self._refresh_drive(reset)
        else:
            self.cli.print_message("Usage: refresh [gmail|drive] [--reset]", "warning")
    
    def _refresh_gmail(self, reset=False):
        """Refresh Gmail authentication"""
        if not self.cli.gmail:
            self.cli.print_message("Gmail service not initialized", "error")
            return
        
        # If reset flag is set, delete token
        if reset:
            token_path = os.path.expanduser(self.cli.config["gmail_token_path"])
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                    self.cli.print_message("Gmail token deleted. Will re-authenticate.", "success")
                except Exception as e:
                    log_exception(e, "Error deleting token")
                    self.cli.print_message(f"Error deleting token: {e}", "error")
            else:
                self.cli.print_message("Gmail token file not found. Will create new token.", "success")
        
        try:
            self.cli.print_message("Refreshing Gmail authentication...", "info")
            
            # Reinitialize Gmail service
            creds_path = os.path.expanduser(self.cli.config["gmail_credentials_path"])
            token_path = os.path.expanduser(self.cli.config["gmail_token_path"])
            
            # Use force_refresh=True to ensure token is refreshed
            from gmail_service import GmailService
            self.cli.gmail = GmailService(
                credentials_path=creds_path,
                token_path=token_path,
                force_refresh=True
            )
            
            self.cli.print_message("Gmail authentication refreshed", "success")
            
        except Exception as e:
            log_exception(e, "Error refreshing Gmail authentication")
            self.cli.print_message(f"Error refreshing Gmail authentication: {e}", "error")
    
    def _refresh_drive(self, reset=False):
        """Refresh Drive authentication"""
        if not self.cli.drive:
            self.cli.print_message("Drive service not initialized", "error")
            return
        
        # If reset flag is set, delete token
        if reset:
            token_path = os.path.expanduser(self.cli.config["drive_token_path"])
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                    self.cli.print_message("Drive token deleted. Will re-authenticate.", "success")
                except Exception as e:
                    log_exception(e, "Error deleting token")
                    self.cli.print_message(f"Error deleting token: {e}", "error")
            else:
                self.cli.print_message("Drive token file not found. Will create new token.", "success")
        
        try:
            self.cli.print_message("Refreshing Drive authentication...", "info")
            
            # Reinitialize Drive service
            creds_path = os.path.expanduser(self.cli.config["drive_credentials_path"])
            token_path = os.path.expanduser(self.cli.config["drive_token_path"])
            
            # Use force_refresh=True to ensure token is refreshed
            from drive_service import DriveService
            self.cli.drive = DriveService(
                credentials_path=creds_path,
                token_path=token_path,
                force_refresh=True
            )
            
            self.cli.print_message("Drive authentication refreshed", "success")
            
        except Exception as e:
            log_exception(e, "Error refreshing Drive authentication")
            self.cli.print_message(f"Error refreshing Drive authentication: {e}", "error")
    
    def _update_env_file(self, key, value):
        """Update or create .env file with key=value pair"""
        # Determine .env file location
        env_file = os.path.expanduser("~/.simple_anthropic_cli/.env")
        env_dir = os.path.dirname(env_file)
        
        # Ensure directory exists
        os.makedirs(env_dir, exist_ok=True)
        
        content = {}
        
        # Read existing content if file exists
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle "export KEY=value" format
                        if line.startswith('export '):
                            line = line[7:]  # Remove 'export ' prefix
                        
                        # Split by first equals sign
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            k, v = parts
                            content[k.strip()] = v.strip()
        
        # Update or add key-value pair
        content[key] = value
        
        # Write back to file
        with open(env_file, 'w') as f:
            for k, v in content.items():
                f.write(f"{k}={v}\n")
        
        self.cli.print_message(f"Updated {key} in {env_file}", "success")