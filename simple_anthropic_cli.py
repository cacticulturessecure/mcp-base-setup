#!/usr/bin/env python3
"""
SimpleAnthropicCLI v4 - A CLI for chatting with Anthropic models with Gmail, Drive integration and function calling/tool use.
With .env file support for API keys.
"""

import os
import sys
import cmd
import argparse
import textwrap
import logging
from typing import Dict, List, Optional, Any, Union
import time
import pathlib

# Initialize logging first
from utils.logging_utils import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

# Import config utilities
from utils.config_utils import parse_env_file

# Look for .env file in multiple locations
env_paths = [
    os.path.join(os.getcwd(), '.env'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),
    os.path.expanduser('~/.simple_anthropic_cli/.env')
]

env_loaded = False
for env_path in env_paths:
    if os.path.exists(env_path):
        logger.info(f"Loading .env file from {env_path}")
        if parse_env_file(env_path):
            env_loaded = True
            logger.info(f"Successfully loaded environment from {env_path}")
            break

if not env_loaded:
    logger.warning("No .env file found. Please set required API keys manually.")

# Import utility modules
from utils.config_utils import load_config, save_config
from utils.history_utils import load_history, save_history
from utils.security_utils import mask_api_key

# Import command handlers
from commands.chat_commands import ChatCommands
from commands.email_commands import EmailCommands
from commands.extraction_commands import ExtractionCommands
from commands.drive_commands import DriveCommands
from commands.search_commands import SearchCommands
from commands.setup_commands import SetupCommands

# Import service modules
from gmail_service import GmailService
from drive_service import DriveService
from utils.anthropic_client_v2 import AnthropicClientV2
from brave_service import BraveSearchService

# Models available
MODELS = [
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-instant-1.2"
]

