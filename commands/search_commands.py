#!/usr/bin/env python3
"""
Search-related command handlers for SimpleAnthropicCLI
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Union

from utils.logging_utils import log_exception

class SearchCommands:
    """Search commands for the SimpleAnthropicCLI."""
    
    def __init__(self, cli_instance):
        """Initialize with a reference to the CLI instance.
        
        Args:
            cli_instance: The AnthropicCLI instance
        """
        self.cli = cli_instance
    
    def _ensure_brave_authentication(self):
        """Helper method to handle Brave authentication issues
        
        Returns:
            bool: True if authentication is successful, False otherwise
        """
        if not self.cli.brave:
            self.cli.print_message("Brave Search service not initialized. Run setup first or add BRAVE_API_KEY.", "error")
            return False
        
        return True
    
    def _display_web_search_results(self, results):
        """Helper method to display web search results nicely."""
        if not results or not results.get('web', {}).get('results'):
            self.cli.print_message("No results found", "warning")
            return
        
        web_results = results['web']['results']
        
        print(f"\n\033[1;36mSearch Results ({len(web_results)} found):\033[0m\n")
        
        for i, result in enumerate(web_results, 1):
            title = result.get('title', 'No title')
            url = result.get('url', 'No URL')
            description = result.get('description', 'No description')
            
            # Clean up description
            description = description.replace('\n', ' ').strip()
            
            print(f"\033[1;33m[{i}]\033[0m \033[1m{title}\033[0m")
            print(f"\033[90m{url}\033[0m")
            print(description)
            print()
    
    def handle_web_search(self, arg):
        """Search the web: web_search <query> [--count=<n>]"""
        if not self._ensure_brave_authentication():
            return
        
        if not arg:
            self.cli.print_message("Please provide a search query", "warning")
            return
        
        # Parse arguments
        parts = arg.split(' --')
        query = parts[0]
        
        count = 5  # Default count
        offset = 0  # Default offset
        
        # Parse options
        for i in range(1, len(parts)):
            option = '--' + parts[i]
            if option.startswith('--count='):
                try:
                    count = int(option.split('=')[1])
                except (ValueError, IndexError):
                    self.cli.print_message("Invalid count value", "error")
                    return
            elif option.startswith('--offset='):
                try:
                    offset = int(option.split('=')[1])
                except (ValueError, IndexError):
                    self.cli.print_message("Invalid offset value", "error")
                    return
        
        try:
            self.cli.print_message(f"Searching for: {query}", "info")
            results = self.cli.brave.web_search(query=query, count=count, offset=offset)
            
            self._display_web_search_results(results)
            
        except Exception as e:
            log_exception(e, "Error during web search")
            self.cli.print_message(f"Search error: {e}", "error")
    
    def handle_local_search(self, arg):
        """Search your documents and emails: local_search <query>"""
        if not arg:
            self.cli.print_message("Please provide a search query", "warning")
            return
        
        print("\n\033[1;36mLocal Search Results:\033[0m\n")
        
        # Track if we have any results at all
        any_results = False
        
        # Search emails if Gmail service is available
        if self.cli.gmail:
            try:
                self.cli.print_message("Searching emails...", "info")
                emails = self.cli.gmail.list_emails(query=arg, max_results=3)
                
                if emails:
                    any_results = True
                    print("\033[1;33mEmails:\033[0m")
                    for email in emails:
                        print(f"  \033[1m{email['subject']}\033[0m")
                        print(f"  From: {email['from']}")
                        print(f"  Date: {email['date']}")
                        print(f"  ID: {email['id']}")
                        print()
            except Exception as e:
                log_exception(e, "Error searching emails")
                self.cli.print_message(f"Email search error: {e}", "error")
        
        # Search Drive if service is available
        if self.cli.drive:
            try:
                self.cli.print_message("Searching Drive...", "info")
                files = self.cli.drive.list_files(query=arg, max_results=3)
                
                if files:
                    any_results = True
                    print("\033[1;33mDrive Files:\033[0m")
                    for file in files:
                        file_id = file.get('id', 'Unknown')
                        file_type = file.get('mimeType', 'Unknown').split('/')[-1]
                        file_name = file.get('name', 'Unnamed')
                        
                        # Format type nicely
                        if 'folder' in file_type:
                            file_type = 'Folder'
                        elif 'document' in file_type:
                            file_type = 'Document'
                        elif 'spreadsheet' in file_type:
                            file_type = 'Spreadsheet'
                        elif 'presentation' in file_type:
                            file_type = 'Presentation'
                        
                        print(f"  \033[1m{file_name}\033[0m ({file_type})")
                        print(f"  ID: {file_id}")
                        if file.get('webViewLink'):
                            print(f"  Link: {file.get('webViewLink')}")
                        print()
            except Exception as e:
                log_exception(e, "Error searching Drive files")
                self.cli.print_message(f"Drive search error: {e}", "error")
        
        # Also do a web search if Brave service is available
        if self.cli.brave:
            try:
                self.cli.print_message("Searching the web...", "info")
                results = self.cli.brave.web_search(query=arg, count=3, offset=0)
                
                if results and results.get('web', {}).get('results'):
                    any_results = True
                    web_results = results['web']['results']
                    
                    print("\033[1;33mWeb Results:\033[0m")
                    for result in web_results:
                        title = result.get('title', 'No title')
                        url = result.get('url', 'No URL')
                        
                        print(f"  \033[1m{title}\033[0m")
                        print(f"  {url}")
                        print()
            except Exception as e:
                log_exception(e, "Error during web search")
                self.cli.print_message(f"Web search error: {e}", "error")
        
        if not any_results:
            self.cli.print_message("No results found in any source", "warning")