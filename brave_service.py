#!/usr/bin/env python3
"""
Brave Search service for the SimpleAnthropicCLI.
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any

class BraveSearchService:
    """Brave Search service for interacting with Brave Search API."""
    
    # Brave Search API endpoints
    WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
    LOCAL_SEARCH_URL = "https://api.search.brave.com/res/v1/news/search"
    
    def __init__(self, api_key: str = None):
        """Initialize the Brave Search service.
        
        Args:
            api_key: Brave Search API key. If None, will try to get from environment.
        """
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY")
        
        if not self.api_key:
            raise ValueError("Brave Search API key not provided and BRAVE_API_KEY environment variable not set.")
    
    def web_search(self, query: str, count: int = 10, offset: int = 0) -> Dict:
        """Perform a web search using Brave Search API.
        
        Args:
            query: Search query
            count: Number of results to return (max 20)
            offset: Offset for pagination (max 9)
            
        Returns:
            Dictionary containing search results
        """
        # Ensure params are within limits
        count = min(max(1, count), 20)
        offset = min(max(0, offset), 9)
        
        # Set up headers and params
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": count,
            "offset": offset
        }
        
        # Make the request
        response = requests.get(
            self.WEB_SEARCH_URL,
            headers=headers,
            params=params
        )
        
        # Check for errors
        response.raise_for_status()
        
        # Parse and return results
        return response.json()
    
    def local_search(self, query: str, count: int = 10) -> Dict:
        """Perform a local search using Brave Search API.
        Falls back to web search if no local results found.
        
        Args:
            query: Search query
            count: Number of results to return (max 20)
            
        Returns:
            Dictionary containing search results
        """
        # Add 'near me' if not already in query to improve local results
        if 'near me' not in query.lower():
            local_query = f"{query} near me"
        else:
            local_query = query
        
        # First try web search with local query
        result = self.web_search(local_query, count)
        
        # Check if we got meaningful results
        if not result.get('web', {}).get('results', []):
            # Fall back to regular web search
            result = self.web_search(query, count)
            result['_fallback'] = True
        else:
            result['_fallback'] = False
        
        return result
    
    def format_web_results(self, results: Dict) -> str:
        """Format web search results for display.
        
        Args:
            results: Search results from web_search
            
        Returns:
            Formatted string with search results
        """
        if not results or not results.get('web', {}).get('results'):
            return "No results found."
        
        web_results = results['web']['results']
        query = results.get('query', {}).get('q', '')
        total_count = results.get('web', {}).get('totalCount', 0)
        
        output = [f"\033[1;36mSearch results for: '{query}'\033[0m"]
        output.append(f"Found approximately {total_count} results\n")
        
        for i, result in enumerate(web_results, 1):
            title = result.get('title', 'No Title')
            url = result.get('url', '')
            description = result.get('description', 'No description available')
            
            output.append(f"\033[1;33m{i}. {title}\033[0m")
            output.append(f"\033[90m{url}\033[0m")
            output.append(f"{description}\n")
        
        return "\n".join(output)
    
    def format_local_results(self, results: Dict) -> str:
        """Format local search results for display.
        
        Args:
            results: Search results from local_search
            
        Returns:
            Formatted string with search results
        """
        if not results or not results.get('web', {}).get('results'):
            return "No results found."
        
        web_results = results['web']['results']
        query = results.get('query', {}).get('q', '')
        fallback = results.get('_fallback', False)
        
        output = [f"\033[1;36mLocal search results for: '{query}'\033[0m"]
        
        if fallback:
            output.append("\033[33m! No specific local results found. Showing general web results instead.\033[0m\n")
        
        for i, result in enumerate(web_results, 1):
            title = result.get('title', 'No Title')
            url = result.get('url', '')
            description = result.get('description', 'No description available')
            
            output.append(f"\033[1;33m{i}. {title}\033[0m")
            output.append(f"\033[90m{url}\033[0m")
            output.append(f"{description}\n")
        
        return "\n".join(output)