class AnthropicCLI(cmd.Cmd):
    """Interactive CLI for chatting with Anthropic models with Gmail, Drive integration and tool use."""
    
    # Override the default help headers
    doc_header = "Available commands (type help <command>):"
    misc_header = "Miscellaneous help topics:"
    undoc_header = "Undocumented commands:"
    ruler = "\033[90m-\033[0m"
    
    intro = """
    ╔══════════════════════════════════════════════════════╗
    ║ \033[1;36mWelcome to SimpleAnthropicCLI v4\033[0m                     ║
    ║                                                      ║
    ║ API keys are loaded from .env file automatically     ║
    ║                                                      ║
    ║ Type '\033[1mhelp\033[0m' for a list of commands                   ║
    ║ Type '\033[1mchat <message>\033[0m' to chat with Claude            ║
    ║ Type '\033[1memail_list\033[0m' to check your Gmail               ║
    ║ Type '\033[1mdrive_list\033[0m' to view your Drive files          ║
    ║ Type '\033[1mweb_search <query>\033[0m' to search the web         ║
    ║ Type '\033[1msetup\033[0m' to configure services                   ║
    ║ Type '\033[1mstatus\033[0m' to check service status                ║
    ║ Type '\033[1mquit\033[0m' to exit                                  ║
    ╚══════════════════════════════════════════════════════╝
    """
    prompt = "\033[1;36msimple-anthropic-v4>\033[0m "
    
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.history = load_history()
        
        # Get API key - already loaded from .env by load_dotenv()
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            print("\033[31m✘\033[0m ANTHROPIC_API_KEY not found in environment or .env file")
            key_input = input("Would you like to enter your ANTHROPIC_API_KEY now? (y/n): ")
            if key_input.lower() == 'y':
                anthropic_api_key = input("Enter your ANTHROPIC_API_KEY: ")
                os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key
                logger.info("ANTHROPIC_API_KEY set for this session")
            else:
                print("  Please add it to your .env file in the format: ANTHROPIC_API_KEY=your_api_key_here")
                sys.exit(1)
            
        self.anthropic = AnthropicClientV2(
            api_key=anthropic_api_key, 
            model=self.config["model"],
            temperature=self.config["temperature"],
            max_tokens=self.config["max_tokens"],
            thinking_enabled=self.config.get("thinking_enabled", True),
            thinking_budget=self.config.get("thinking_budget", 16000),
            extended_output=self.config.get("extended_output", False)
        )
        
        # Initialize services
        self.gmail = None
        self.drive = None
        self.brave = None
        self._initialize_services()
        
        # Current conversation
        self.current_conversation = []
        
        # Define tools for Claude
        self.tools = self._define_tools()
        
        # Initialize command handlers
        self.chat_commands = ChatCommands(self)
        self.email_commands = EmailCommands(self)
        self.extraction_commands = ExtractionCommands(self)
        self.drive_commands = DriveCommands(self)
        self.search_commands = SearchCommands(self)
        self.setup_commands = SetupCommands(self)
        
        # Set up the MODELS list for this instance
        self.MODELS = MODELS
    
    def _define_tools(self) -> List[Dict]:
        """Define tools that Claude can use."""
        return [
            {
                "name": "search_web",
                "description": "Search the web for information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of results to return (max 20)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_emails",
                "description": "Search for emails in Gmail",
                "input_schema": {
                    "type": "object", 
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query for emails"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of emails to return",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_files",
                "description": "Search for files in Google Drive",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string", 
                            "description": "The search query for files"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of files to return",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "create_draft_email",
                "description": "Create a draft email in Gmail",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Email recipient(s)"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content"
                        },
                        "cc": {
                            "type": "string",
                            "description": "CC recipients"
                        },
                        "bcc": {
                            "type": "string",
                            "description": "BCC recipients"
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "create_document",
                "description": "Create a new Google Doc",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Document title"
                        },
                        "content": {
                            "type": "string",
                            "description": "Document content"
                        }
                    },
                    "required": ["title", "content"]
                }
            }
        ]
    
    def _execute_tool(self, tool_name: str, parameters: Dict) -> Dict:
        """Execute a tool call from Claude."""
        logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")
        
        try:
            if tool_name == "search_web":
                if not self.brave:
                    return {"error": "Brave Search service not initialized. Run setup first."}
                
                results = self.brave.web_search(
                    query=parameters["query"],
                    count=parameters.get("count", 5),
                    offset=0
                )
                return {"results": results["web"]["results"]}
            
            elif tool_name == "search_emails":
                if not self.gmail:
                    return {"error": "Gmail service not initialized. Run setup first."}
                
                emails = self.gmail.list_emails(
                    query=parameters["query"],
                    max_results=parameters.get("max_results", 5)
                )
                return {"emails": emails}
            
            elif tool_name == "search_files":
                if not self.drive:
                    return {"error": "Drive service not initialized. Run setup first."}
                
                files = self.drive.list_files(
                    query=parameters["query"],
                    max_results=parameters.get("max_results", 10)
                )
                return {"files": files}
            
            elif tool_name == "create_draft_email":
                if not self.gmail:
                    return {"error": "Gmail service not initialized. Run setup first."}
                
                draft_id = self.gmail.create_draft(
                    to=parameters["to"],
                    subject=parameters["subject"],
                    body=parameters["body"],
                    cc=parameters.get("cc", ""),
                    bcc=parameters.get("bcc", "")
                )
                return {"draft_id": draft_id, "status": "success"}
            
            elif tool_name == "create_document":
                if not self.drive:
                    return {"error": "Drive service not initialized. Run setup first."}
                
                doc = self.drive.create_document(
                    name=parameters["title"],
                    content=parameters["content"]
                )
                return {
                    "document_id": doc["id"],
                    "title": doc["name"],
                    "link": doc.get("webViewLink", "Not available"),
                    "status": "success"
                }
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}: {e}")
            return {"error": f"Error executing tool {tool_name}: {str(e)}"}
    
    def _save_config(self):
        """Save configuration to file."""
        save_config(self.config)
    
    def _save_history(self):
        """Save chat history to file."""
        save_history(self.history)
    
    def _initialize_services(self):
        """Initialize Gmail, Drive, and Brave services."""
        # Check if credential files exist first
        gmail_creds_path = os.path.expanduser(self.config["gmail_credentials_path"])
        gmail_token_path = os.path.expanduser(self.config["gmail_token_path"])
        drive_creds_path = os.path.expanduser(self.config["drive_credentials_path"])
        drive_token_path = os.path.expanduser(self.config["drive_token_path"])
        
        # Initialize Gmail service
        if os.path.exists(gmail_creds_path):
            try:
                self.gmail = GmailService(
                    credentials_path=gmail_creds_path,
                    token_path=gmail_token_path
                )
                print("\033[32m✓\033[0m Gmail service initialized")
            except Exception as e:
                logger.error(f"Gmail service initialization failed: {e}")
                print(f"\033[31m×\033[0m Gmail service initialization failed: {e}")
                # If the Drive credentials exist, try using them instead
                if os.path.exists(drive_creds_path) and drive_creds_path != gmail_creds_path:
                    try:
                        print(f"\033[33m! Trying to use Drive credentials for Gmail...\033[0m")
                        self.gmail = GmailService(
                            credentials_path=drive_creds_path,
                            token_path=gmail_token_path
                        )
                        # Update config if successful
                        self.config["gmail_credentials_path"] = drive_creds_path
                        self._save_config()
                        print("\033[32m✓\033[0m Gmail service initialized with Drive credentials")
                    except Exception as e2:
                        logger.error(f"Gmail service initialization with Drive credentials failed: {e2}")
                        print(f"\033[31m×\033[0m Gmail service initialization with Drive credentials failed: {e2}")
                        self.gmail = None
                else:
                    self.gmail = None
        else:
            logger.warning(f"Gmail credentials file not found: {gmail_creds_path}")
            print(f"\033[33m! Gmail service not initialized: Credentials file not found\033[0m")
            # If the Drive credentials exist, try using them instead
            if os.path.exists(drive_creds_path):
                try:
                    print(f"\033[33m! Trying to use Drive credentials for Gmail...\033[0m")
                    self.gmail = GmailService(
                        credentials_path=drive_creds_path,
                        token_path=gmail_token_path
                    )
                    # Update config if successful
                    self.config["gmail_credentials_path"] = drive_creds_path
                    self._save_config()
                    print("\033[32m✓\033[0m Gmail service initialized with Drive credentials")
                except Exception as e:
                    logger.error(f"Gmail service initialization with Drive credentials failed: {e}")
                    print(f"\033[31m×\033[0m Gmail service initialization with Drive credentials failed: {e}")
                    self.gmail = None
            else:
                self.gmail = None
        
        # Initialize Drive service
        if os.path.exists(drive_creds_path):
            try:
                self.drive = DriveService(
                    credentials_path=drive_creds_path,
                    token_path=drive_token_path
                )
                print("\033[32m✓\033[0m Drive service initialized")
            except Exception as e:
                logger.error(f"Drive service initialization failed: {e}")
                print(f"\033[31m×\033[0m Drive service initialization failed: {e}")
                self.drive = None
        else:
            logger.warning(f"Drive credentials file not found: {drive_creds_path}")
            print(f"\033[33m! Drive service not initialized: Credentials file not found\033[0m")
            self.drive = None
            
        # Initialize Brave service
        brave_api_key = self.config.get("brave_api_key") or os.environ.get("BRAVE_API_KEY")
        if brave_api_key:
            try:
                self.brave = BraveSearchService(api_key=brave_api_key)
                print("\033[32m✓\033[0m Brave Search service initialized")
            except Exception as e:
                logger.error(f"Brave Search service initialization failed: {e}")
                print(f"\033[31m×\033[0m Brave Search service initialization failed: {e}")
                self.brave = None
        else:
            logger.warning("Brave API key not provided")
            print("\033[33m! Brave Search service not initialized: API key not provided\033[0m")
            self.brave = None
    
    def _print_wrapped(self, text, prefix=""):
        """Print text with word wrapping."""
        width = os.get_terminal_size().columns - len(prefix)
        for line in text.split("\n"):
            wrapped = textwrap.fill(line, width=width, subsequent_indent=prefix)
            print(f"{prefix}{wrapped}")
    
    def print_message(self, message: str, msg_type: str = "info", end: str = "\n"):
        """Print a formatted message.
        
        Args:
            message: Message to print
            msg_type: Message type (info, success, warning, error)
            end: Line ending character
        """
        if msg_type == "success":
            print(f"\033[32m✓\033[0m {message}", end=end)
        elif msg_type == "warning":
            print(f"\033[33m! {message}\033[0m", end=end)
        elif msg_type == "error":
            print(f"\033[31m✘\033[0m {message}", end=end)
        else:  # info
            print(f"\033[90m{message}\033[0m", end=end)
    
    # Command handlers
    def do_chat(self, arg):
        """Chat with Claude: chat <message>"""
        self.chat_commands.handle_chat(arg)
    
    def do_thinking(self, arg):
        """Enable, disable, or configure extended thinking: thinking [on|off|show|hide|budget <number>]"""
        self.chat_commands.handle_thinking(arg)
    
    def do_tools(self, arg):
        """Enable, disable, or list available tools: tools [on|off|list]"""
        self.chat_commands.handle_tools(arg)
    
    def do_clear(self, arg):
        """Clear the current conversation"""
        self.chat_commands.handle_clear(arg)
        
    def do_reset(self, arg):
        """Reset the CLI state when encountering tool use errors"""
        self.chat_commands.handle_reset(arg)
    
    def do_model(self, arg):
        """Set or view the current model: model [model_name]"""
        if not arg:
            print(f"\n\033[1;36mCurrent model:\033[0m \033[1m{self.config['model']}\033[0m")
            print("\n\033[1;36mAvailable models:\033[0m")
            for model in MODELS:
                if model == self.config['model']:
                    print(f"  \033[32m•\033[0m \033[1m{model}\033[0m (current)")
                else:
                    print(f"  • {model}")
            return
        
        if arg in MODELS:
            self.config["model"] = arg
            self.anthropic.model = arg
            self._save_config()
            print(f"\033[32m✓\033[0m Model set to \033[1m{arg}\033[0m")
        else:
            print(f"\033[31m✘\033[0m Unknown model: \033[1m{arg}\033[0m")
            print("\n\033[1;36mAvailable models:\033[0m")
            for model in MODELS:
                print(f"  • {model}")
    
    def do_extended_output(self, arg):
        """Enable or disable extended output (128k tokens): extended_output [on|off]"""
        if not arg:
            # Show current extended output configuration
            enabled = self.config.get("extended_output", False)
            
            print("\n\033[1;36mExtended Output Configuration:\033[0m")
            print(f"  Status: {'Enabled' if enabled else 'Disabled'}")
            return
        
        cmd = arg.lower()
        
        if cmd == "on":
            if "claude-3-7" not in self.config["model"]:
                print("\033[33m! Extended output is only available with Claude 3.7 models.\033[0m")
                print("  Please select claude-3-7-sonnet-20250219 using the model command.")
                return
                
            self.config["extended_output"] = True
            self.anthropic.extended_output = True
            print("\033[32m✓\033[0m Extended output (128k tokens) enabled")
        
        elif cmd == "off":
            self.config["extended_output"] = False
            self.anthropic.extended_output = False
            print("\033[32m✓\033[0m Extended output disabled")
        
        else:
            print("\033[33m! Usage: extended_output [on|off]\033[0m")
        
        # Save configuration
        self._save_config()
    
    def do_save_conversation(self, arg):
        """Save the current conversation to a file: save_conversation [filename]"""
        self.chat_commands.handle_save_conversation(arg)
    
    def do_load_conversation(self, arg):
        """Load a saved conversation: load_conversation <filename>"""
        self.chat_commands.handle_load_conversation(arg)
        
    def do_list_conversations(self, arg):
        """List saved conversations: list_conversations"""
        self.chat_commands.handle_list_conversations(arg)
        
    # Email commands
    def do_gmail(self, arg):
        """Gmail service commands: gmail [setup|refresh]"""
        args = arg.split()
        cmd = args[0].lower() if args else ""
        
        if cmd == "setup":
            self.setup_commands.handle_setup("gmail")
        elif cmd == "refresh":
            reset_flag = "--reset" if len(args) > 1 and args[1] == "--reset" else ""
            self.setup_commands.handle_refresh(f"gmail {reset_flag}")
        else:
            self.print_message("Usage: gmail [setup|refresh [--reset]]", "warning")
    
    def do_email_list(self, arg):
        """List recent emails: email_list [query]"""
        self.email_commands.handle_email_list(arg)
    
    def do_email_read(self, arg):
        """Read an email by ID: email_read <email_id>"""
        self.email_commands.handle_email_read(arg)
    
    def do_email_compose(self, arg):
        """Compose an email interactively"""
        self.email_commands.handle_email_compose(arg)
    
    def do_email_send(self, arg):
        """Send an email: email_send <to> <subject> <body>"""
        self.email_commands.handle_email_send(arg)
    
    def do_email_drafts(self, arg):
        """List and manage email drafts: email_drafts [send <draft_id> | view <draft_id>]"""
        self.email_commands.handle_email_drafts(arg)
    
    # Extraction commands
    def do_extract(self, arg):
        """Extract and edit message segments: extract <message_index> [email|document|save]"""
        self.extraction_commands.handle_extract(arg)
        
    # Drive commands
    def do_drive(self, arg):
        """Drive service commands: drive [setup|refresh]"""
        args = arg.split()
        cmd = args[0].lower() if args else ""
        
        if cmd == "setup":
            self.setup_commands.handle_setup("drive")
        elif cmd == "refresh":
            reset_flag = "--reset" if len(args) > 1 and args[1] == "--reset" else ""
            self.setup_commands.handle_refresh(f"drive {reset_flag}")
        else:
            self.print_message("Usage: drive [setup|refresh [--reset]]", "warning")
    
    def do_drive_list(self, arg):
        """List files on Google Drive: drive_list [query]"""
        self.drive_commands.handle_drive_list(arg)
    
    def do_drive_download(self, arg):
        """Download a file from Google Drive: drive_download <file_id> [output_path]"""
        self.drive_commands.handle_drive_download(arg)
    
    def do_drive_create(self, arg):
        """Create a document on Google Drive: drive_create <name> <content>"""
        self.drive_commands.handle_drive_create(arg)
    
    def do_drive_shared(self, arg):
        """List files shared with you: drive_shared [max_results]"""
        self.drive_commands.handle_drive_shared(arg)
    
    def do_drive_share(self, arg):
        """Share a file with another user: drive_share <file_id> <email> [role]"""
        self.drive_commands.handle_drive_share(arg)
    
    # Search commands
    def do_brave(self, arg):
        """Brave Search service commands: brave [setup]"""
        if arg.strip().lower() == "setup":
            self.setup_commands.handle_setup("brave")
        else:
            self.print_message("Usage: brave [setup]", "warning")
    
    def do_web_search(self, arg):
        """Search the web: web_search <query> [--count=<n>]"""
        self.search_commands.handle_web_search(arg)
    
    def do_local_search(self, arg):
        """Search your documents and emails: local_search <query>"""
        self.search_commands.handle_local_search(arg)
        
    # Setup and refresh commands
    def do_setup(self, arg):
        """Run setup wizard for various services: setup [anthropic|gmail|drive|brave]"""
        self.setup_commands.handle_setup(arg)
    
    def do_refresh(self, arg):
        """Refresh authentication tokens: refresh [gmail|drive] [--reset]"""
        self.setup_commands.handle_refresh(arg)
    
    def do_config(self, arg):
        """View or change configuration: config [setting] [value]"""
        args = arg.split()
        
        if not args:
            print("\n\033[1;36mCurrent configuration:\033[0m")
            for key, value in self.config.items():
                # Mask API keys for security
                if 'api_key' in key.lower():
                    value = mask_api_key(str(value))
                print(f"  \033[1m{key}\033[0m: {value}")
            return
        
        if len(args) == 1:
            key = args[0]
            if key in self.config:
                value = self.config[key]
                # Mask API keys for security
                if 'api_key' in key.lower():
                    value = mask_api_key(str(value))
                print(f"{key}: {value}")
            else:
                print(f"Unknown setting: {key}")
            return
        
        key, value = args[0], args[1]
        
        if key not in self.config:
            print(f"Unknown setting: {key}")
            return
        
        # Convert value to the right type
        if key == "temperature":
            try:
                value = float(value)
            except ValueError:
                print("Temperature must be a float")
                return
        elif key in ["max_tokens", "thinking_budget"]:
            try:
                value = int(value)
            except ValueError:
                print(f"{key} must be an integer")
                return
        elif key in ["thinking_enabled", "show_thinking", "use_tools", "extended_output"]:
            if value.lower() in ["true", "yes", "on", "1"]:
                value = True
            elif value.lower() in ["false", "no", "off", "0"]:
                value = False
            else:
                print(f"{key} must be true or false")
                return
        
        self.config[key] = value
        self._save_config()
        
        # Update client if needed
        if key == "model":
            self.anthropic.model = value
        elif key == "temperature":
            self.anthropic.temperature = value
        elif key == "max_tokens":
            self.anthropic.max_tokens = value
        elif key == "thinking_enabled":
            self.anthropic.thinking_enabled = value
        elif key == "thinking_budget":
            self.anthropic.thinking_budget = value
        elif key == "extended_output":
            self.anthropic.extended_output = value
        
        print(f"\033[32m✓\033[0m Set {key} to {value}")
    
    def do_status(self, arg):
        """Check the status of all services"""
        print("\n\033[1;36mService Status:\033[0m")
        
        # Anthropic API
        if self.anthropic:
            print(f"  \033[32m✓\033[0m Anthropic API: Connected")
            print(f"    - Model: \033[1m{self.config['model']}\033[0m")
            print(f"    - Temperature: {self.config['temperature']}")
            print(f"    - Max tokens: {self.config['max_tokens']}")
            thinking = self.config.get("thinking_enabled", True)
            print(f"    - Extended thinking: {'Enabled' if thinking else 'Disabled'}")
            if thinking:
                print(f"    - Thinking budget: {self.config.get('thinking_budget', 16000)} tokens")
            tools = self.config.get("use_tools", True)
            print(f"    - Tool use: {'Enabled' if tools else 'Disabled'}")
            extended = self.config.get("extended_output", False)
            print(f"    - Extended output: {'Enabled' if extended else 'Disabled'}")
        else:
            print(f"  \033[31m✘\033[0m Anthropic API: Not connected")
        
        # Gmail service
        if self.gmail:
            print(f"  \033[32m✓\033[0m Gmail: Connected")
            print(f"    - Credentials: \033[1m{self.config['gmail_credentials_path']}\033[0m")
            print(f"    - Token: \033[1m{self.config['gmail_token_path']}\033[0m")
        else:
            print(f"  \033[31m✘\033[0m Gmail: Not connected")
        
        # Drive service
        if self.drive:
            print(f"  \033[32m✓\033[0m Google Drive: Connected")
            print(f"    - Credentials: \033[1m{self.config['drive_credentials_path']}\033[0m")
            print(f"    - Token: \033[1m{self.config['drive_token_path']}\033[0m")
        else:
            print(f"  \033[31m✘\033[0m Google Drive: Not connected")
        
        # Brave Search service
        if self.brave:
            print(f"  \033[32m✓\033[0m Brave Search: Connected")
            masked_key = mask_api_key(self.config['brave_api_key'])
            print(f"    - API Key: {masked_key}")
        else:
            print(f"  \033[31m✘\033[0m Brave Search: Not connected")
        
        # System status
        print(f"\n\033[1;36mSystem Status:\033[0m")
        logger_status = "Enabled" if logging.getLogger().isEnabledFor(logging.INFO) else "Disabled"
        print(f"  - Logging: {logger_status}")
        print(f"  - Log file: {os.path.join(os.path.expanduser('~/.simple_anthropic_cli/logs'), 'cli.log')}")
        print(f"  - Configuration: {os.path.expanduser('~/.simple_anthropic_cli/config.json')}")
        
        print()
    
    def do_quit(self, arg):
        """Exit the CLI"""
        self._save_history()
        print("\n\033[1;36mGoodbye!\033[0m")
        return True
    
    def do_exit(self, arg):
        """Exit the CLI"""
        return self.do_quit(arg)
    
    # Default handler
    def default(self, line):
        """Default handler: treat as chat message"""
        return self.do_chat(line)
    
    # Help handler
    def do_help(self, arg):
        """List available commands or get help for a specific command"""
        if arg:
            # Use default help for specific commands
            super().do_help(arg)
        else:
            # Custom help display
            print("\n\033[1;36mSimpleAnthropicCLI v4 Help\033[0m")
            print("\n\033[1mChat Commands:\033[0m")
            print("  \033[1mchat\033[0m <message>     Chat with Claude")
            print("  \033[1mmodel\033[0m               View or change the current Claude model")
            print("  \033[1mclear\033[0m               Clear the current conversation")
            print("  \033[1mreset\033[0m               Reset CLI state (use when tool errors occur)")
            
            print("\n\033[1mConversation Management:\033[0m")
            print("  \033[1msave_conversation\033[0m [filename]   Save the current conversation")
            print("  \033[1mlist_conversations\033[0m             List all saved conversations")
            print("  \033[1mload_conversation\033[0m <filename>   Load a saved conversation")
            print("  \033[1mextract\033[0m <message_index>       Extract content from a conversation message")
            
            print("\n\033[1mClaude Features:\033[0m")
            print("  \033[1mthinking\033[0m [on|off|budget <n>|show|hide]  Configure extended thinking")
            print("  \033[1mtools\033[0m [on|off|list]  Configure tool use (function calling)")
            print("  \033[1mextended_output\033[0m [on|off]  Configure extended output (128k tokens)")
            
            print("\n\033[1mEmail Commands:\033[0m")
            print("  \033[1mgmail\033[0m [setup|refresh]        Gmail service configuration")
            print("  \033[1memail_list\033[0m [query]            List recent emails")
            print("  \033[1memail_read\033[0m <email_id>         Read an email by ID")
            print("  \033[1memail_compose\033[0m                 Compose an email interactively")
            print("  \033[1memail_send\033[0m <to> <subj> <body> Send a quick email")
            print("  \033[1memail_drafts\033[0m [send|view <id>] Manage email drafts")
            
            print("\n\033[1mDrive Commands:\033[0m")
            print("  \033[1mdrive\033[0m [setup|refresh]        Drive service configuration")
            print("  \033[1mdrive_list\033[0m [query]            List files on Google Drive")
            print("  \033[1mdrive_download\033[0m <id> [path]    Download a file from Drive")
            print("  \033[1mdrive_create\033[0m [name] [content] Create a document on Drive")
            print("  \033[1mdrive_shared\033[0m [max_results]    List files shared with you")
            print("  \033[1mdrive_share\033[0m <id> <email>      Share a file with someone")
            
            print("\n\033[1mSearch Commands:\033[0m")
            print("  \033[1mbrave\033[0m [setup]                Brave Search service configuration")
            print("  \033[1mweb_search\033[0m <query>            Search the web with Brave")
            print("  \033[1mlocal_search\033[0m <query>          Search emails and documents")
            
            print("\n\033[1mSetup & Configuration:\033[0m")
            print("  \033[1msetup\033[0m               Run the setup wizard")
            print("  \033[1mstatus\033[0m              Check service status")
            print("  \033[1mconfig\033[0m              View or change configuration settings")
            
            print("\n\033[1mOther Commands:\033[0m")
            print("  \033[1mhelp\033[0m [command]      Show this help message or help for a specific command")
            print("  \033[1mquit\033[0m or \033[1mexit\033[0m      Exit the CLI")
            
            print("\n\033[90mFor detailed help on any command, type: help <command>\033[0m")
            print("\033[90mYou can also just type your message directly to chat with Claude\033[0m")
            print()

