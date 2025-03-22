#!/usr/bin/env python3
"""
Enhanced Anthropic API client with support for thinking mode, tool use, and extended output.
"""

import requests
from typing import Dict, List, Union, Optional, Any

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
        
        try:
            # Make API request
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=data,
                stream=stream,
                timeout=60  # Adding timeout for better error handling
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
                
        except requests.exceptions.Timeout:
            raise Exception("Request to Anthropic API timed out. Please try again later.")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection error. Please check your internet connection.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request error: {str(e)}")
        except Exception as e:
            raise Exception(f"Error communicating with Anthropic API: {str(e)}")
    
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