#!/usr/bin/env python3
"""
Gmail service for the SimpleAnthropicCLI.
"""

import os
import json
import base64
from typing import Dict, List, Optional, Any
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

class GmailService:
    """Gmail service for interacting with Gmail API."""
    
    # Gmail API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.metadata',
    ]
    
    def __init__(self, credentials_path: str, token_path: str, force_refresh: bool = False, reset_auth: bool = False):
        """Initialize the Gmail service.
        
        Args:
            credentials_path: Path to the credentials.json file
            token_path: Path to the token.json file
            force_refresh: If True, force token refresh even if token is valid
            reset_auth: If True, remove existing token and force complete re-authentication
        """
        self.credentials_path = os.path.abspath(credentials_path)
        self.token_path = os.path.abspath(token_path)
        self.force_refresh = force_refresh
        self.reset_auth = reset_auth
        
        # If reset_auth is True, delete the token file to force re-authentication
        if self.reset_auth and os.path.exists(self.token_path):
            try:
                os.remove(self.token_path)
                print(f"\033[33m! Removed existing token at {self.token_path}\033[0m")
                print(f"\033[33m! You will need to re-authenticate with Google\033[0m")
            except Exception as e:
                print(f"\033[31m✘\033[0m Error removing token file: {e}")
        
        self.service = self._get_gmail_service()
    
    def _get_gmail_service(self):
        """Get an authorized Gmail API service instance."""
        creds = None
        
        # Load the token file if it exists
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'r') as token:
                    creds = Credentials.from_authorized_user_info(
                        json.load(token), self.SCOPES)
                print(f"\033[32m✓\033[0m Successfully loaded token from {self.token_path}")
            except Exception as e:
                print(f"\033[33m! Error loading token: {e}\033[0m")
        
        # Force refresh if requested, even if token is valid
        if self.force_refresh and creds and creds.refresh_token:
            try:
                creds.refresh(Request())
                print(f"\033[32m✓\033[0m Successfully force-refreshed token")
                
                # Save the refreshed credentials
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
                print(f"\033[32m✓\033[0m Refreshed token saved to {self.token_path}")
            except Exception as e:
                print(f"\033[33m! Error force-refreshing token: {e}\033[0m")
                creds = None
            
        # If no valid credentials, authenticate
        elif not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print(f"\033[32m✓\033[0m Successfully refreshed token")
                    
                    # Save the refreshed credentials
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                    print(f"\033[32m✓\033[0m Refreshed token saved to {self.token_path}")
                except Exception as e:
                    print(f"\033[33m! Error refreshing token: {e}\033[0m")
                    creds = None
            
            if not creds:
                try:
                    # Load credentials from file
                    with open(self.credentials_path, 'r') as f:
                        cred_data = json.load(f)
                    
                    # Handle different credential file formats
                    if 'installed' in cred_data:
                        # Format from Google Cloud downloaded JSON
                        client_id = cred_data['installed']['client_id']
                        client_secret = cred_data['installed']['client_secret']
                        redirect_uri = cred_data['installed']['redirect_uris'][0]
                    elif 'client_id' in cred_data and 'client_secret' in cred_data:
                        # Simple format
                        client_id = cred_data['client_id']
                        client_secret = cred_data['client_secret']
                        redirect_uri = cred_data.get('redirect_uris', ['http://localhost:3001'])[0]
                    else:
                        raise ValueError("Unrecognized credentials format")
                    
                    print(f"\033[32m✓\033[0m Successfully parsed credentials from {self.credentials_path}")
                    
                    # Create OAuth2 flow manually
                    from google_auth_oauthlib.flow import Flow
                    flow = Flow.from_client_config(
                        {"installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "redirect_uris": [redirect_uri],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                        }},
                        scopes=self.SCOPES
                    )
                    flow.redirect_uri = 'http://localhost:3001'
                    
                    # Run the flow - include access_type=offline to get a refresh token
                    auth_url, _ = flow.authorization_url(
                        prompt='consent',
                        access_type='offline',
                        include_granted_scopes='true'
                    )
                    print(f"\033[1;36mPlease visit this URL to authenticate:\033[0m\n{auth_url}")
                    
                    # Manual authentication process
                    print("\n\033[1;33mAfter authorizing in your browser, you'll be redirected to a URL\033[0m")
                    print("\033[1;33mCopy the entire URL from your browser after authorization\033[0m")
                    auth_response = input("\nPaste the redirect URL here: ")
                    
                    # Extract code from URL
                    import urllib.parse
                    query = urllib.parse.urlparse(auth_response).query
                    params = dict(urllib.parse.parse_qsl(query))
                    code = params.get('code')
                    
                    if not code:
                        raise ValueError("Authorization code not found in the URL")
                    
                    # Exchange code for credentials
                    flow.fetch_token(code=code)
                    creds = flow.credentials
                    
                    # Ensure token directory exists
                    token_dir = os.path.dirname(self.token_path)
                    if not os.path.exists(token_dir):
                        os.makedirs(token_dir, exist_ok=True)
                        print(f"Created token directory: {token_dir}")
                        
                    # Save the credentials for next run
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                    
                    print(f"\033[32m✓\033[0m Authentication successful! Token saved to {self.token_path}")
                    
                except Exception as e:
                    print(f"\033[31m✘\033[0m Error during authentication: {e}")
                    raise
        
        # Build the Gmail service
        return build('gmail', 'v1', credentials=creds)
    
    def list_emails(self, max_results: int = 10, query: Optional[str] = None) -> List[Dict]:
        """List emails from Gmail inbox.
        
        Args:
            max_results: Maximum number of emails to retrieve
            query: Optional Gmail search query
        
        Returns:
            List of email metadata
        """
        # Prepare the request parameters
        params = {
            'userId': 'me',
            'maxResults': max_results
        }
        
        if query:
            params['q'] = query
        
        # Get list of messages
        results = self.service.users().messages().list(**params).execute()
        messages = results.get('messages', [])
        
        if not messages:
            return []
        
        # Get details for each message
        emails = []
        for message in messages:
            msg = self.service.users().messages().get(
                userId='me', 
                id=message['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            emails.append({
                'id': message['id'],
                'subject': subject,
                'from': sender,
                'date': date
            })
            
            # Add snippet if available
            if 'snippet' in msg:
                emails[-1]['snippet'] = msg['snippet']
        
        return emails
        
    def list_sent_emails(self, max_results: int = 5) -> List[Dict]:
        """List recent sent emails.
        
        Args:
            max_results: Maximum number of emails to retrieve
        
        Returns:
            List of sent email metadata
        """
        # Use Gmail search query for sent mail
        return self.list_emails(max_results=max_results, query="in:sent")
        
    def list_drafts(self, max_results: int = 10) -> List[Dict]:
        """List email drafts.
        
        Args:
            max_results: Maximum number of drafts to retrieve
        
        Returns:
            List of draft metadata
        """
        # Get list of drafts
        results = self.service.users().drafts().list(
            userId='me',
            maxResults=max_results
        ).execute()
        
        drafts = results.get('drafts', [])
        
        if not drafts:
            return []
        
        # Get details for each draft
        draft_details = []
        for draft in drafts:
            result = self.service.users().drafts().get(
                userId='me',
                id=draft['id'],
                format='metadata'
            ).execute()
            
            # Extract message details
            message = result.get('message', {})
            headers = message.get('payload', {}).get('headers', [])
            
            to = next((h['value'] for h in headers if h['name'] == 'To'), 'No Recipient')
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            
            draft_details.append({
                'id': draft['id'],
                'to': to,
                'subject': subject
            })
        
        return draft_details
    
    def get_draft(self, draft_id: str) -> Dict:
        """Get a specific draft.
        
        Args:
            draft_id: The ID of the draft to retrieve
        
        Returns:
            Draft data with headers and body
        """
        # Get draft
        result = self.service.users().drafts().get(
            userId='me',
            id=draft_id,
            format='full'
        ).execute()
        
        # Extract message details
        message = result.get('message', {})
        headers = message.get('payload', {}).get('headers', [])
        
        to = next((h['value'] for h in headers if h['name'] == 'To'), 'No Recipient')
        cc = next((h['value'] for h in headers if h['name'] == 'Cc'), '')
        bcc = next((h['value'] for h in headers if h['name'] == 'Bcc'), '')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        
        # Extract body
        body = ''
        if 'parts' in message.get('payload', {}):
            # Multipart message
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part.get('body', {}):
                    body = base64.urlsafe_b64decode(
                        part['body']['data']).decode('utf-8')
                    break
        elif 'data' in message.get('payload', {}).get('body', {}):
            # Simple message
            body = base64.urlsafe_b64decode(
                message['payload']['body']['data']).decode('utf-8')
        
        return {
            'id': draft_id,
            'to': to,
            'cc': cc,
            'bcc': bcc,
            'subject': subject,
            'body': body
        }
    
    def get_email(self, email_id: str) -> Dict:
        """Get a specific email by ID.
        
        Args:
            email_id: The ID of the email to retrieve
        
        Returns:
            Email data with headers and body
        """
        # Get full message
        msg = self.service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()
        
        # Extract headers
        headers = msg['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        to = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # Extract body
        body = ''
        if 'parts' in msg['payload']:
            # Multipart message
            for part in msg['payload']['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(
                        part['body']['data']).decode('utf-8')
                    break
        elif 'data' in msg['payload']['body']:
            # Simple message
            body = base64.urlsafe_b64decode(
                msg['payload']['body']['data']).decode('utf-8')
        
        return {
            'id': email_id,
            'subject': subject,
            'from': sender,
            'to': to,
            'date': date,
            'body': body,
            'snippet': msg['snippet']
        }
    
    def create_draft(self, to: str, subject: str, body: str, 
                    cc: Optional[str] = None, bcc: Optional[str] = None) -> str:
        """Create a draft email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional CC recipients
            bcc: Optional BCC recipients
        
        Returns:
            Draft ID
        """
        # Create message
        message = self._create_message(to, subject, body, cc, bcc)
        
        # Create draft
        draft = self.service.users().drafts().create(
            userId='me',
            body={'message': {'raw': message}}
        ).execute()
        
        return draft['id']
    
    def send_email(self, to: str, subject: str, body: str,
                  cc: Optional[str] = None, bcc: Optional[str] = None) -> None:
        """Send an email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional CC recipients
            bcc: Optional BCC recipients
        """
        # Create message
        message = self._create_message(to, subject, body, cc, bcc)
        
        # Send message
        self.service.users().messages().send(
            userId='me',
            body={'raw': message}
        ).execute()
    
    def send_draft(self, draft_id: str) -> None:
        """Send an existing draft email.
        
        Args:
            draft_id: The ID of the draft to send
        """
        self.service.users().drafts().send(
            userId='me',
            body={'id': draft_id}
        ).execute()
    
    def _create_message(self, to: str, subject: str, body: str,
                       cc: Optional[str] = None, bcc: Optional[str] = None) -> str:
        """Create a message for the Gmail API.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional CC recipients
            bcc: Optional BCC recipients
        
        Returns:
            URL-safe base64 encoded email
        """
        # Create MIMEText message
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        
        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc
        
        # Encode to base64URL
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return raw