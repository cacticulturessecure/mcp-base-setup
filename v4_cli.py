#!/usr/bin/env python3
"""
SimpleAnthropicCLI v3 - A CLI for chatting with Anthropic models with Gmail, Drive integration and function calling/tool use.
With .env file support for API keys.
"""

import os
import sys
import json
import time
import cmd
import argparse
from typing import Dict, List, Optional, Any, Union
import textwrap
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Local imports
from gmail_service import GmailService
from drive_service import DriveService
from anthropic_client import AnthropicClient
from brave_service import BraveSearchService

CONFIG_DIR = os.path.expanduser("~/.simple_anthropic_cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")

# Default configuration
# Note: API keys are loaded from .env file via load_dotenv()
DEFAULT_CONFIG = {
    "model": "claude-3-7-sonnet-20250219",
    "temperature": 0.7,
    "max_tokens": 4000,
    "thinking_enabled": True,
    "thinking_budget": 16000,
    "use_tools": True,
    "extended_output": False,
    "gmail_credentials_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/gcp-oauth.keys.json",
    "gmail_token_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/token.json",
    "drive_credentials_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/gcp-oauth.keys.json",
    "drive_token_path": "/home/tails/TERMINAL_CLAUDE_PROJECTS/servers/phase1-gmail/token.json",
    # API keys are now loaded directly from environment variables (from .env)
    "brave_api_key": os.environ.get("BRAVE_API_KEY", "")
}

MODELS = [
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-instant-1.2"
]

