#!/usr/bin/env python3
"""
Email-related command handlers for SimpleAnthropicCLI
"""

import os
import time
import logging
from typing import Dict, List, Any, Optional, Union

from utils.logging_utils import log_exception

class EmailCommands:
    """Email commands for the SimpleAnthropicCLI."""
    
    def __init__(self, cli_instance):
        """Initialize with a reference to the CLI instance.
        
        Args:
            cli_instance: The AnthropicCLI instance
        """
        self.cli = cli_instance
    
    def _ensure_gmail_authentication(self):
        """Helper method to handle Gmail authentication issues
        
        Returns:
            bool: True if authentication is successful, False otherwise
        """
        if not self.cli.gmail:
            self.cli.print_message("Gmail service not initialized. Run setup first.", "error")
            return False
        
        return True
    
    def handle_email_list(self, arg):
        """List recent emails: email_list [query]"""
        if not self._ensure_gmail_authentication():
            return
        
        try:
            self.cli.print_message("Fetching emails...", "info")
            emails = self.cli.gmail.list_emails(query=arg if arg else None)
            if not emails:
                self.cli.print_message("No emails found.", "warning")
                return
            
            print(f"\n\033[1;36m{'ID':<12} {'From':<30} {'Subject':<50}\033[0m")
            print(f"\033[90m{'-'*12} {'-'*30} {'-'*50}\033[0m")
            
            for email in emails:
                print(f"{email['id'][:10]:<12} \033[1m{email['from'][:30]:<30}\033[0m {email['subject'][:50]}")
            print()
        
        except Exception as e:
            error_msg = str(e)
            log_exception(e, "Error listing emails")
            self.cli.print_message(f"Error listing emails: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                print("  2. \033[1mrefresh gmail --reset\033[0m - to completely re-authenticate with Google")
                print("  3. \033[1msetup\033[0m - if the above options don't work")
    
    def handle_email_read(self, arg):
        """Read an email by ID: email_read <email_id>"""
        if not self._ensure_gmail_authentication():
            return
        
        if not arg:
            self.cli.print_message("Please provide an email ID.", "warning")
            return
        
        try:
            self.cli.print_message("Fetching email content...", "info")
            email = self.cli.gmail.get_email(arg)
            
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
            log_exception(e, "Error reading email")
            self.cli.print_message(f"Error reading email: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                print("  2. \033[1mrefresh gmail --reset\033[0m - to completely re-authenticate with Google")
                print("  3. \033[1msetup\033[0m - if the above options don't work")
    
    def handle_email_compose(self, arg):
        """Compose an email interactively"""
        if not self._ensure_gmail_authentication():
            return
        
        print("\n\033[1;36mEmail Composition\033[0m")
        
        # Get recipient
        to = input("\033[1mTo:\033[0m ").strip()
        if not to:
            self.cli.print_message("Email recipient is required", "warning")
            return
        
        # Get CC (optional)
        cc = input("\033[1mCC:\033[0m ").strip()
        
        # Get BCC (optional)
        bcc = input("\033[1mBCC:\033[0m ").strip()
        
        # Get subject
        subject = input("\033[1mSubject:\033[0m ").strip()
        if not subject:
            self.cli.print_message("Email subject is required", "warning")
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
            self.cli.print_message("Email body is required", "warning")
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
                self.cli.print_message("Sending email...", "info")
                self.cli.gmail.send_email(to, subject, body, cc, bcc)
                self.cli.print_message(f"Email sent to {to}!", "success")
            except Exception as e:
                log_exception(e, "Error sending email")
                self.cli.print_message(f"Error sending email: {e}", "error")
        
        elif choice == '2':
            try:
                self.cli.print_message("Saving draft...", "info")
                draft_id = self.cli.gmail.create_draft(to, subject, body, cc, bcc)
                self.cli.print_message(f"Draft saved! ID: {draft_id}", "success")
            except Exception as e:
                error_msg = str(e)
                log_exception(e, "Error saving draft")
                self.cli.print_message(f"Error saving draft: {e}", "error")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
        
        else:
            self.cli.print_message("Email composition cancelled", "warning")
    
    def handle_email_send(self, arg):
        """Send an email: email_send <to> <subject> <body>"""
        if not self._ensure_gmail_authentication():
            return
        
        args = arg.split(' ', 2)
        if len(args) < 3:
            self.cli.print_message("Usage: email_send <to> <subject> <body>", "warning")
            return
        
        to, subject, body = args
        
        try:
            self.cli.print_message("Sending email...", "info")
            self.cli.gmail.send_email(to, subject, body)
            self.cli.print_message(f"Email sent to {to}!", "success")
        except Exception as e:
            error_msg = str(e)
            log_exception(e, "Error sending email")
            self.cli.print_message(f"Error sending email: {e}", "error")
            
            # Suggest refreshing if it looks like an authentication error
            if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
    
    def handle_email_drafts(self, arg):
        """List and manage email drafts"""
        if not self._ensure_gmail_authentication():
            return
            
        args = arg.split()
        if not args:
            # List drafts
            try:
                self.cli.print_message("Fetching drafts...", "info")
                drafts = self.cli.gmail.list_drafts()
                
                if not drafts:
                    self.cli.print_message("No drafts found", "warning")
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
                log_exception(e, "Error listing drafts")
                self.cli.print_message(f"Error listing drafts: {e}", "error")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
                
        elif args[0] == 'send' and len(args) > 1:
            # Send a specific draft
            draft_id = args[1]
            try:
                self.cli.print_message(f"Sending draft {draft_id}...", "info")
                self.cli.gmail.send_draft(draft_id)
                self.cli.print_message("Draft sent successfully!", "success")
            except Exception as e:
                error_msg = str(e)
                log_exception(e, "Error sending draft")
                self.cli.print_message(f"Error sending draft: {e}", "error")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
                
        elif args[0] == 'view' and len(args) > 1:
            # View a specific draft
            draft_id = args[1]
            try:
                self.cli.print_message(f"Fetching draft {draft_id}...", "info")
                draft = self.cli.gmail.get_draft(draft_id)
                
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
                log_exception(e, "Error viewing draft")
                self.cli.print_message(f"Error viewing draft: {e}", "error")
                
                # Suggest refreshing if it looks like an authentication error
                if "insufficient" in error_msg.lower() or "permission" in error_msg.lower():
                    print("\033[33m! This looks like an authentication issue. Try running:\033[0m")
                    print("  1. \033[1mrefresh gmail\033[0m - to refresh your Gmail token")
                    print("  2. \033[1msetup\033[0m - if refreshing doesn't work")
                
        else:
            self.cli.print_message("Usage: email_drafts [send <draft_id> | view <draft_id>]", "warning")