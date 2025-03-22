#!/usr/bin/env python3
"""
Drive-related command handlers for SimpleAnthropicCLI
"""

import os
import time
import logging
import json
from typing import Dict, List, Any, Optional, Union

from utils.logging_utils import log_exception

class DriveCommands:
    """Drive commands for the SimpleAnthropicCLI."""
    
    def __init__(self, cli_instance):
        """Initialize with a reference to the CLI instance.
        
        Args:
            cli_instance: The AnthropicCLI instance
        """
        self.cli = cli_instance
    
    def _ensure_drive_authentication(self):
        """Helper method to handle Drive authentication issues
        
        Returns:
            bool: True if authentication is successful, False otherwise
        """
        if not self.cli.drive:
            self.cli.print_message("Drive service not initialized. Run setup first.", "error")
            return False
        
        return True
    
    def handle_drive_list(self, arg):
        """List files on Google Drive: drive_list [query]"""
        if not self._ensure_drive_authentication():
            return
        
        try:
            self.cli.print_message("Fetching files...", "info")
            
            # Parse arguments
            args = arg.split()
            query = None
            max_results = 10
            
            if args:
                # If argument doesn't look like a flag, treat it as a query
                if args[0].startswith('--'):
                    i = 0
                    while i < len(args):
                        if args[i] == '--max' and i + 1 < len(args):
                            try:
                                max_results = int(args[i + 1])
                                i += 2
                            except ValueError:
                                self.cli.print_message(f"Invalid max results value: {args[i + 1]}", "error")
                                return
                        else:
                            i += 1
                    
                    # Reconstruct query from remaining args
                    query_args = [arg for arg in args if not arg.startswith('--') and 
                                  args.index(arg) - 1 >= 0 and args[args.index(arg) - 1] != '--max']
                    if query_args:
                        query = ' '.join(query_args)
                else:
                    query = arg
            
            # Get files
            files = self.cli.drive.list_files(query=query, max_results=max_results)
            
            if not files:
                self.cli.print_message("No files found", "warning")
                return
            
            # Display files
            print(f"\n\033[1;36m{'ID':<40} {'Type':<15} {'Name':<40}\033[0m")
            print(f"\033[90m{'-'*40} {'-'*15} {'-'*40}\033[0m")
            
            for file in files:
                file_id = file.get('id', 'Unknown')
                file_type = file.get('mimeType', 'Unknown').split('/')[-1]
                
                # Format type nicely
                if 'folder' in file_type:
                    file_type = 'Folder'
                elif 'document' in file_type:
                    file_type = 'Document'
                elif 'spreadsheet' in file_type:
                    file_type = 'Spreadsheet'
                elif 'presentation' in file_type:
                    file_type = 'Presentation'
                
                file_name = file.get('name', 'Unnamed')
                
                # Truncate name if too long
                if len(file_name) > 40:
                    file_name = file_name[:37] + "..."
                
                # Format folders with a different color
                if file_type == 'Folder':
                    print(f"{file_id:<40} \033[1;33m{file_type:<15}\033[0m \033[1m{file_name}\033[0m")
                else:
                    print(f"{file_id:<40} \033[1;36m{file_type:<15}\033[0m {file_name}")
            
            print()
        
        except Exception as e:
            error_msg = str(e)
            log_exception(e, "Error listing files")
            self.cli.print_message(f"Error listing files: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh drive\033[0m - to refresh your Drive token")
                print("  2. \033[1mrefresh drive --reset\033[0m - to completely re-authenticate with Google")
                print("  3. \033[1msetup\033[0m - if the above options don't work")
    
    def handle_drive_download(self, arg):
        """Download a file from Google Drive: drive_download <file_id> [output_path]"""
        if not self._ensure_drive_authentication():
            return
        
        args = arg.split()
        if not args:
            self.cli.print_message("Please provide a file ID", "warning")
            return
        
        file_id = args[0]
        output_path = args[1] if len(args) > 1 else None
        
        try:
            self.cli.print_message(f"Downloading file {file_id}...", "info")
            path = self.cli.drive.download_file(file_id, output_path)
            
            if path:
                self.cli.print_message(f"File downloaded to {path}", "success")
            else:
                self.cli.print_message("Download failed", "error")
        
        except Exception as e:
            error_msg = str(e)
            log_exception(e, "Error downloading file")
            self.cli.print_message(f"Error downloading file: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh drive\033[0m - to refresh your Drive token")
                print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
    
    def handle_drive_create(self, arg):
        """Create a document on Google Drive: drive_create <name> <content>"""
        if not self._ensure_drive_authentication():
            return
            
        if not arg:
            # Interactive mode
            print("\n\033[1;36mCreate Google Doc\033[0m")
            name = input("\033[1mDocument name:\033[0m ").strip()
            
            if not name:
                self.cli.print_message("Document name is required", "warning")
                return
            
            print("\033[1mContent:\033[0m (Type your content. Enter '.' on a new line to finish)")
            lines = []
            while True:
                line = input()
                if line.strip() == '.':
                    break
                lines.append(line)
            
            content = '\n'.join(lines)
            
            if not content:
                self.cli.print_message("Document content is required", "warning")
                return
        else:
            # Command line mode
            parts = arg.split(' ', 1)
            if len(parts) < 2:
                self.cli.print_message("Please provide both name and content", "warning")
                return
            
            name, content = parts
        
        try:
            self.cli.print_message("Creating document...", "info")
            doc = self.cli.drive.create_document(name, content)
            
            if doc:
                self.cli.print_message(f"Document '{name}' created!", "success")
                print(f"  Link: {doc.get('webViewLink', 'Not available')}")
            else:
                self.cli.print_message("Document creation failed", "error")
        
        except Exception as e:
            error_msg = str(e)
            log_exception(e, "Error creating document")
            self.cli.print_message(f"Error creating document: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh drive\033[0m - to refresh your Drive token")
                print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
    
    def handle_drive_shared(self, arg):
        """List files shared with you: drive_shared [max_results]"""
        if not self._ensure_drive_authentication():
            return
        
        max_results = 10
        if arg:
            try:
                max_results = int(arg)
            except ValueError:
                self.cli.print_message(f"Invalid max results value: {arg}", "error")
                return
        
        try:
            self.cli.print_message("Fetching shared files...", "info")
            files = self.cli.drive.list_shared_files(max_results=max_results)
            
            if not files:
                self.cli.print_message("No shared files found", "warning")
                return
            
            # Display files
            print(f"\n\033[1;36m{'ID':<40} {'Type':<15} {'Name':<30} {'Shared By':<20}\033[0m")
            print(f"\033[90m{'-'*40} {'-'*15} {'-'*30} {'-'*20}\033[0m")
            
            for file in files:
                file_id = file.get('id', 'Unknown')
                file_type = file.get('mimeType', 'Unknown').split('/')[-1]
                file_name = file.get('name', 'Unnamed')
                shared_by = file.get('shared_by', 'Unknown')
                
                # Format type nicely
                if 'folder' in file_type:
                    file_type = 'Folder'
                elif 'document' in file_type:
                    file_type = 'Document'
                elif 'spreadsheet' in file_type:
                    file_type = 'Spreadsheet'
                elif 'presentation' in file_type:
                    file_type = 'Presentation'
                
                # Truncate name if too long
                if len(file_name) > 30:
                    file_name = file_name[:27] + "..."
                
                # Format folders with a different color
                if file_type == 'Folder':
                    print(f"{file_id:<40} \033[1;33m{file_type:<15}\033[0m \033[1m{file_name:<30}\033[0m {shared_by:<20}")
                else:
                    print(f"{file_id:<40} \033[1;36m{file_type:<15}\033[0m {file_name:<30} {shared_by:<20}")
            
            print()
        
        except Exception as e:
            error_msg = str(e)
            log_exception(e, "Error listing shared files")
            self.cli.print_message(f"Error listing shared files: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh drive\033[0m - to refresh your Drive token")
                print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
    
    def handle_drive_share(self, arg):
        """Share a file with another user: drive_share <file_id> <email> [role]"""
        if not self._ensure_drive_authentication():
            return
        
        args = arg.split()
        if len(args) < 2:
            self.cli.print_message("Please provide file ID and email", "warning")
            print("Usage: drive_share <file_id> <email> [role]")
            print("Roles: reader (default), writer, commenter")
            return
        
        file_id = args[0]
        email = args[1]
        role = args[2] if len(args) > 2 else 'reader'
        
        # Validate role
        valid_roles = ['reader', 'writer', 'commenter']
        if role not in valid_roles:
            self.cli.print_message(f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}", "error")
            return
        
        try:
            self.cli.print_message(f"Sharing file {file_id} with {email}...", "info")
            result = self.cli.drive.share_file(file_id, email, role)
            
            if result:
                self.cli.print_message(f"File shared with {email} ({role})", "success")
            else:
                self.cli.print_message("Failed to share file", "error")
        
        except Exception as e:
            error_msg = str(e)
            log_exception(e, "Error sharing file")
            self.cli.print_message(f"Error sharing file: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh drive\033[0m - to refresh your Drive token")
                print("  2. \033[1msetup\033[0m - if refreshing doesn't work")