class AnthropicClientV2:
    """Enhanced client for interacting with Anthropic's Claude API with tool use and thinking modes."""
    
    API_URL = "https://api.anthropic.com/v1/messages"
    
    def __init__(self, api_key: str, model: str = "claude-3-7-sonnet-20250219", 
                 temperature: float = 0.7, max_tokens: int = 4000,
                 thinking_enabled: bool = True, thinking_budget: int = 16000,
                 extended_output: bool = False):
        """Initialize the Anthropic client with extended thinking support.
        
        Args:
            api_key: Anthropic API key
            model: Model name to use
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in the response
            thinking_enabled: Whether to enable extended thinking
            thinking_budget: Token budget for extended thinking
            extended_output: Whether to enable extended output (128k)
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking_enabled = thinking_enabled
        self.thinking_budget = thinking_budget
        self.extended_output = extended_output
    
    def send_message(self, messages: List[Dict], stream: bool = False, tools: List[Dict] = None) -> Union[str, Dict]:
        """Send a message to Claude and get a response.
        
        Args:
            messages: List of message objects with role and content
            stream: Whether to stream the response
            tools: List of tool definitions if using tools
        
        Returns:
            Claude's response text or full response object
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Add beta header for extended output if enabled
        if self.extended_output:
            headers["anthropic-beta"] = "output-128k-2025-02-19"
        
        # Format messages for Anthropic API
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Build request payload
        data = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream
        }
        
        # Add thinking configuration if enabled
        if self.thinking_enabled:
            # Temperature must be 1.0 when thinking is enabled
            data["temperature"] = 1.0  
            data["thinking"] = {
                "type": "enabled",
                "budget_tokens": min(self.thinking_budget, self.max_tokens - 100)
            }
        
        # Add tools if provided
        if tools:
            data["tools"] = tools
        
        # Make API request
        response = requests.post(
            self.API_URL,
            headers=headers,
            json=data,
            stream=stream
        )
        
        # Handle errors
        if response.status_code != 200:
            error_msg = f"API error {response.status_code}: {response.text}"
            raise Exception(error_msg)
        
        if stream:
            return response
        
        # Parse response
        result = response.json()
        
        # Check if we want to return the full response or just the text
        if self.thinking_enabled:
            # Return the full response including thinking and content blocks
            return result
        else:
            # Just return the text from the first content block
            return result["content"][0]["text"]
    
    def get_completion(self, prompt: str) -> str:
        """Get a completion from Claude for a single prompt.
        
        This is a convenience method for one-off prompts.
        
        Args:
            prompt: The text prompt
        
        Returns:
            Claude's response text
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.send_message(messages)
        
        if isinstance(response, dict) and "content" in response:
            # Extract just the text content from the response
            for block in response["content"]:
                if block["type"] == "text":
                    return block["text"]
            return "No text content found in response"
        
        return response

class AnthropicCLI(cmd.Cmd):
    """Interactive CLI for chatting with Anthropic models with Gmail, Drive integration and tool use."""
    
    # Override the default help headers
    doc_header = "Available commands (type help <command>):"
    misc_header = "Miscellaneous help topics:"
    undoc_header = "Undocumented commands:"
    ruler = "\033[90m-\033[0m"
    
    intro = """
    ╔══════════════════════════════════════════════════════╗
    ║ \033[1;36mWelcome to SimpleAnthropicCLI v3\033[0m                     ║
    ║                                                      ║
    ║ API keys are loaded from .env file automatically     ║
    ║                                                      ║
    ║ Type '\033[1mhelp\033[0m' for a list of commands                   ║
    ║ Type '\033[1mchat <message>\033[0m' to chat with Claude            ║
    ║ Type '\033[1msetup\033[0m' to configure services                   ║
    ║ Type '\033[1mstatus\033[0m' to check service status                ║
    ║ Type '\033[1mquit\033[0m' to exit                                  ║
    ╚══════════════════════════════════════════════════════╝
    """
    prompt = "\033[1;36msimple-anthropic-v3>\033[0m "
    
    def __init__(self):
        super().__init__()
        self.config = self._load_config()
        self.history = self._load_history()
        
        # Get API key - already loaded from .env by load_dotenv()
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            print("\033[31m✘\033[0m ANTHROPIC_API_KEY not found in environment or .env file")
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
        if tool_name == "search_web":
            if not self.brave:
                return {"error": "Brave Search service not initialized. Run setup first."}
            
            try:
                results = self.brave.web_search(
                    query=parameters["query"],
                    count=parameters.get("count", 5),
                    offset=0
                )
                return {"results": results["web"]["results"]}
            except Exception as e:
                return {"error": f"Error performing web search: {e}"}
        
        elif tool_name == "search_emails":
            if not self.gmail:
                return {"error": "Gmail service not initialized. Run setup first."}
            
            try:
                emails = self.gmail.list_emails(
                    query=parameters["query"],
                    max_results=parameters.get("max_results", 5)
                )
                return {"emails": emails}
            except Exception as e:
                return {"error": f"Error searching emails: {e}"}
        
        elif tool_name == "search_files":
            if not self.drive:
                return {"error": "Drive service not initialized. Run setup first."}
            
            try:
                files = self.drive.list_files(
                    query=parameters["query"],
                    max_results=parameters.get("max_results", 10)
                )
                return {"files": files}
            except Exception as e:
                return {"error": f"Error searching files: {e}"}
        
        elif tool_name == "create_draft_email":
            if not self.gmail:
                return {"error": "Gmail service not initialized. Run setup first."}
            
            try:
                draft_id = self.gmail.create_draft(
                    to=parameters["to"],
                    subject=parameters["subject"],
                    body=parameters["body"],
                    cc=parameters.get("cc", ""),
                    bcc=parameters.get("bcc", "")
                )
                return {"draft_id": draft_id, "status": "success"}
            except Exception as e:
                return {"error": f"Error creating email draft: {e}"}
        
        elif tool_name == "create_document":
            if not self.drive:
                return {"error": "Drive service not initialized. Run setup first."}
            
            try:
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
            except Exception as e:
                return {"error": f"Error creating document: {e}"}
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default."""
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
        
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return DEFAULT_CONFIG
    
    def _save_config(self):
        """Save configuration to file."""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _load_history(self) -> List[Dict]:
        """Load chat history from file."""
        if not os.path.exists(HISTORY_FILE):
            return []
        
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")
            return []
    
    def _save_history(self):
        """Save chat history to file."""
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def _initialize_services(self):
        """Initialize Gmail, Drive, and Brave services."""
        try:
            self.gmail = GmailService(
                credentials_path=self.config["gmail_credentials_path"],
                token_path=self.config["gmail_token_path"]
            )
            print("\033[32m✓\033[0m Gmail service initialized")
        except Exception as e:
            print(f"\033[31m×\033[0m Gmail service initialization failed: {e}")
        
        try:
            self.drive = DriveService(
                credentials_path=self.config["drive_credentials_path"],
                token_path=self.config["drive_token_path"]
            )
            print("\033[32m✓\033[0m Drive service initialized")
        except Exception as e:
            print(f"\033[31m×\033[0m Drive service initialization failed: {e}")
            
        try:
            if self.config["brave_api_key"]:
                self.brave = BraveSearchService(api_key=self.config["brave_api_key"])
                print("\033[32m✓\033[0m Brave Search service initialized")
            else:
                print("\033[33m! Brave Search service not initialized: API key not provided\033[0m")
        except Exception as e:
            print(f"\033[31m×\033[0m Brave Search service initialization failed: {e}")
    
    def _print_wrapped(self, text, prefix=""):
        """Print text with word wrapping."""
        width = os.get_terminal_size().columns - len(prefix)
        for line in text.split("\n"):
            wrapped = textwrap.fill(line, width=width, subsequent_indent=prefix)
            print(f"{prefix}{wrapped}")
    
    def _handle_tool_calls(self, tool_calls):
        """Handle tool calls from Claude's response."""
        tool_results = []
        
        print("\n\033[90mExecuting tool calls...\033[0m\n")
        
        for tool_call in tool_calls:
            tool_id = tool_call.get("id")
            tool_name = tool_call.get("name")
            tool_params = tool_call.get("input", {})
            
            print(f"\033[1;33m⚙️ Calling tool:\033[0m \033[1m{tool_name}\033[0m")
            print(f"  Parameters: {json.dumps(tool_params, indent=2)}")
            
            # Execute the tool
            result = self._execute_tool(tool_name, tool_params)
            
            # Add to results
            tool_results.append({
                "tool_call_id": tool_id,
                "role": "tool",
                "content": json.dumps(result, indent=2)
            })
            
            print(f"  \033[32m✓\033[0m Tool execution complete\n")
        
        return tool_results
    
    def _display_thinking(self, thinking_content):
        """Display Claude's thinking process."""
        print("\n\033[1;35m🧠 Claude's thinking process:\033[0m")
        print("\033[90m" + "=" * 60 + "\033[0m")
        self._print_wrapped(thinking_content, "  ")
        print("\033[90m" + "=" * 60 + "\033[0m\n")
    
    def do_chat(self, arg):
        """Chat with Claude: chat <message>"""
        if not arg:
            print("\033[33m! Please provide a message to send to Claude.\033[0m")
            return
        
        # Add message to conversation
        self.current_conversation.append({"role": "user", "content": arg})
        
        # Determine if we're using tools
        use_tools = self.config.get("use_tools", True)
        tools = self.tools if use_tools else None
        
        try:
            # Show typing indicator
            print("\033[90mClaude is thinking...\033[0m", end="\r")
            
            # Get response from Claude
            response = self.anthropic.send_message(self.current_conversation, tools=tools)
            
            # Clear typing indicator
            print(" " * 30, end="\r")
            
            # Process the response
            if isinstance(response, dict):
                # Extract thinking if available
                thinking_found = False
                text_content = ""
                tool_calls = []
                
                for content_block in response.get("content", []):
                    if content_block["type"] == "thinking":
                        thinking_found = True
                        if self.config.get("show_thinking", True):
                            self._display_thinking(content_block["thinking"])
                    elif content_block["type"] == "text":
                        text_content = content_block["text"]
                    elif content_block["type"] == "tool_use":
                        tool_calls = content_block.get("tools", [])
                
                # Handle any tool calls
                if tool_calls:
                    print("\033[1;36mClaude is requesting tool use:\033[0m")
                    tool_results = self._handle_tool_calls(tool_calls)
                    
                    # We don't add the initial assistant response with tool calls to the conversation
                    # Instead, just add the tool results
                    for result in tool_results:
                        self.current_conversation.append(result)
                    
                    # Now get a follow-up response after tool use
                    print("\033[90mGetting Claude's response after tool use...\033[0m", end="\r")
                    follow_up = self.anthropic.send_message(self.current_conversation, tools=tools)
                    print(" " * 50, end="\r")
                    
                    # Extract text from follow-up
                    if isinstance(follow_up, dict):
                        for content_block in follow_up.get("content", []):
                            if content_block["type"] == "text":
                                text_content = content_block["text"]
                                break
                        
                        # Update conversation with this final response
                        self.current_conversation.append({
                            "role": "assistant",
                            "content": follow_up.get("content", [])
                        })
                    else:
                        text_content = follow_up
                        self.current_conversation.append({
                            "role": "assistant", 
                            "content": text_content
                        })
                else:
                    # Add response to conversation
                    self.current_conversation.append({
                        "role": "assistant",
                        "content": response.get("content", [])
                    })
            else:
                # Simple text response
                text_content = response
                self.current_conversation.append({
                    "role": "assistant", 
                    "content": text_content
                })
            
            # Print the text response
            print("\n\033[1;34mClaude:\033[0m")
            self._print_wrapped(text_content, "  ")
            print()
            
            # Add to history
            self.history.append({
                "user": arg,
                "assistant": text_content,
                "model": self.config["model"],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            self._save_history()
        
        except Exception as e:
            print(f"\033[31m✘ Error communicating with Claude:\033[0m {e}")
    
    def do_thinking(self, arg):
        """Enable, disable, or configure extended thinking: thinking [on|off|show|hide|budget <number>]"""
        if not arg:
            # Show current thinking configuration
            enabled = self.config.get("thinking_enabled", True)
            budget = self.config.get("thinking_budget", 16000)
            show = self.config.get("show_thinking", True)
            
            print("\n\033[1;36mExtended Thinking Configuration:\033[0m")
            print(f"  Status: {'Enabled' if enabled else 'Disabled'}")
            print(f"  Budget: {budget} tokens")
            print(f"  Display: {'Show' if show else 'Hide'}")
            return
        
        args = arg.split()
        cmd = args[0].lower()
        
        if cmd == "on":
            self.config["thinking_enabled"] = True
            self.anthropic.thinking_enabled = True
            print("\033[32m✓\033[0m Extended thinking enabled")
        
        elif cmd == "off":
            self.config["thinking_enabled"] = False
            self.anthropic.thinking_enabled = False
            print("\033[32m✓\033[0m Extended thinking disabled")
        
        elif cmd == "show":
            self.config["show_thinking"] = True
            print("\033[32m✓\033[0m Claude's thinking process will be shown")
        
        elif cmd == "hide":
            self.config["show_thinking"] = False
            print("\033[32m✓\033[0m Claude's thinking process will be hidden")
        
        elif cmd == "budget" and len(args) > 1:
            try:
                budget = int(args[1])
                if budget < 1024:
                    print("\033[33m! Minimum budget is 1024 tokens. Setting to 1024.\033[0m")
                    budget = 1024
                
                self.config["thinking_budget"] = budget
                self.anthropic.thinking_budget = budget
                print(f"\033[32m✓\033[0m Thinking budget set to {budget} tokens")
            except ValueError:
                print("\033[31m✘\033[0m Budget must be a number")
        
        else:
            print("\033[33m! Usage: thinking [on|off|show|hide|budget <number>]\033[0m")
        
        # Save configuration
        self._save_config()
    
    def do_tools(self, arg):
        """Enable, disable, or list available tools: tools [on|off|list]"""
        if not arg:
            # Show current tools configuration
            enabled = self.config.get("use_tools", True)
            
            print("\n\033[1;36mTool Use Configuration:\033[0m")
            print(f"  Status: {'Enabled' if enabled else 'Disabled'}")
            print(f"  Available Tools: {len(self.tools)}")
            return
        
        cmd = arg.lower()
        
        if cmd == "on":
            self.config["use_tools"] = True
            print("\033[32m✓\033[0m Tool use enabled")
        
        elif cmd == "off":
            self.config["use_tools"] = False
            print("\033[32m✓\033[0m Tool use disabled")
        
        elif cmd == "list":
            print("\n\033[1;36mAvailable Tools:\033[0m")
            for tool in self.tools:
                print(f"  \033[1m{tool['name']}\033[0m: {tool['description']}")
                required_params = tool['input_schema'].get('required', [])
                print(f"  Required parameters: {', '.join(required_params)}")
                print()
        
        else:
            print("\033[33m! Usage: tools [on|off|list]\033[0m")
        
        # Save configuration
        self._save_config()
    
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
    
    def do_clear(self, arg):
        """Clear the current conversation"""
        self.current_conversation = []
        print("\033[32m✓\033[0m Conversation cleared.")
        
    def do_reset(self, arg):
        """Reset the CLI state when encountering tool use errors"""
        self.current_conversation = []
        print("\033[32m✓\033[0m CLI state reset. Any corrupted conversation state has been cleared.")
        
    def do_refresh(self, arg):
        """Refresh service connections and tokens without full setup
        
        Usage: refresh [service] [--reset]
        Where service can be:
        - all (default): Refresh all services
        - gmail: Just refresh Gmail connection
        - drive: Just refresh Drive connection
        - anthropic: Refresh Anthropic API connection
        - brave: Refresh Brave Search API connection
        
        Options:
        --reset: Force complete re-authentication (removes existing tokens)
        """
        args = arg.split()
        
        # Check for reset flag
        reset_auth = False
        if "--reset" in args:
            reset_auth = True
            args.remove("--reset")
            
        service = args[0].lower() if args else "all"
        
        if service in ["all", "anthropic"]:
            try:
                # Get API key - already loaded from .env by load_dotenv()
                anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not anthropic_api_key:
                    print("\033[31m✘\033[0m ANTHROPIC_API_KEY not found in environment or .env file")
                    print("  Please add it to your .env file in the format: ANTHROPIC_API_KEY=your_api_key_here")
                    return
                
                # Re-initialize Anthropic client
                self.anthropic = AnthropicClientV2(
                    api_key=anthropic_api_key, 
                    model=self.config["model"],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"],
                    thinking_enabled=self.config.get("thinking_enabled", True),
                    thinking_budget=self.config.get("thinking_budget", 16000),
                    extended_output=self.config.get("extended_output", False)
                )
                print("\033[32m✓\033[0m Anthropic API reconnected")
            except Exception as e:
                print(f"\033[31m✘\033[0m Anthropic API reconnection failed: {e}")
                print("  Please check your ANTHROPIC_API_KEY in the .env file")
        
        if service in ["all", "gmail"]:
            try:
                # Reinitialize Gmail service (this will refresh the token)
                self.gmail = GmailService(
                    credentials_path=self.config["gmail_credentials_path"],
                    token_path=self.config["gmail_token_path"],
                    force_refresh=True,
                    reset_auth=reset_auth
                )
                if reset_auth:
                    print("\033[32m✓\033[0m Gmail service reinitialized with complete re-authentication")
                else:
                    print("\033[32m✓\033[0m Gmail service reinitialized and token refreshed")
            except Exception as e:
                print(f"\033[31m✘\033[0m Gmail service reinitialization failed: {e}")
                print("  You may need to run 'setup' to reconfigure credentials")
        
        if service in ["all", "drive"]:
            try:
                # Reinitialize Drive service (this will refresh the token)
                self.drive = DriveService(
                    credentials_path=self.config["drive_credentials_path"],
                    token_path=self.config["drive_token_path"],
                    force_refresh=True,
                    reset_auth=reset_auth
                )
                if reset_auth:
                    print("\033[32m✓\033[0m Drive service reinitialized with complete re-authentication")
                else:
                    print("\033[32m✓\033[0m Drive service reinitialized and token refreshed")
            except Exception as e:
                print(f"\033[31m✘\033[0m Drive service reinitialization failed: {e}")
                print("  You may need to run 'setup' to reconfigure credentials")
                
        if service in ["all", "brave"]:
            try:
                # Reinitialize Brave service
                if self.config["brave_api_key"]:
                    self.brave = BraveSearchService(api_key=self.config["brave_api_key"])
                    print("\033[32m✓\033[0m Brave Search service reinitialized")
                else:
                    print("\033[33m! Brave Search service not initialized: API key not provided\033[0m")
            except Exception as e:
                print(f"\033[31m✘\033[0m Brave Search service reinitialization failed: {e}")
                
        if service not in ["all", "gmail", "drive", "anthropic", "brave"]:
            print(f"\033[31m✘\033[0m Unknown service: {service}")
            print("  Valid options: all, gmail, drive, anthropic, brave")
        
    def do_save_conversation(self, arg):
        """Save the current conversation to a file: save_conversation [filename]"""
        if not self.current_conversation:
            print("\033[33m! No conversation to save\033[0m")
            return
            
        filename = arg if arg else f"conversation_{int(time.time())}.json"
        if not filename.endswith('.json'):
            filename += '.json'
            
        try:
            # Create save directory if it doesn't exist
            save_dir = os.path.join(CONFIG_DIR, "conversations")
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            # Save conversation to file
            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'w') as f:
                # Include conversation metadata
                save_data = {
                    "model": self.config["model"],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "messages": self.current_conversation
                }
                json.dump(save_data, f, indent=2)
                
            print(f"\033[32m✓\033[0m Conversation saved to \033[1m{filepath}\033[0m")
        except Exception as e:
            print(f"\033[31m✘\033[0m Error saving conversation: {e}")
    
    def do_list_conversations(self, arg):
        """List saved conversations"""
        save_dir = os.path.join(CONFIG_DIR, "conversations")
        
        if not os.path.exists(save_dir):
            print("\033[33m! No saved conversations found\033[0m")
            return
            
        conversations = [f for f in os.listdir(save_dir) if f.endswith('.json')]
        
        if not conversations:
            print("\033[33m! No saved conversations found\033[0m")
            return
            
        print("\n\033[1;36mSaved Conversations:\033[0m")
        print(f"\033[90m{'Filename':<30} {'Date':<20} {'Model':<25} {'Messages':<10}\033[0m")
        print(f"\033[90m{'-'*30} {'-'*20} {'-'*25} {'-'*10}\033[0m")
        
        for filename in sorted(conversations, reverse=True):
            filepath = os.path.join(save_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    timestamp = data.get("timestamp", "Unknown")
                    model = data.get("model", "Unknown")
                    message_count = len(data.get("messages", []))
                    print(f"{filename:<30} {timestamp:<20} {model:<25} {message_count:<10}")
            except Exception:
                print(f"{filename:<30} \033[33mError loading metadata\033[0m")
        print()
    
    def do_load_conversation(self, arg):
        """Load a saved conversation: load_conversation <filename>"""
        if not arg:
            print("\033[33m! Please provide a filename\033[0m")
            return
            
        filename = arg
        if not filename.endswith('.json'):
            filename += '.json'
            
        filepath = os.path.join(CONFIG_DIR, "conversations", filename)
        
        if not os.path.exists(filepath):
            print(f"\033[31m✘\033[0m Conversation file not found: {filename}")
            return
            
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            # Ask for confirmation if there's an existing conversation
            if self.current_conversation:
                response = input("\033[33m! Current conversation will be replaced. Continue? (y/n) \033[0m")
                if response.lower() != 'y':
                    print("\033[33m! Load cancelled\033[0m")
                    return
            
            # Load the conversation
            self.current_conversation = data.get("messages", [])
            
            # Set the model if specified
            loaded_model = data.get("model")
            if loaded_model and loaded_model in MODELS:
                self.config["model"] = loaded_model
                self.anthropic.model = loaded_model
                print(f"\033[32m✓\033[0m Model set to \033[1m{loaded_model}\033[0m")
            
            # Print confirmation
            message_count = len(self.current_conversation)
            print(f"\033[32m✓\033[0m Loaded conversation with \033[1m{message_count}\033[0m messages")
            
            # Print conversation summary
            if message_count > 0:
                print("\n\033[1;36mConversation Summary:\033[0m")
                for i, msg in enumerate(self.current_conversation):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    # Truncate content for display
                    if isinstance(content, str):
                        content_display = content
                    elif isinstance(content, list):
                        # Handle structured content blocks
                        content_items = []
                        for block in content[:2]:  # Just look at first 2 blocks for summary
                            if isinstance(block, dict) and block.get("type") == "text":
                                content_items.append(block.get("text", "")[:40])
                        content_display = "; ".join(content_items)
                    else:
                        content_display = str(content)
                        
                    # Truncate for display
                    if len(content_display) > 60:
                        content_display = content_display[:57] + "..."
                        
                    print(f"{i+1:2d}. \033[1m{role:<10}\033[0m {content_display}")
                print()
                
        except Exception as e:
            print(f"\033[31m✘\033[0m Error loading conversation: {e}")
    
    def do_config(self, arg):
        """View or change configuration: config [setting] [value]"""
        args = arg.split()
        
        if not args:
            print("\n\033[1;36mCurrent configuration:\033[0m")
            for key, value in self.config.items():
                print(f"  \033[1m{key}\033[0m: {value}")
            return
        
        if len(args) == 1:
            key = args[0]
            if key in self.config:
                print(f"{key}: {self.config[key]}")
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
            masked_key = self.config['brave_api_key'][:6] + "..." if self.config['brave_api_key'] else "Not set"
            print(f"    - API Key: {masked_key}")
        else:
            print(f"  \033[31m✘\033[0m Brave Search: Not connected")
        
        print()
    
    def do_setup(self, arg):
        """Set up or reconfigure services"""
        print("\n\033[1;36mSetup Wizard\033[0m")
        
        # Configure paths
        print("\nEnter the paths to your Google API credentials and tokens.")
        print("Press Enter to keep the current value.")
        
        # Gmail credentials
        gmail_creds = input(f"Gmail credentials path [{self.config['gmail_credentials_path']}]: ")
        if gmail_creds:
            self.config["gmail_credentials_path"] = os.path.abspath(gmail_creds)
        
        # Gmail token
        gmail_token = input(f"Gmail token path [{self.config['gmail_token_path']}]: ")
        if gmail_token:
            self.config["gmail_token_path"] = os.path.abspath(gmail_token)
        
        # Drive credentials
        drive_creds = input(f"Drive credentials path [{self.config['drive_credentials_path']}]: ")
        if drive_creds:
            self.config["drive_credentials_path"] = os.path.abspath(drive_creds)
        
        # Drive token
        drive_token = input(f"Drive token path [{self.config['drive_token_path']}]: ")
        if drive_token:
            self.config["drive_token_path"] = os.path.abspath(drive_token)
            
        # Brave Search API key
        current_brave_key = os.environ.get("BRAVE_API_KEY", "")
        masked_key = current_brave_key[:6] + "..." if current_brave_key else "Not set"
        print(f"Current Brave Search API key: {masked_key}")
        print("\033[33mNote: API keys should be stored in your .env file\033[0m")
        print("To update your Brave API key, edit the .env file and add/modify:")
        print("BRAVE_API_KEY=your_api_key_here")
        print("")
            
        # Model selection
        print("\n\033[1;36mAvailable Claude models:\033[0m")
        for i, model in enumerate(MODELS, 1):
            if model == self.config["model"]:
                print(f"  {i}. \033[1m{model}\033[0m (current)")
            else:
                print(f"  {i}. {model}")
        
        model_choice = input(f"Select model (1-{len(MODELS)}) or press Enter to keep current: ")
        if model_choice and model_choice.isdigit():
            index = int(model_choice) - 1
            if 0 <= index < len(MODELS):
                self.config["model"] = MODELS[index]
                self.anthropic.model = MODELS[index]
        
        # Configure extended thinking
        print("\n\033[1;36mConfigure Extended Thinking:\033[0m")
        thinking_enabled = input(f"Enable extended thinking? (y/n) [{('y' if self.config.get('thinking_enabled', True) else 'n')}]: ")
        if thinking_enabled.lower() in ["y", "yes"]:
            self.config["thinking_enabled"] = True
            self.anthropic.thinking_enabled = True
            
            budget = input(f"Thinking budget in tokens [{self.config.get('thinking_budget', 16000)}]: ")
            if budget and budget.isdigit():
                budget = int(budget)
                if budget < 1024:
                    print("\033[33m! Minimum budget is 1024 tokens. Setting to 1024.\033[0m")
                    budget = 1024
                self.config["thinking_budget"] = budget
                self.anthropic.thinking_budget = budget
                
            show_thinking = input(f"Show thinking in output? (y/n) [{('y' if self.config.get('show_thinking', True) else 'n')}]: ")
            self.config["show_thinking"] = show_thinking.lower() in ["y", "yes"]
            
        elif thinking_enabled.lower() in ["n", "no"]:
            self.config["thinking_enabled"] = False
            self.anthropic.thinking_enabled = False
        
        # Configure tool use
        print("\n\033[1;36mConfigure Tool Use:\033[0m")
        tools_enabled = input(f"Enable tool use? (y/n) [{('y' if self.config.get('use_tools', True) else 'n')}]: ")
        if tools_enabled.lower() in ["y", "yes"]:
            self.config["use_tools"] = True
        elif tools_enabled.lower() in ["n", "no"]:
            self.config["use_tools"] = False
        
        # Configure extended output for Claude 3.7
        if "claude-3-7" in self.config["model"]:
            print("\n\033[1;36mConfigure Extended Output (128k tokens):\033[0m")
            ext_output = input(f"Enable extended output? (y/n) [{('y' if self.config.get('extended_output', False) else 'n')}]: ")
            if ext_output.lower() in ["y", "yes"]:
                self.config["extended_output"] = True
                self.anthropic.extended_output = True
            elif ext_output.lower() in ["n", "no"]:
                self.config["extended_output"] = False
                self.anthropic.extended_output = False
        
        # Save configuration
        self._save_config()
        print("\n\033[32m✓\033[0m Configuration saved.")
        
        # Re-initialize services
        print("\n\033[1;36mInitializing services...\033[0m")
        self._initialize_services()
        
        print("\n\033[1;32m✓ Setup complete!\033[0m")
    
    def do_quit(self, arg):
        """Exit the CLI"""
        self._save_history()
        print("\n\033[1;36mGoodbye!\033[0m")
        return True
    
    def do_exit(self, arg):
        """Exit the CLI"""
        return self.do_quit(arg)
        
    def do_web_search(self, arg):
        """Perform a web search: web_search <query> [count] [offset]"""
        if not self.brave:
            print("\033[31m✘\033[0m Brave Search service not initialized. Run \033[1msetup\033[0m first.")
            return
            
        if not arg:
            print("\033[33m! Please provide a search query\033[0m")
            return
            
        # Parse arguments
        args = arg.split()
        query = args[0]
        count = 10
        offset = 0
        
        # If there are more words in the query, combine them
        if len(args) > 1:
            try:
                # Try to extract count if the last argument is a number
                count = int(args[-1])
                query = " ".join(args[:-1])
            except ValueError:
                # If not a number, include in the query
                query = " ".join(args)
                
        # Ensure params are within limits
        count = min(max(1, count), 20)
        
        try:
            print(f"\033[90mSearching for '{query}'...\033[0m")
            results = self.brave.web_search(query, count, offset)
            
            print(self.brave.format_web_results(results))
            
            # Add a suggested refinement if available
            if 'query' in results and 'suggestionGroups' in results['query']:
                for group in results['query']['suggestionGroups']:
                    if 'suggestions' in group and group['suggestions']:
                        suggestions = [s['text'] for s in group['suggestions']]
                        print("\033[36mSuggested searches:\033[0m", ", ".join(suggestions))
                        break
                        
        except Exception as e:
            print(f"\033[31m✘\033[0m Error performing web search: {e}")
            
    def do_local_search(self, arg):
        """Search for local businesses and services: local_search <query> [count]"""
        if not self.brave:
            print("\033[31m✘\033[0m Brave Search service not initialized. Run \033[1msetup\033[0m first.")
            return
            
        if not arg:
            print("\033[33m! Please provide a search query\033[0m")
            return
            
        # Parse arguments
        args = arg.split()
        query = args[0]
        count = 10
        
        # If there are more words in the query, combine them
        if len(args) > 1:
            try:
                # Try to extract count if the last argument is a number
                count = int(args[-1])
                query = " ".join(args[:-1])
            except ValueError:
                # If not a number, include in the query
                query = " ".join(args)
                
        # Ensure params are within limits
        count = min(max(1, count), 20)
        
        try:
            print(f"\033[90mSearching for local results for '{query}'...\033[0m")
            results = self.brave.local_search(query, count)
            
            print(self.brave.format_local_results(results))
            
        except Exception as e:
            print(f"\033[31m✘\033[0m Error performing local search: {e}")
    
    def _ensure_gmail_authentication(self):
        """Helper method to handle Gmail authentication issues
        
        Returns:
            bool: True if authentication is successful, False otherwise
        """
        if not self.gmail:
            print("\033[31m✘\033[0m Gmail service not initialized. Run \033[1msetup\033[0m first.")
            return False
        
        return True
        
    def do_email_list(self, arg):
        """List recent emails: email_list [query]"""
        if not self._ensure_gmail_authentication():
            return
        
        try:
            print("\033[90mFetching emails...\033[0m")
            emails = self.gmail.list_emails(query=arg if arg else None)
            if not emails:
                print("\033[33m! No emails found.\033[0m")
                return
            
            print(f"\n\033[1;36m{'ID':<12} {'From':<30} {'Subject':<50}\033[0m")
            print(f"\033[90m{'-'*12} {'-'*30} {'-'*50}\033[0m")
            
            for email in emails:
                print(f"{email['id'][:10]:<12} \033[1m{email['from'][:30]:<30}\033[0m {email['subject'][:50]}")
            print()
        
        except Exception as e:
            error_msg = str(e)
            print(f"\033[31m✘ Error listing emails:\033[0m {e}")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                print("  2. \033[1mrefresh gmail --reset\033[0m - to completely re-authenticate with Google")
                print("  3. \033[1msetup\033[0m - if the above options don't work")
    
    def do_email_read(self, arg):
        """Read an email by ID: email_read <email_id>"""
        if not self._ensure_gmail_authentication():
            return
        
        if not arg:
            print("\033[33m! Please provide an email ID.\033[0m")
            return
        
        try:
            print("\033[90mFetching email content...\033[0m")
            email = self.gmail.get_email(arg)
            
            print(f"\n\033[1;36m{'='*60}\033[0m")
            print(f"\033[1mFrom:\033[0m {email['from']}")
            print(f"\033[1mTo:\033[0m {email['to']}")
            print(f"\033[1mDate:\033[0m {email['date']}")
            print(f"\033[1mSubject:\033[0m {email['subject']}")
            print(f"\033[90m{'-'*60}\033[0m")
            print(email['body'])
            print(f"\033[1;36m{'='*60}\033[0m\n")
        
        except Exception as e:
            error_msg = str(e)
            print(f"\033[31m✘ Error reading email:\033[0m {e}")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                print("  2. \033[1mrefresh gmail --reset\033[0m - to completely re-authenticate with Google")
                print("  3. \033[1msetup\033[0m - if the above options don't work")
    
    def do_email_compose(self, arg):
        """Compose an email interactively"""
        if not self._ensure_gmail_authentication():
            return
        
        print("\n\033[1;36mEmail Composition\033[0m")
        
        # Get recipient
        to = input("\033[1mTo:\033[0m ").strip()
        if not to:
            print("\033[33m! Email recipient is required\033[0m")
            return
        
        # Get CC (optional)
        cc = input("\033[1mCC:\033[0m ").strip()
        
        # Get BCC (optional)
        bcc = input("\033[1mBCC:\033[0m ").strip()
        
        # Get subject
        subject = input("\033[1mSubject:\033[0m ").strip()
        if not subject:
            print("\033[33m! Email subject is required\033[0m")
            return
        
        # Get body (multiline)
        print("\033[1mBody:\033[0m (Type your message. Enter '.' on a new line to finish)")
        lines = []
        while True:
            line = input()
            if line.strip() == '.':
                break
            lines.append(line)
        
        body = '\n'.join(lines)
        
        if not body:
            print("\033[33m! Email body is required\033[0m")
            return
        
        # Confirm before sending
        print("\n\033[1;36mEmail Preview:\033[0m")
        print(f"\033[1mTo:\033[0m {to}")
        if cc:
            print(f"\033[1mCC:\033[0m {cc}")
        if bcc:
            print(f"\033[1mBCC:\033[0m {bcc}")
        print(f"\033[1mSubject:\033[0m {subject}")
        print("\033[1mBody:\033[0m")
        print("\033[90m" + "-" * 40 + "\033[0m")
        print(body)
        print("\033[90m" + "-" * 40 + "\033[0m")
        
        # Ask if they want to send or save as draft
        choice = input("\n\033[1mOptions:\033[0m [1] Send now  [2] Save as draft  [3] Cancel: ").strip()
        
        if choice == '1':
            try:
                print("\033[90mSending email...\033[0m")
                self.gmail.send_email(to, subject, body, cc, bcc)
                print(f"\033[32m✓\033[0m Email sent to \033[1m{to}\033[0m!")
            except Exception as e:
                print(f"\033[31m✘ Error sending email:\033[0m {e}")
        
        elif choice == '2':
            try:
                print("\033[90mSaving draft...\033[0m")
                draft_id = self.gmail.create_draft(to, subject, body, cc, bcc)
                print(f"\033[32m✓\033[0m Draft saved! ID: \033[1m{draft_id}\033[0m")
            except Exception as e:
                error_msg = str(e)
                print(f"\033[31m✘ Error saving draft:\033[0m {e}")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
        
        else:
            print("\033[33m! Email composition cancelled\033[0m")
    
    def do_email_send(self, arg):
        """Send an email: email_send <to> <subject> <body>"""
        if not self._ensure_gmail_authentication():
            return
        
        args = arg.split(' ', 2)
        if len(args) < 3:
            print("\033[33m! Usage: email_send <to> <subject> <body>\033[0m")
            return
        
        to, subject, body = args
        
        try:
            print("\033[90mSending email...\033[0m")
            self.gmail.send_email(to, subject, body)
            print(f"\033[32m✓\033[0m Email sent to \033[1m{to}\033[0m!")
        except Exception as e:
            error_msg = str(e)
            print(f"\033[31m✘ Error sending email:\033[0m {e}")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
            
    def do_email_drafts(self, arg):
        """List and manage email drafts"""
        if not self._ensure_gmail_authentication():
            return
            
        args = arg.split()
        if not args:
            # List drafts
            try:
                print("\033[90mFetching drafts...\033[0m")
                drafts = self.gmail.list_drafts()
                
                if not drafts:
                    print("\033[33m! No drafts found\033[0m")
                    return
                
                print(f"\n\033[1;36m{'ID':<12} {'To':<25} {'Subject':<40}\033[0m")
                print(f"\033[90m{'-'*12} {'-'*25} {'-'*40}\033[0m")
                
                for draft in drafts:
                    draft_id = draft.get('id', 'Unknown')[:10] 
                    draft_to = draft.get('to', 'Unknown')[:23]
                    draft_subject = draft.get('subject', 'No Subject')[:40]
                    print(f"{draft_id:<12} \033[1m{draft_to:<25}\033[0m {draft_subject}")
                print()
                
            except Exception as e:
                error_msg = str(e)
                print(f"\033[31m✘ Error listing drafts:\033[0m {e}")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
                
        elif args[0] == 'send' and len(args) > 1:
            # Send a specific draft
            draft_id = args[1]
            try:
                print(f"\033[90mSending draft {draft_id}...\033[0m")
                self.gmail.send_draft(draft_id)
                print(f"\033[32m✓\033[0m Draft sent successfully!")
            except Exception as e:
                error_msg = str(e)
                print(f"\033[31m✘ Error sending draft:\033[0m {e}")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
                
        elif args[0] == 'view' and len(args) > 1:
            # View a specific draft
            draft_id = args[1]
            try:
                print(f"\033[90mFetching draft {draft_id}...\033[0m")
                draft = self.gmail.get_draft(draft_id)
                
                print(f"\n\033[1;36m{'='*60}\033[0m")
                print(f"\033[1mTo:\033[0m {draft['to']}")
                if draft.get('cc'):
                    print(f"\033[1mCC:\033[0m {draft['cc']}")
                if draft.get('bcc'):
                    print(f"\033[1mBCC:\033[0m {draft['bcc']}")
                print(f"\033[1mSubject:\033[0m {draft['subject']}")
                print(f"\033[90m{'-'*60}\033[0m")
                print(draft['body'])
                print(f"\033[1;36m{'='*60}\033[0m\n")
                
            except Exception as e:
                error_msg = str(e)
                print(f"\033[31m✘ Error viewing draft:\033[0m {e}")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
                
        else:
            print("\033[33m! Usage: email_drafts [send <draft_id> | view <draft_id>]\033[0m")
    
    def do_drive_list(self, arg):
        """List files in Google Drive: drive_list [query]"""
        if not self.drive:
            print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
            return
        
        try:
            print("\033[90mFetching Drive files...\033[0m")
            
            # Process natural language queries into Google Drive query format
            if arg:
                # Handle common natural language patterns
                if "with" in arg.lower() and "in" in arg.lower() and "title" in arg.lower():
                    # "files with X in the title" pattern
                    search_term = arg.lower().split("with")[1].split("in")[0].strip()
                    query = f"name contains '{search_term}'"
                elif "containing" in arg.lower():
                    # "files containing X" pattern
                    search_term = arg.lower().split("containing")[1].strip()
                    query = f"name contains '{search_term}' or fullText contains '{search_term}'"
                elif "named" in arg.lower():
                    # "files named X" pattern
                    search_term = arg.lower().split("named")[1].strip()
                    query = f"name contains '{search_term}'"
                else:
                    # Default: treat as a search term for name
                    query = f"name contains '{arg}'"
            else:
                query = None
            
            files = self.drive.list_files(query=query)
            if not files:
                print("\033[33m! No files found.\033[0m")
                return
            
            print(f"\n\033[1;36m{'ID':<20} {'Name':<40} {'Type':<20} {'Size':<10}\033[0m")
            print(f"\033[90m{'-'*20} {'-'*40} {'-'*20} {'-'*10}\033[0m")
            
            for file in files:
                size = file.get('size', 'N/A')
                if size != 'N/A':
                    size = f"{int(size) // 1024} KB"
                
                # Color-code file types
                mime_type = file['mimeType']
                if 'folder' in mime_type:
                    type_str = f"\033[1;34m{mime_type[:18]:<18}\033[0m"  # Blue for folders
                elif 'document' in mime_type:
                    type_str = f"\033[1;32m{mime_type[:18]:<18}\033[0m"  # Green for documents
                elif 'spreadsheet' in mime_type:
                    type_str = f"\033[1;33m{mime_type[:18]:<18}\033[0m"  # Yellow for spreadsheets
                elif 'presentation' in mime_type:
                    type_str = f"\033[1;35m{mime_type[:18]:<18}\033[0m"  # Purple for presentations
                elif 'pdf' in mime_type:
                    type_str = f"\033[1;31m{mime_type[:18]:<18}\033[0m"  # Red for PDFs
                else:
                    type_str = f"{mime_type[:18]:<18}"
                
                print(f"{file['id'][:18]:<20} \033[1m{file['name'][:38]:<40}\033[0m {type_str} {size:<10}")
            print()
        
        except Exception as e:
            error_msg = str(e)
            print(f"\033[31m✘ Error listing Drive files:\033[0m {e}")
            print("\033[33m! Hint: Use a simpler query format like 'cwt' or 'name contains cwt'\033[0m")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh drive\033[0m - to refresh your Drive token")
                print("  2. \033[1mrefresh drive --reset\033[0m - to completely re-authenticate with Google")
                print("  3. \033[1msetup\033[0m - if the above options don't work")
            else:
                print("  Google Drive API requires specific query formats. Try using 'refresh drive' if authentication failed.")
    
    def do_drive_download(self, arg):
        """Download a file from Google Drive: drive_download <file_id> [output_path]"""
        if not self.drive:
            print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
            return
        
        args = arg.split()
        if not args:
            print("\033[33m! Usage: drive_download <file_id> [output_path]\033[0m")
            return
        
        file_id = args[0]
        output_path = args[1] if len(args) > 1 else None
        
        try:
            print("\033[90mDownloading file...\033[0m")
            path = self.drive.download_file(file_id, output_path)
            print(f"\033[32m✓\033[0m File downloaded to \033[1m{path}\033[0m")
        except Exception as e:
            error_msg = str(e)
            print(f"\033[31m✘ Error downloading file:\033[0m {e}")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh drive\033[0m - to refresh your Drive token")
                print("  2. \033[1mrefresh drive --reset\033[0m - to completely re-authenticate with Google")
                print("  3. \033[1msetup\033[0m - if the above options don't work")
    
    def do_drive_create(self, arg):
        """Create Google Drive files: drive_create <type> <n>"""
        if not self.drive:
            print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
            return
            
        args = arg.split(' ', 1)
        if len(args) < 2:
            print("\033[33m! Usage: drive_create <type> <n>\033[0m")
            print("\033[33m! Types: document, spreadsheet, folder\033[0m")
            return
            
        file_type, name = args
        
        if file_type not in ['document', 'spreadsheet', 'folder']:
            print(f"\033[31m✘\033[0m Invalid file type: {file_type}")
            print("\033[33m! Valid types: document, spreadsheet, folder\033[0m")
            return
            
        try:
            print(f"\033[90mCreating {file_type}...\033[0m")
            
            if file_type == 'document':
                # For documents, ask for optional content
                print("\nEnter document content (optional):")
                print("Type your content. Enter '.' on a new line to finish")
                lines = []
                while True:
                    line = input()
                    if line.strip() == '.':
                        break
                    lines.append(line)
                
                content = '\n'.join(lines) if lines else None
                
                # Create the document
                result = self.drive.create_document(name, content)
                print(f"\033[32m✓\033[0m Document created: \033[1m{result['name']}\033[0m")
                print(f"  ID: {result['id']}")
                print(f"  Link: {result.get('webViewLink', 'Not available')}")
                
                # Ask if they want to share the document
                share = input("\nShare this document? (y/n): ").strip().lower()
                if share == 'y':
                    email = input("Enter email address to share with: ").strip()
                    role = input("Enter role (reader/writer/commenter) [reader]: ").strip().lower() or 'reader'
                    
                    if role not in ['reader', 'writer', 'commenter']:
                        print("\033[33m! Invalid role. Using 'reader' instead.\033[0m")
                        role = 'reader'
                        
                    self.drive.share_file(result['id'], email, role)
                    print(f"\033[32m✓\033[0m Document shared with {email} as {role}")
                
            elif file_type == 'spreadsheet':
                # Create the spreadsheet
                result = self.drive.create_spreadsheet(name)
                print(f"\033[32m✓\033[0m Spreadsheet created: \033[1m{result['name']}\033[0m")
                print(f"  ID: {result['id']}")
                print(f"  Link: {result.get('webViewLink', 'Not available')}")
                
                # Ask if they want to share the spreadsheet
                share = input("\nShare this spreadsheet? (y/n): ").strip().lower()
                if share == 'y':
                    email = input("Enter email address to share with: ").strip()
                    role = input("Enter role (reader/writer/commenter) [reader]: ").strip().lower() or 'reader'
                    
                    if role not in ['reader', 'writer', 'commenter']:
                        print("\033[33m! Invalid role. Using 'reader' instead.\033[0m")
                        role = 'reader'
                        
                    self.drive.share_file(result['id'], email, role)
                    print(f"\033[32m✓\033[0m Spreadsheet shared with {email} as {role}")
                
            elif file_type == 'folder':
                # Create the folder
                result = self.drive.create_folder(name)
                print(f"\033[32m✓\033[0m Folder created: \033[1m{result['name']}\033[0m")
                print(f"  ID: {result['id']}")
                
        except Exception as e:
            print(f"\033[31m✘ Error creating {file_type}:\033[0m {e}")
    
    def do_drive_shared(self, arg):
        """List files shared with me"""
        if not self.drive:
            print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
            return
            
        try:
            print("\033[90mFetching shared files...\033[0m")
            files = self.drive.get_shared_files()
            
            if not files:
                print("\033[33m! No shared files found\033[0m")
                return
                
            print(f"\n\033[1;36m{'Name':<40} {'Type':<20} {'Owner':<30}\033[0m")
            print(f"\033[90m{'-'*40} {'-'*20} {'-'*30}\033[0m")
            
            for file in files:
                # Format file type for display
                mime_type = file['mimeType']
                type_display = mime_type.split('.')[-1].capitalize() if '.' in mime_type else mime_type
                
                # Get owner info
                owner = file.get('owners', [{}])[0].get('displayName', 'Unknown') if 'owners' in file else 'Unknown'
                
                # Color-code file types
                if 'folder' in mime_type:
                    type_str = f"\033[1;34m{type_display[:18]:<18}\033[0m"  # Blue for folders
                elif 'document' in mime_type:
                    type_str = f"\033[1;32m{type_display[:18]:<18}\033[0m"  # Green for documents
                elif 'spreadsheet' in mime_type:
                    type_str = f"\033[1;33m{type_display[:18]:<18}\033[0m"  # Yellow for spreadsheets
                elif 'presentation' in mime_type:
                    type_str = f"\033[1;35m{type_display[:18]:<18}\033[0m"  # Purple for presentations
                else:
                    type_str = f"{type_display[:18]:<18}"
                
                print(f"\033[1m{file['name'][:38]:<40}\033[0m {type_str} {owner[:28]:<30}")
                
            print()
                
        except Exception as e:
            print(f"\033[31m✘ Error listing shared files:\033[0m {e}")
    
    def do_drive_share(self, arg):
        """Share a Drive file: drive_share <file_id> <email> [role]"""
        if not self.drive:
            print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
            return
            
        args = arg.split()
        if len(args) < 2:
            print("\033[33m! Usage: drive_share <file_id> <email> [role]\033[0m")
            print("\033[33m! Roles: reader, writer, commenter (default: reader)\033[0m")
            return
            
        file_id = args[0]
        email = args[1]
        role = args[2] if len(args) > 2 else 'reader'
        
        if role not in ['reader', 'writer', 'commenter']:
            print(f"\033[33m! Invalid role: {role}. Using 'reader' instead.\033[0m")
            role = 'reader'
            
        try:
            # Get file info first
            file_info = self.drive.get_file_metadata(file_id)
            
            print(f"\033[90mSharing file {file_info['name']} with {email}...\033[0m")
            self.drive.share_file(file_id, email, role)
            print(f"\033[32m✓\033[0m File \033[1m{file_info['name']}\033[0m shared with {email} as {role}")
            
        except Exception as e:
            print(f"\033[31m✘ Error sharing file:\033[0m {e}")
    
    def do_recent(self, arg):
        """Show recent items (emails, drafts, files): recent <type> [count]"""
        args = arg.split()
        
        if not args:
            print("\033[33m! Usage: recent <type> [count]\033[0m")
            print("\033[33m! Types: emails, drafts, sent, files, created\033[0m")
            return
            
        item_type = args[0].lower()
        count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
        
        if item_type == "emails":
            if not self.gmail:
                print("\033[31m✘\033[0m Gmail service not initialized. Run \033[1msetup\033[0m first.")
                return
                
            try:
                print(f"\033[90mFetching {count} recent emails...\033[0m")
                emails = self.gmail.list_emails(max_results=count)
                
                if not emails:
                    print("\033[33m! No emails found\033[0m")
                    return
                
                print(f"\n\033[1;36m{'ID':<12} {'From':<25} {'Subject':<40}\033[0m")
                print(f"\033[90m{'-'*12} {'-'*25} {'-'*40}\033[0m")
                
                for email in emails:
                    email_id = email.get('id', 'Unknown')[:10] 
                    email_from = email.get('from', 'Unknown')[:23]
                    email_subject = email.get('subject', 'No Subject')[:40]
                    print(f"{email_id:<12} \033[1m{email_from:<25}\033[0m {email_subject}")
                print()
                
            except Exception as e:
                print(f"\033[31m✘ Error listing recent emails:\033[0m {e}")
                
        elif item_type == "sent":
            if not self.gmail:
                print("\033[31m✘\033[0m Gmail service not initialized. Run \033[1msetup\033[0m first.")
                return
                
            try:
                print(f"\033[90mFetching {count} recent sent emails...\033[0m")
                emails = self.gmail.list_sent_emails(max_results=count)
                
                if not emails:
                    print("\033[33m! No sent emails found\033[0m")
                    return
                
                print(f"\n\033[1;36m{'ID':<12} {'To':<25} {'Subject':<40}\033[0m")
                print(f"\033[90m{'-'*12} {'-'*25} {'-'*40}\033[0m")
                
                for email in emails:
                    email_id = email.get('id', 'Unknown')[:10] 
                    email_from = email.get('from', 'Unknown')[:23]
                    email_subject = email.get('subject', 'No Subject')[:40]
                    print(f"{email_id:<12} \033[1m{email_from:<25}\033[0m {email_subject}")
                print()
                
            except Exception as e:
                print(f"\033[31m✘ Error listing recent sent emails:\033[0m {e}")
                
        elif item_type == "drafts":
            if not self.gmail:
                print("\033[31m✘\033[0m Gmail service not initialized. Run \033[1msetup\033[0m first.")
                return
                
            try:
                print(f"\033[90mFetching {count} recent drafts...\033[0m")
                drafts = self.gmail.list_drafts(max_results=count)
                
                if not drafts:
                    print("\033[33m! No drafts found\033[0m")
                    return
                
                print(f"\n\033[1;36m{'ID':<12} {'To':<25} {'Subject':<40}\033[0m")
                print(f"\033[90m{'-'*12} {'-'*25} {'-'*40}\033[0m")
                
                for draft in drafts:
                    draft_id = draft.get('id', 'Unknown')[:10] 
                    draft_to = draft.get('to', 'Unknown')[:23]
                    draft_subject = draft.get('subject', 'No Subject')[:40]
                    print(f"{draft_id:<12} \033[1m{draft_to:<25}\033[0m {draft_subject}")
                print()
                
            except Exception as e:
                print(f"\033[31m✘ Error listing recent drafts:\033[0m {e}")
                
        elif item_type == "files":
            if not self.drive:
                print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
                return
                
            try:
                print(f"\033[90mFetching {count} recent files...\033[0m")
                files = self.drive.list_recent_files(max_results=count)
                
                if not files:
                    print("\033[33m! No files found\033[0m")
                    return
                
                print(f"\n\033[1;36m{'ID':<12} {'Name':<40} {'Modified':<20}\033[0m")
                print(f"\033[90m{'-'*12} {'-'*40} {'-'*20}\033[0m")
                
                for file in files:
                    modified = file.get('modifiedTime', '').split('T')[0] if 'modifiedTime' in file else ''
                    print(f"{file['id'][:10]:<12} \033[1m{file['name'][:38]:<40}\033[0m {modified:<20}")
                print()
                
            except Exception as e:
                print(f"\033[31m✘ Error listing recent files:\033[0m {e}")
                
        elif item_type == "created":
            if not self.drive:
                print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
                return
                
            try:
                print(f"\033[90mFetching {count} recently created files...\033[0m")
                files = self.drive.list_recently_created_files(max_results=count)
                
                if not files:
                    print("\033[33m! No files found\033[0m")
                    return
                
                print(f"\n\033[1;36m{'ID':<12} {'Name':<40} {'Created':<20}\033[0m")
                print(f"\033[90m{'-'*12} {'-'*40} {'-'*20}\033[0m")
                
                for file in files:
                    created = file.get('createdTime', '').split('T')[0] if 'createdTime' in file else ''
                    print(f"{file['id'][:10]:<12} \033[1m{file['name'][:38]:<40}\033[0m {created:<20}")
                print()
                
            except Exception as e:
                print(f"\033[31m✘ Error listing recently created files:\033[0m {e}")
                
        else:
            print(f"\033[31m✘ Unknown item type: {item_type}\033[0m")
            print("\033[33m! Valid types: emails, drafts, sent, files, created\033[0m")
    
    def _split_content_into_segments(self, content):
        """Split content into logical segments for extraction."""
        # First try to split by double newlines (paragraphs)
        segments = [seg.strip() for seg in content.split("\n\n") if seg.strip()]
        
        # If we have very few segments, try splitting by single newlines
        if len(segments) <= 2:
            segments = [seg.strip() for seg in content.split("\n") if seg.strip()]
            
        # If we still have too few segments or some are too long,
        # try to further split paragraphs
        refined_segments = []
        for segment in segments:
            # If segment is short enough, keep as is
            if len(segment) < 500:
                refined_segments.append(segment)
            else:
                # Try to split by sentences for long segments
                sentences = segment.replace('. ', '.\n').split('\n')
                current_segment = []
                current_length = 0
                
                for sentence in sentences:
                    if current_length + len(sentence) > 500 and current_segment:
                        refined_segments.append(' '.join(current_segment))
                        current_segment = [sentence]
                        current_length = len(sentence)
                    else:
                        current_segment.append(sentence)
                        current_length += len(sentence)
                
                if current_segment:
                    refined_segments.append(' '.join(current_segment))
        
        # If we have meaningful segments, use them, otherwise fall back to original segments
        if refined_segments and len(refined_segments) > 1:
            return refined_segments
        
        # If we still have too few segments, just use the original content as a single segment
        if not segments:
            return [content]
            
        return segments
    
    def do_extract(self, arg):
        """Extract and edit message segments: extract <message_index> [<export_action>]
        
        export_action can be:
        - email: Create a draft email with the extracted content
        - document: Create a Google Doc with the extracted content
        - save: Save to a text file
        - clipboard: Copy to clipboard (if available)
        """
        if not self.current_conversation:
            print("\033[33m! No conversation to extract from\033[0m")
            return
            
        args = arg.split(None, 1)
        if not args:
            print("\033[33m! Please provide a message index\033[0m")
            return
            
        # Get message index
        try:
            msg_idx = int(args[0]) - 1  # Convert to 0-based index
            if msg_idx < 0 or msg_idx >= len(self.current_conversation):
                print(f"\033[31m✘\033[0m Invalid message index. Valid range: 1-{len(self.current_conversation)}")
                return
        except ValueError:
            print("\033[31m✘\033[0m Message index must be a number")
            return
            
        # Get the message
        message = self.current_conversation[msg_idx]
        content = ""
        role = message.get("role", "unknown")
        
        # Extract text from content based on format (string or structured content blocks)
        if isinstance(message.get("content"), str):
            content = message.get("content", "")
        elif isinstance(message.get("content"), list):
            # Handle structured content blocks
            content_blocks = []
            for block in message.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    content_blocks.append(block.get("text", ""))
            content = "\n\n".join(content_blocks)
        
        # Show content with segment markers
        segments = self._split_content_into_segments(content)
        
        print(f"\n\033[1;36mMessage {msg_idx+1} ({role}):\033[0m\n")
        for i, segment in enumerate(segments):
            print(f"\033[1;33m[{i+1}]\033[0m {segment}\n")
            
        # Ask which segments to include
        include_prompt = "Enter segment numbers to include (comma-separated, e.g. 1,3,5), or 'all': "
        include_input = input(include_prompt).strip()
        
        if not include_input or include_input.lower() == 'cancel':
            print("\033[33m! Extraction cancelled\033[0m")
            return
            
        # Determine which segments to include
        selected_segments = []
        if include_input.lower() == 'all':
            selected_segments = segments
        else:
            try:
                segment_indices = [int(idx.strip()) - 1 for idx in include_input.split(',')]
                for idx in segment_indices:
                    if 0 <= idx < len(segments):
                        selected_segments.append(segments[idx])
                    else:
                        print(f"\033[33m! Invalid segment index {idx+1}, skipping\033[0m")
            except ValueError:
                print("\033[31m✘\033[0m Invalid input. Using all segments.")
                selected_segments = segments
                
        if not selected_segments:
            print("\033[33m! No valid segments selected\033[0m")
            return
            
        # Combine selected segments
        combined_text = "\n\n".join(selected_segments)
        
        # Allow editing
        edit_prompt = "\nEdit selected text? (y/n): "
        if input(edit_prompt).lower().startswith('y'):
            print("\n\033[1;36mEditing Mode\033[0m")
            print("Edit the text below. Enter a single '.' on a line to finish.\n")
            print(combined_text)
            print("\n--- Start editing below ---")
            
            # Collect edited text
            edited_lines = []
            while True:
                line = input()
                if line == '.':
                    break
                edited_lines.append(line)
                
            if edited_lines:
                combined_text = "\n".join(edited_lines)
                print("\n\033[32m✓\033[0m Text updated")
            else:
                print("\n\033[33m! No changes made\033[0m")
            
        # Determine export action
        export_action = args[1].lower() if len(args) > 1 else None
        if not export_action:
            export_options = [
                ("1", "Create email draft"),
                ("2", "Create Google Doc"),
                ("3", "Save to text file"),
                ("4", "Display only (no export)")
            ]
            
            print("\n\033[1;36mExport Options:\033[0m")
            for opt_num, opt_desc in export_options:
                print(f"{opt_num}. {opt_desc}")
                
            export_choice = input("\nChoose export option (1-4): ").strip()
            
            if export_choice == '1':
                export_action = 'email'
            elif export_choice == '2':
                export_action = 'document'
            elif export_choice == '3':
                export_action = 'save'
            else:
                export_action = 'display'
        
        # Handle export based on action
        if export_action == 'email':
            if not self.gmail:
                print("\033[31m✘\033[0m Gmail service not initialized. Run \033[1msetup\033[0m first.")
                return
                
            # Get email details
            print("\n\033[1;36mEmail Draft Creation\033[0m")
            to = input("\033[1mTo:\033[0m ").strip()
            if not to:
                print("\033[33m! Email recipient is required\033[0m")
                return
                
            subject = input("\033[1mSubject:\033[0m ").strip()
            if not subject:
                print("\033[33m! Email subject is required\033[0m")
                return
                
            # Add CC/BCC if needed
            cc = input("\033[1mCC:\033[0m ").strip()
            bcc = input("\033[1mBCC:\033[0m ").strip()
            
            try:
                print("\033[90mCreating email draft...\033[0m")
                draft_id = self.gmail.create_draft(to, subject, combined_text, cc, bcc)
                print(f"\033[32m✓\033[0m Draft created! ID: \033[1m{draft_id}\033[0m")
            except Exception as e:
                print(f"\033[31m✘\033[0m Error creating draft: {e}")
                
        elif export_action == 'document':
            if not self.drive:
                print("\033[31m✘\033[0m Drive service not initialized. Run \033[1msetup\033[0m first.")
                return
                
            # Get document details
            print("\n\033[1;36mGoogle Doc Creation\033[0m")
            doc_name = input("\033[1mDocument name:\033[0m ").strip()
            if not doc_name:
                doc_name = f"Extracted content {time.strftime('%Y-%m-%d %H:%M')}"
                
            try:
                print("\033[90mCreating Google Doc...\033[0m")
                doc = self.drive.create_document(doc_name, combined_text)
                print(f"\033[32m✓\033[0m Document created: \033[1m{doc['name']}\033[0m")
                print(f"  Link: {doc.get('webViewLink', 'Not available')}")
            except Exception as e:
                print(f"\033[31m✘\033[0m Error creating document: {e}")
                
        elif export_action == 'save':
            # Get file details
            print("\n\033[1;36mSave to Text File\033[0m")
            file_name = input("\033[1mFile name (without extension):\033[0m ").strip()
            if not file_name:
                file_name = f"extracted_{int(time.time())}"
                
            file_name = f"{file_name}.txt"
            
            try:
                # Create export directory if it doesn't exist
                export_dir = os.path.join(CONFIG_DIR, "exports")
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)
                    
                # Save to file
                file_path = os.path.join(export_dir, file_name)
                with open(file_path, 'w') as f:
                    f.write(combined_text)
                    
                print(f"\033[32m✓\033[0m Text saved to \033[1m{file_path}\033[0m")
            except Exception as e:
                print(f"\033[31m✘\033[0m Error saving file: {e}")
                
        else:  # display only
            print("\n\033[1;36mExtracted Content:\033[0m")
            print("\033[90m" + "=" * 60 + "\033[0m")
            print(combined_text)
            print("\033[90m" + "=" * 60 + "\033[0m")

    def do_mcp(self, arg):
        """Manage MCP server integration"""
        args = arg.split()
        if not args:
            print("\033[33m! Usage: mcp [status|setup|info]\033[0m")
            return
        
        cmd = args[0].lower()
        
        if cmd == "status":
            print("\n\033[1;36mMCP Server Status:\033[0m")
            print("  \033[33m! MCP integration not enabled in this CLI version\033[0m")
            print("  Use the full MCP server implementation for direct MCP protocol support")
        
        elif cmd == "setup":
            print("\n\033[1;36mMCP Server Setup:\033[0m")
            print("  \033[33m! MCP server setup is not available in this CLI version\033[0m")
            print("  This simplified CLI provides Gmail and Drive functionality directly")
            print("  without requiring the MCP protocol layer")
        
        elif cmd == "info":
            print("\n\033[1;36mMCP Information:\033[0m")
            print("  Model Context Protocol (MCP) is a standardized way for AI models")
            print("  to interact with external tools and services.")
            print("  This CLI provides direct integration with Gmail and Drive without")
            print("  using the full MCP protocol layer.")
            print("\n  For full MCP support, use the dedicated MCP server implementations:")
            print("  - Gmail: @modelcontextprotocol/server-gmail")
            print("  - Drive: @modelcontextprotocol/server-gdrive")
        
        else:
            print(f"\033[33m! Unknown MCP command: {cmd}\033[0m")
            print("  Available commands: status, setup, info")
    
    def default(self, line):
        """Default handler: treat as chat message"""
        return self.do_chat(line)
        
    def do_help(self, arg):
        """List available commands or get help for a specific command"""
        if arg:
            # Help for specific commands
            if arg == "brave" or arg == "web_search" or arg == "local_search":
                print("\n\033[1;36mBrave Search Commands:\033[0m")
                print("\n  \033[1mweb_search\033[0m <query> [count]")
                print("    Search the web using Brave Search API")
                print("    - query: The search query to perform")
                print("    - count: Number of results to return (max 20, default 10)")
                print("\n  \033[1mlocal_search\033[0m <query> [count]")
                print("    Search for local businesses and services")
                print("    - query: What you're looking for locally")
                print("    - count: Number of results to return (max 20, default 10)")
                print("\n  Example: web_search Claude AI capabilities 5")
                print("  Example: local_search coffee shops near me")
                return
            elif arg == "email" or arg == "gmail":
                print("\n\033[1;36mEmail Commands:\033[0m")
                print("\n  \033[1memail_list\033[0m [query]")
                print("    List recent emails, optionally filtered by search query")
                print("    - query: Optional search terms (e.g., 'from:someone@example.com')")
                print("\n  \033[1memail_read\033[0m <email_id>")
                print("    Read a specific email by ID")
                print("    - email_id: ID of the email to read (from email_list)")
                print("\n  \033[1memail_compose\033[0m")
                print("    Compose an email interactively with prompts for recipients, subject, and body")
                print("\n  \033[1memail_send\033[0m <to> <subject> <body>")
                print("    Send an email directly from the command line")
                print("\n  \033[1memail_drafts\033[0m [view|send] [draft_id]")
                print("    Manage email drafts - list, view, or send")
                print("\n  Example: email_list from:company.com after:2023/01/01")
                print("  Example: email_read ABCdef123")
                print("  Example: email_drafts view draft123")
                return
            elif arg == "drive" or arg == "gdrive":
                print("\n\033[1;36mDrive Commands:\033[0m")
                print("\n  \033[1mdrive_list\033[0m [query]")
                print("    List files in Google Drive, optionally filtered by search query")
                print("    - query: Optional search terms (e.g., 'name contains report')")
                print("\n  \033[1mdrive_download\033[0m <file_id> [output_path]")
                print("    Download a file from Google Drive")
                print("    - file_id: ID of the file to download (from drive_list)")
                print("    - output_path: Optional path to save the file (defaults to current dir)")
                print("\n  \033[1mdrive_create\033[0m <type> <name>")
                print("    Create a new file in Google Drive")
                print("    - type: Type of file to create (document, spreadsheet, folder)")
                print("    - name: Name for the new file")
                print("\n  \033[1mdrive_shared\033[0m")
                print("    List files shared with you")
                print("\n  \033[1mdrive_share\033[0m <file_id> <email> [role]")
                print("    Share a file with someone")
                print("    - file_id: ID of the file to share")
                print("    - email: Email address to share with")
                print("    - role: Sharing permission (reader, writer, commenter), defaults to reader")
                print("\n  Example: drive_list name contains 'report'")
                print("  Example: drive_download 1a2b3c4d5e /home/user/downloads/myfile.pdf")
                print("  Example: drive_create document 'Meeting Notes'")
                return
            elif arg == "extract":
                print("\n\033[1;36mExtract Command:\033[0m")
                print("\n  \033[1mextract\033[0m <message_index> [export_action]")
                print("    Extract and edit segments from conversation messages")
                print("    - message_index: Index of the message in the conversation (starting at 1)")
                print("    - export_action: Optional export method (email, document, save, display)")
                print("\n  This command lets you:")
                print("    1. Select a message from the current conversation")
                print("    2. Choose specific segments from the message to extract")
                print("    3. Edit the extracted content")
                print("    4. Export the content to various destinations:")
                print("       - Create a draft email")
                print("       - Create a Google Doc")
                print("       - Save to a text file")
                print("       - Simply display the extracted content")
                print("\n  Example: extract 3 email")
                print("  Example: extract 2 document")
                return
            elif arg == "refresh":
                print("\n\033[1;36mRefresh Command:\033[0m")
                print("\n  \033[1mrefresh\033[0m [service]")
                print("    Refresh service connections and tokens without running full setup")
                print("    - service: Optional service to refresh (default: all)")
                print("\n  Available services:")
                print("    - all: Refresh all services (default)")
                print("    - gmail: Refresh Gmail connection and token")
                print("    - drive: Refresh Google Drive connection and token") 
                print("    - anthropic: Refresh Claude API connection")
                print("    - brave: Refresh Brave Search API connection")
                print("\n  Use this command when:")
                print("    - You encounter authentication errors")
                print("    - Tokens have expired")
                print("    - API connections are failing")
                print("\n  Example: refresh")
                print("  Example: refresh gmail")
                print("  Example: refresh drive")
                return
            elif arg == "recent":
                print("\n\033[1;36mRecent Command:\033[0m")
                print("\n  \033[1mrecent\033[0m <type> [count]")
                print("    Show recent items of various types")
                print("    - type: Type of items to show (emails, drafts, sent, files, created)")
                print("    - count: Optional number of items to show (default: 5)")
                print("\n  Available types:")
                print("    - emails: Recent received emails")
                print("    - drafts: Email drafts")
                print("    - sent: Recently sent emails")
                print("    - files: Recently modified Google Drive files")
                print("    - created: Recently created Google Drive files")
                print("\n  Example: recent emails 10")
                print("  Example: recent files")
                print("  Example: recent created 3")
                return
            else:
                # Use default help for other commands
                super().do_help(arg)
        else:
            # Custom help display
            print("\n\033[1;36mSimpleAnthropicCLI v2 Help\033[0m")
            print("\n\033[1mChat Commands:\033[0m")
            print("  \033[1mchat\033[0m <message>     Chat with Claude")
            print("  \033[1mmodel\033[0m               View or change the current Claude model")
            print("  \033[1mclear\033[0m               Clear the current conversation")
            print("  \033[1mreset\033[0m               Reset CLI state (use when tool errors occur)")
            
            print("\n\033[1mConversation Management:\033[0m")
            print("  \033[1msave_conversation\033[0m [filename]   Save the current conversation")
            print("  \033[1mload_conversation\033[0m <filename>   Load a saved conversation")
            print("  \033[1mlist_conversations\033[0m             List saved conversations")
            
            print("\n\033[1mClaude 3.7 Features:\033[0m")
            print("  \033[1mthinking\033[0m [on|off|budget <n>|show|hide]  Configure extended thinking")
            print("  \033[1mtools\033[0m [on|off|list]  Configure tool use (function calling)")
            print("  \033[1mextended_output\033[0m [on|off]  Configure extended output (128k tokens)")
            
            print("\n\033[1mSetup & Configuration:\033[0m")
            print("  \033[1msetup\033[0m               Run the setup wizard")
            print("  \033[1mstatus\033[0m              Check service status")
            print("  \033[1mconfig\033[0m              View or change configuration settings")
            print("  \033[1mrefresh\033[0m [service]    Refresh service connections and tokens")
            
            print("\n\033[1mEmail Commands:\033[0m")
            print("  \033[1memail_list\033[0m [query]  List emails, optionally with search query")
            print("  \033[1memail_read\033[0m <id>     Read a specific email by ID")
            print("  \033[1memail_compose\033[0m       Compose an email interactively")
            print("  \033[1memail_send\033[0m <to> <subject> <body>  Send an email")
            print("  \033[1memail_drafts\033[0m        List email drafts")
            
            print("\n\033[1mDrive Commands:\033[0m")
            print("  \033[1mdrive_list\033[0m [query]  List Drive files, optionally with search query")
            print("  \033[1mdrive_download\033[0m <id> [path]  Download a file from Drive")
            print("  \033[1mdrive_create\033[0m <type> <n>  Create a new file in Drive")
            print("  \033[1mdrive_shared\033[0m        List files shared with you")
            print("  \033[1mdrive_share\033[0m <id> <email> [role]  Share a file with someone")
            
            print("\n\033[1mSearch Commands:\033[0m")
            print("  \033[1mweb_search\033[0m <query> [count]  Search the web with Brave Search")
            print("  \033[1mlocal_search\033[0m <query> [count]  Search for local businesses and services")
            print("  \033[1mrecent\033[0m <type> [count]  Show recent emails, drafts, files, etc.")
            print("  Type 'help brave' for more details on search commands")
            
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
        print("\033[31m✘ Error:\033[0m The following required API keys are missing from your .env file:")
        for key in missing_required:
            print(f"  - {key}")
        print("\nPlease add them to your .env file in the format: KEY=value")
        return False
        
    if missing_recommended:
        print("\033[33m! Warning:\033[0m The following recommended API keys are missing from your .env file:")
        for key in missing_recommended:
            print(f"  - {key}")
        print("\nSome features may not work without these keys.")
    
    return len(missing_required) == 0

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="SimpleAnthropicCLI v3")
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
    args = parser.parse_args()
    
    # Set API key from args or .env file
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    elif not validate_env_file():
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
        cli.do_setup("")
    
    # Print a welcome banner
    os.system('clear' if os.name == 'posix' else 'cls')
    print("\033[1;36m" + "="*60 + "\033[0m")
    print("\033[1;36m    SimpleAnthropicCLI v2.0.0\033[0m")
    print("\033[1;36m" + "="*60 + "\033[0m")
    print("\n\033[90mType 'help' for a list of commands, 'status' to check service status\033[0m\n")
    
    # Start CLI
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\n\033[1;36mGoodbye!\033[0m")
        return 0
    except Exception as e:
        print(f"\033[31m✘ Error:\033[0m {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())