def validate_env_file():
    """Validate that required keys exist in .env file."""
    required_keys = ["ANTHROPIC_API_KEY"]
    recommended_keys = ["BRAVE_API_KEY", "GOOGLE_API_KEY"]
    
    missing_required = [key for key in required_keys if not os.environ.get(key)]
    missing_recommended = [key for key in recommended_keys if not os.environ.get(key)]
    
    if missing_required:
        print("\033[31m✘ Error:\033[0m The following required API keys are missing:")
        for key in missing_required:
            print(f"  - {key}")
        
        # For each missing required key, prompt the user to enter it
        for key in missing_required:
            prompt_response = input(f"\nWould you like to enter your {key} now? (y/n): ")
            if prompt_response.lower() == 'y':
                api_key = input(f"Enter your {key}: ")
                os.environ[key] = api_key
                print(f"✓ {key} set for this session")
            else:
                print(f"\nPlease add {key} to your .env file in the format: {key}=your_key_here")
                return False
        
    if missing_recommended:
        print("\033[33m! Warning:\033[0m The following recommended API keys are missing:")
        for key in missing_recommended:
            print(f"  - {key}")
        print("\nSome features may not work without these keys.")
    
    return len([key for key in required_keys if not os.environ.get(key)]) == 0

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="SimpleAnthropicCLI v4")
    parser.add_argument("--api-key", help="Anthropic API key")
    parser.add_argument("--model", help="Model to use", choices=MODELS)
    parser.add_argument("--setup", action="store_true", help="Run setup wizard on startup")
    parser.add_argument("--gmail-creds", help="Path to Gmail credentials.json")
    parser.add_argument("--gmail-token", help="Path to Gmail token.json")
    parser.add_argument("--drive-creds", help="Path to Drive credentials.json")
    parser.add_argument("--drive-token", help="Path to Drive token.json")
    parser.add_argument("--brave-api-key", help="Brave Search API key")
    parser.add_argument("--no-thinking", action="store_true", help="Disable extended thinking")
    parser.add_argument("--no-tools", action="store_true", help="Disable tool use")
    parser.add_argument("--extended-output", action="store_true", help="Enable extended output (128k tokens)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Set up logging based on arguments
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level=log_level, console_output=args.debug)
    
    # Set API key from args or .env file
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
        logger.info("Using API key from command line arguments")
    # Check for API key and validate other env vars
    elif not validate_env_file():
        logger.error("Required API keys missing and not provided interactively")
        return 1
    
    # Initialize CLI
    cli = AnthropicCLI()
    
    # Override model if specified
    if args.model:
        cli.config["model"] = args.model
        cli.anthropic.model = args.model
    
    # Override paths if specified
    if args.gmail_creds:
        cli.config["gmail_credentials_path"] = os.path.abspath(args.gmail_creds)
    if args.gmail_token:
        cli.config["gmail_token_path"] = os.path.abspath(args.gmail_token)
    if args.drive_creds:
        cli.config["drive_credentials_path"] = os.path.abspath(args.drive_creds)
    if args.drive_token:
        cli.config["drive_token_path"] = os.path.abspath(args.drive_token)
    if args.brave_api_key:
        cli.config["brave_api_key"] = args.brave_api_key
    
    # Set thinking, tools, and extended output flags
    if args.no_thinking:
        cli.config["thinking_enabled"] = False
        cli.anthropic.thinking_enabled = False
    if args.no_tools:
        cli.config["use_tools"] = False
    if args.extended_output:
        if "claude-3-7" in cli.config["model"]:
            cli.config["extended_output"] = True
            cli.anthropic.extended_output = True
        else:
            print("\033[33m! Extended output is only available with Claude 3.7 models. Ignoring flag.\033[0m")
    
    # Save any changes to config
    cli._save_config()
    
    # Re-initialize services if paths were changed
    if args.gmail_creds or args.gmail_token or args.drive_creds or args.drive_token or args.brave_api_key:
        cli._initialize_services()
    
    # Run setup wizard if requested
    if args.setup:
        cli.setup_commands.handle_setup("")
    
    # Print a welcome banner
    os.system('clear' if os.name == 'posix' else 'cls')
    print("\033[1;36m" + "="*60 + "\033[0m")
    print("\033[1;36m    SimpleAnthropicCLI v4.0.0\033[0m")
    print("\033[1;36m" + "="*60 + "\033[0m")
    print("\n\033[90mType 'help' for a list of commands, 'status' to check service status\033[0m\n")
    
    # Start CLI
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\n\033[1;36mGoodbye!\033[0m")
        return 0
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        print(f"\033[31m✘ Error:\033[0m {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())