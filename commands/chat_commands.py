#!/usr/bin/env python3
"""
Chat-related command handlers for SimpleAnthropicCLI
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Union, Callable

from utils.logging_utils import log_exception
from utils.history_utils import add_history_entry, save_conversation, load_conversation

class ChatCommands:
    """Chat commands for the SimpleAnthropicCLI."""
    
    def __init__(self, cli_instance):
        """Initialize with a reference to the CLI instance.
        
        Args:
            cli_instance: The AnthropicCLI instance
        """
        self.cli = cli_instance
    
    def handle_chat(self, arg: str) -> None:
        """Handle the chat command.
        
        Args:
            arg: The message to send to Claude
        """
        if not arg:
            self.cli.print_message("Please provide a message to send to Claude.", "warning")
            return
        
        # Add message to conversation
        self.cli.current_conversation.append({"role": "user", "content": arg})
        
        # Determine if we're using tools
        use_tools = self.cli.config.get("use_tools", True)
        tools = self.cli.tools if use_tools else None
        
        try:
            # Show typing indicator
            print("\033[90mClaude is thinking...\033[0m", end="\n", flush=True)
            
            # Get response from Claude
            response = self.cli.anthropic.send_message(self.cli.current_conversation, tools=tools)
            
            # Clear typing indicator - no need with newline approach
            
            # Process the response
            if isinstance(response, dict):
                # Extract thinking if available
                thinking_found = False
                text_content = ""
                tool_calls = []
                
                for content_block in response.get("content", []):
                    if content_block["type"] == "thinking":
                        thinking_found = True
                        if self.cli.config.get("show_thinking", True):
                            self._display_thinking(content_block["thinking"])
                    elif content_block["type"] == "text":
                        text_content = content_block["text"]
                    elif content_block["type"] == "tool_use":
                        tool_calls = content_block.get("tools", [])
                
                # Handle any tool calls
                if tool_calls:
                    self.cli.print_message("Claude is requesting tool use:", "info")
                    tool_results = self._handle_tool_calls(tool_calls)
                    
                    # We don't add the initial assistant response with tool calls to the conversation
                    # Instead, just add the tool results
                    for result in tool_results:
                        self.cli.current_conversation.append(result)
                    
                    # Now get a follow-up response after tool use
                    print("\033[90mGetting Claude's response after tool use...\033[0m", end="\n", flush=True)
                    follow_up = self.cli.anthropic.send_message(self.cli.current_conversation, tools=tools)
                    
                    # Extract text from follow-up
                    if isinstance(follow_up, dict):
                        for content_block in follow_up.get("content", []):
                            if content_block["type"] == "text":
                                text_content = content_block["text"]
                                break
                        
                        # Update conversation with this final response
                        self.cli.current_conversation.append({
                            "role": "assistant",
                            "content": follow_up.get("content", [])
                        })
                    else:
                        text_content = follow_up
                        self.cli.current_conversation.append({
                            "role": "assistant", 
                            "content": text_content
                        })
                else:
                    # Add response to conversation
                    self.cli.current_conversation.append({
                        "role": "assistant",
                        "content": response.get("content", [])
                    })
            else:
                # Simple text response
                text_content = response
                self.cli.current_conversation.append({
                    "role": "assistant", 
                    "content": text_content
                })
            
            # Print the text response
            print("\n\033[1;34mClaude:\033[0m")
            self.cli._print_wrapped(text_content, "  ")
            print()
            
            # Add to history
            add_history_entry(
                user_message=arg,
                assistant_message=text_content,
                model=self.cli.config["model"]
            )
            
        except Exception as e:
            log_exception(e, "Error communicating with Claude")
            self.cli.print_message(f"Error communicating with Claude: {e}", "error")
    
    def _display_thinking(self, thinking_content: str) -> None:
        """Display Claude's thinking process.
        
        Args:
            thinking_content: The thinking content to display
        """
        print("\n\033[1;35m🧠 Claude's thinking process:\033[0m")
        print("\033[90m" + "=" * 60 + "\033[0m")
        self.cli._print_wrapped(thinking_content, "  ")
        print("\033[90m" + "=" * 60 + "\033[0m\n")
    
    def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Handle tool calls from Claude's response.
        
        Args:
            tool_calls: List of tool call objects
            
        Returns:
            List of tool result objects
        """
        tool_results = []
        
        print("\n\033[90mExecuting tool calls...\033[0m\n")
        
        for tool_call in tool_calls:
            tool_id = tool_call.get("id")
            tool_name = tool_call.get("name")
            tool_params = tool_call.get("input", {})
            
            print(f"\033[1;33m⚙️ Calling tool:\033[0m \033[1m{tool_name}\033[0m")
            print(f"  Parameters: {json.dumps(tool_params, indent=2)}")
            
            try:
                # Execute the tool
                result = self.cli._execute_tool(tool_name, tool_params)
                
                # Add to results
                tool_results.append({
                    "tool_call_id": tool_id,
                    "role": "tool",
                    "content": json.dumps(result, indent=2)
                })
                
                print(f"  \033[32m✓\033[0m Tool execution complete\n")
            except Exception as e:
                log_exception(e, f"Error executing tool {tool_name}")
                error_result = {"error": f"Error executing tool: {str(e)}"}
                tool_results.append({
                    "tool_call_id": tool_id,
                    "role": "tool",
                    "content": json.dumps(error_result, indent=2)
                })
                print(f"  \033[31m✘\033[0m Tool execution failed: {e}\n")
        
        return tool_results
    
    def handle_thinking(self, arg: str) -> None:
        """Handle the thinking command.
        
        Args:
            arg: Command arguments
        """
        if not arg:
            # Show current thinking configuration
            enabled = self.cli.config.get("thinking_enabled", True)
            budget = self.cli.config.get("thinking_budget", 16000)
            show = self.cli.config.get("show_thinking", True)
            
            print("\n\033[1;36mExtended Thinking Configuration:\033[0m")
            print(f"  Status: {'Enabled' if enabled else 'Disabled'}")
            print(f"  Budget: {budget} tokens")
            print(f"  Display: {'Show' if show else 'Hide'}")
            return
        
        args = arg.split()
        cmd = args[0].lower()
        
        if cmd == "on":
            self.cli.config["thinking_enabled"] = True
            self.cli.anthropic.thinking_enabled = True
            self.cli.print_message("Extended thinking enabled", "success")
        
        elif cmd == "off":
            self.cli.config["thinking_enabled"] = False
            self.cli.anthropic.thinking_enabled = False
            self.cli.print_message("Extended thinking disabled", "success")
        
        elif cmd == "show":
            self.cli.config["show_thinking"] = True
            self.cli.print_message("Claude's thinking process will be shown", "success")
        
        elif cmd == "hide":
            self.cli.config["show_thinking"] = False
            self.cli.print_message("Claude's thinking process will be hidden", "success")
        
        elif cmd == "budget" and len(args) > 1:
            try:
                budget = int(args[1])
                if budget < 1024:
                    self.cli.print_message("Minimum budget is 1024 tokens. Setting to 1024.", "warning")
                    budget = 1024
                
                self.cli.config["thinking_budget"] = budget
                self.cli.anthropic.thinking_budget = budget
                self.cli.print_message(f"Thinking budget set to {budget} tokens", "success")
            except ValueError:
                self.cli.print_message("Budget must be a number", "error")
        
        else:
            self.cli.print_message("Usage: thinking [on|off|show|hide|budget <number>]", "warning")
        
        # Save configuration
        self.cli._save_config()
    
    def handle_tools(self, arg: str) -> None:
        """Handle the tools command.
        
        Args:
            arg: Command arguments
        """
        if not arg:
            # Show current tools configuration
            enabled = self.cli.config.get("use_tools", True)
            
            print("\n\033[1;36mTool Use Configuration:\033[0m")
            print(f"  Status: {'Enabled' if enabled else 'Disabled'}")
            print(f"  Available Tools: {len(self.cli.tools)}")
            return
        
        cmd = arg.lower()
        
        if cmd == "on":
            self.cli.config["use_tools"] = True
            self.cli.print_message("Tool use enabled", "success")
        
        elif cmd == "off":
            self.cli.config["use_tools"] = False
            self.cli.print_message("Tool use disabled", "success")
        
        elif cmd == "list":
            print("\n\033[1;36mAvailable Tools:\033[0m")
            for tool in self.cli.tools:
                print(f"  \033[1m{tool['name']}\033[0m: {tool['description']}")
                required_params = tool['input_schema'].get('required', [])
                print(f"  Required parameters: {', '.join(required_params)}")
                print()
        
        else:
            self.cli.print_message("Usage: tools [on|off|list]", "warning")
        
        # Save configuration
        self.cli._save_config()
    
    def handle_clear(self, arg: str) -> None:
        """Handle the clear command.
        
        Args:
            arg: Command arguments (unused)
        """
        self.cli.current_conversation = []
        self.cli.print_message("Conversation cleared.", "success")
    
    def handle_reset(self, arg: str) -> None:
        """Handle the reset command.
        
        Args:
            arg: Command arguments (unused)
        """
        self.cli.current_conversation = []
        self.cli.print_message("CLI state reset. Any corrupted conversation state has been cleared.", "success")
    
    def handle_save_conversation(self, arg: str) -> None:
        """Handle the save_conversation command.
        
        Args:
            arg: Optional filename
        """
        if not self.cli.current_conversation:
            self.cli.print_message("No conversation to save", "warning")
            return
            
        filename = arg if arg else f"conversation_{int(time.time())}.json"
        
        try:
            filepath = save_conversation(
                messages=self.cli.current_conversation,
                model=self.cli.config["model"],
                filename=filename
            )
            self.cli.print_message(f"Conversation saved to {filepath}", "success")
        except Exception as e:
            log_exception(e, "Error saving conversation")
            self.cli.print_message(f"Error saving conversation: {e}", "error")
    
    def handle_load_conversation(self, arg: str) -> None:
        """Handle the load_conversation command.
        
        Args:
            arg: Filename to load
        """
        if not arg:
            self.cli.print_message("Please provide a filename", "warning")
            return
        
        try:
            data = load_conversation(arg)
            
            # Ask for confirmation if there's an existing conversation
            if self.cli.current_conversation:
                response = input("\033[33m! Current conversation will be replaced. Continue? (y/n) \033[0m")
                if response.lower() != 'y':
                    self.cli.print_message("Load cancelled", "warning")
                    return
            
            # Load the conversation
            self.cli.current_conversation = data.get("messages", [])
            
            # Set the model if specified
            loaded_model = data.get("model")
            if loaded_model and loaded_model in self.cli.MODELS:
                self.cli.config["model"] = loaded_model
                self.cli.anthropic.model = loaded_model
                print(f"\033[32m✓\033[0m Model set to \033[1m{loaded_model}\033[0m")
            
            # Print confirmation
            message_count = len(self.cli.current_conversation)
            self.cli.print_message(f"Loaded conversation with {message_count} messages", "success")
            
            # Print conversation summary
            if message_count > 0:
                print("\n\033[1;36mConversation Summary:\033[0m")
                for i, msg in enumerate(self.cli.current_conversation):
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
            log_exception(e, "Error loading conversation")
            self.cli.print_message(f"Error loading conversation: {e}", "error")
            
    def handle_list_conversations(self, arg: str) -> None:
        """Handle the list_conversations command.
        
        Args:
            arg: Command arguments (unused)
        """
        import os
        
        # Get conversations directory
        config_dir = os.path.expanduser("~/.simple_anthropic_cli")
        conversations_dir = os.path.join(config_dir, "conversations")
        
        # Ensure directory exists
        if not os.path.exists(conversations_dir):
            os.makedirs(conversations_dir, exist_ok=True)
        
        # Get all JSON files in the directory
        files = [f for f in os.listdir(conversations_dir) if f.endswith('.json')]
        
        if not files:
            self.cli.print_message("No saved conversations found", "warning")
            return
        
        # Sort by modification time (newest first)
        files.sort(key=lambda f: os.path.getmtime(os.path.join(conversations_dir, f)), reverse=True)
        
        print("\n\033[1;36mSaved Conversations:\033[0m\n")
        
        for i, filename in enumerate(files, 1):
            file_path = os.path.join(conversations_dir, filename)
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
            
            # Format time and size
            mtime_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/(1024*1024):.1f} MB"
            
            # Try to load the file to get message count
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                message_count = len(data.get("messages", [])) if isinstance(data, dict) else 0
            except:
                message_count = "?"
            
            # Display filename without .json extension
            display_name = filename[:-5] if filename.endswith('.json') else filename
            
            print(f"{i}. \033[1m{display_name}\033[0m")
            print(f"   {mtime_str} | {size_str} | {message_count} messages")
        
        print(f"\nUse 'load_conversation <name>' to load a conversation.")
        print()