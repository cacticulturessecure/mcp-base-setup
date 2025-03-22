#!/usr/bin/env python3
"""
Extraction-related command handlers for SimpleAnthropicCLI
"""

import os
import time
import logging
from typing import Dict, List, Any, Optional, Union

from utils.logging_utils import log_exception

class ExtractionCommands:
    """Extraction commands for the SimpleAnthropicCLI."""
    
    def __init__(self, cli_instance):
        """Initialize with a reference to the CLI instance.
        
        Args:
            cli_instance: The AnthropicCLI instance
        """
        self.cli = cli_instance
    
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
    
    def handle_extract(self, arg):
        """Extract and edit message segments: extract <message_index> [<export_action>]
        
        export_action can be:
        - email: Create a draft email with the extracted content
        - document: Create a Google Doc with the extracted content
        - save: Save to a text file
        - clipboard: Copy to clipboard (if available)
        """
        if not self.cli.current_conversation:
            self.cli.print_message("No conversation to extract from", "warning")
            return
            
        args = arg.split(None, 1)
        if not args:
            self.cli.print_message("Please provide a message index", "warning")
            return
            
        # Get message index
        try:
            msg_idx = int(args[0]) - 1  # Convert to 0-based index
            if msg_idx < 0 or msg_idx >= len(self.cli.current_conversation):
                self.cli.print_message(f"Invalid message index. Valid range: 1-{len(self.cli.current_conversation)}", "error")
                return
        except ValueError:
            self.cli.print_message("Message index must be a number", "error")
            return
            
        # Get the message
        message = self.cli.current_conversation[msg_idx]
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
            self.cli.print_message("Extraction cancelled", "warning")
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
                self.cli.print_message("Invalid input. Using all segments.", "error")
                selected_segments = segments
                
        if not selected_segments:
            self.cli.print_message("No valid segments selected", "warning")
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
                self.cli.print_message("Text updated", "success")
            else:
                self.cli.print_message("No changes made", "warning")
            
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
            if not self.cli.gmail:
                self.cli.print_message("Gmail service not initialized. Run setup first.", "error")
                return
                
            # Get email details
            print("\n\033[1;36mEmail Draft Creation\033[0m")
            to = input("\033[1mTo:\033[0m ").strip()
            if not to:
                self.cli.print_message("Email recipient is required", "warning")
                return
                
            subject = input("\033[1mSubject:\033[0m ").strip()
            if not subject:
                self.cli.print_message("Email subject is required", "warning")
                return
                
            # Add CC/BCC if needed
            cc = input("\033[1mCC:\033[0m ").strip()
            bcc = input("\033[1mBCC:\033[0m ").strip()
            
            try:
                self.cli.print_message("Creating email draft...", "info")
                draft_id = self.cli.gmail.create_draft(to, subject, combined_text, cc, bcc)
                self.cli.print_message(f"Draft created! ID: {draft_id}", "success")
            except Exception as e:
                log_exception(e, "Error creating draft")
                self.cli.print_message(f"Error creating draft: {e}", "error")
                
        elif export_action == 'document':
            if not self.cli.drive:
                self.cli.print_message("Drive service not initialized. Run setup first.", "error")
                return
                
            # Get document details
            print("\n\033[1;36mGoogle Doc Creation\033[0m")
            doc_name = input("\033[1mDocument name:\033[0m ").strip()
            if not doc_name:
                doc_name = f"Extracted content {time.strftime('%Y-%m-%d %H:%M')}"
                
            try:
                self.cli.print_message("Creating Google Doc...", "info")
                doc = self.cli.drive.create_document(doc_name, combined_text)
                self.cli.print_message(f"Document created: {doc['name']}", "success")
                print(f"  Link: {doc.get('webViewLink', 'Not available')}")
            except Exception as e:
                log_exception(e, "Error creating document")
                self.cli.print_message(f"Error creating document: {e}", "error")
                
        elif export_action == 'save':
            # Get file details
            print("\n\033[1;36mSave to Text File\033[0m")
            file_name = input("\033[1mFile name (without extension):\033[0m ").strip()
            if not file_name:
                file_name = f"extracted_{int(time.time())}"
                
            file_name = f"{file_name}.txt"
            
            try:
                # Create export directory if it doesn't exist
                config_dir = os.path.expanduser("~/.simple_anthropic_cli")
                export_dir = os.path.join(config_dir, "exports")
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)
                    
                # Save to file
                file_path = os.path.join(export_dir, file_name)
                with open(file_path, 'w') as f:
                    f.write(combined_text)
                    
                self.cli.print_message(f"Text saved to {file_path}", "success")
            except Exception as e:
                log_exception(e, "Error saving file")
                self.cli.print_message(f"Error saving file: {e}", "error")
                
        else:  # display only
            print("\n\033[1;36mExtracted Content:\033[0m")
            print("\033[90m" + "=" * 60 + "\033[0m")
            print(combined_text)
            print("\033[90m" + "=" * 60 + "\033[0m")