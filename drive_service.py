#!/usr/bin/env python3
"""
Google Drive service for the SimpleAnthropicCLI.
"""

import os
import json
import io
from typing import Dict, List, Optional, Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

class DriveService:
    """Google Drive service for interacting with Google Drive API."""
    
    # Drive API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/drive.metadata.readonly',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive.readonly',
    ]
    
    def __init__(self, credentials_path: str, token_path: str, force_refresh: bool = False, reset_auth: bool = False):
        """Initialize the Drive service.
        
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
        
        self.service = self._get_drive_service()
    
    def _get_drive_service(self):
        """Get an authorized Drive API service instance."""
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
        
        # Build the Drive service
        return build('drive', 'v3', credentials=creds)
    
    def list_files(self, max_results: int = 20, query: Optional[str] = None) -> List[Dict]:
        """List files from Google Drive.
        
        Args:
            max_results: Maximum number of files to retrieve
            query: Optional Google Drive search query
        
        Returns:
            List of file metadata
        """
        # Prepare the request parameters
        params = {
            'pageSize': max_results,
            'fields': 'files(id, name, mimeType, size, modifiedTime, createdTime)',
            'orderBy': 'modifiedTime desc'
        }
        
        if query:
            params['q'] = query
        
        # Get list of files
        results = self.service.files().list(**params).execute()
        files = results.get('files', [])
        
        return files
        
    def list_recent_files(self, max_results: int = 5) -> List[Dict]:
        """List recently modified files.
        
        Args:
            max_results: Maximum number of files to retrieve
        
        Returns:
            List of file metadata
        """
        return self.list_files(max_results=max_results)
        
    def list_recently_created_files(self, max_results: int = 5) -> List[Dict]:
        """List recently created files.
        
        Args:
            max_results: Maximum number of files to retrieve
        
        Returns:
            List of file metadata
        """
        # Prepare the request parameters
        params = {
            'pageSize': max_results,
            'fields': 'files(id, name, mimeType, size, modifiedTime, createdTime)',
            'orderBy': 'createdTime desc'
        }
        
        # Get list of files
        results = self.service.files().list(**params).execute()
        files = results.get('files', [])
        
        return files
    
    def get_file_metadata(self, file_id: str) -> Dict:
        """Get metadata for a specific file.
        
        Args:
            file_id: The ID of the file
        
        Returns:
            File metadata
        """
        return self.service.files().get(
            fileId=file_id, 
            fields='id, name, mimeType, size, modifiedTime, webViewLink'
        ).execute()
    
    def download_file(self, file_id: str, output_path: Optional[str] = None) -> str:
        """Download a file from Google Drive.
        
        Args:
            file_id: The ID of the file to download
            output_path: Optional path to save the file, if None use the file's name
        
        Returns:
            Path to the downloaded file
        """
        # Get file metadata
        file_metadata = self.get_file_metadata(file_id)
        
        # Determine output path
        if not output_path:
            output_path = file_metadata['name']
        
        # Download file
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")
        
        # Save file
        with open(output_path, 'wb') as f:
            f.write(fh.getvalue())
        
        return output_path
    
    def upload_file(self, file_path: str, folder_id: Optional[str] = None) -> Dict:
        """Upload a file to Google Drive.
        
        Args:
            file_path: Path to the file to upload
            folder_id: Optional folder ID to upload to
        
        Returns:
            Metadata of the uploaded file
        """
        file_name = os.path.basename(file_path)
        file_metadata = {'name': file_name}
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaFileUpload(file_path)
        
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, mimeType, size, webViewLink'
        ).execute()
        
        return file
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Dict:
        """Create a folder in Google Drive.
        
        Args:
            folder_name: Name of the folder to create
            parent_id: Optional parent folder ID
        
        Returns:
            Metadata of the created folder
        """
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        folder = self.service.files().create(
            body=file_metadata,
            fields='id, name, mimeType'
        ).execute()
        
        return folder
        
    def create_document(self, name: str, content: Optional[str] = None, parent_id: Optional[str] = None) -> Dict:
        """Create a Google Docs document.
        
        Args:
            name: Name of the document
            content: Optional initial content
            parent_id: Optional parent folder ID
        
        Returns:
            Metadata of the created document
        """
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        # Create empty document
        document = self.service.files().create(
            body=file_metadata,
            fields='id, name, mimeType, webViewLink'
        ).execute()
        
        # If content is provided, update the document
        if content:
            from googleapiclient.http import MediaInMemoryUpload
            
            # Convert HTML content
            html_content = f"<html><body>{content}</body></html>"
            media = MediaInMemoryUpload(
                html_content.encode('utf-8'),
                mimetype='text/html',
                resumable=True
            )
            
            # Update document content
            self.service.files().update(
                fileId=document['id'],
                media_body=media
            ).execute()
        
        return document
        
    def create_spreadsheet(self, name: str, parent_id: Optional[str] = None) -> Dict:
        """Create a Google Sheets spreadsheet.
        
        Args:
            name: Name of the spreadsheet
            parent_id: Optional parent folder ID
        
        Returns:
            Metadata of the created spreadsheet
        """
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        # Create empty spreadsheet
        spreadsheet = self.service.files().create(
            body=file_metadata,
            fields='id, name, mimeType, webViewLink'
        ).execute()
        
        return spreadsheet
    
    def share_file(self, file_id: str, email: str, role: str = 'reader') -> None:
        """Share a file with a specific user.
        
        Args:
            file_id: ID of the file to share
            email: Email address to share with
            role: Permission role (reader, writer, commenter, owner)
        """
        # Create permission
        permission = {
            'type': 'user',
            'role': role,
            'emailAddress': email
        }
        
        # Add permission to the file
        self.service.permissions().create(
            fileId=file_id,
            body=permission,
            sendNotificationEmail=True
        ).execute()
        
    def get_shared_files(self, max_results: int = 20) -> List[Dict]:
        """Get files shared with me.
        
        Args:
            max_results: Maximum number of files to retrieve
        
        Returns:
            List of shared file metadata
        """
        # Get list of shared files
        results = self.service.files().list(
            q="sharedWithMe=true",
            pageSize=max_results,
            fields='files(id, name, mimeType, size, owners, webViewLink)'
        ).execute()
        
        files = results.get('files', [])
        return files