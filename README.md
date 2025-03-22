# SimpleAnthropicCLI v4

A command-line interface for Anthropic's Claude AI models with Gmail, Google Drive integration and function calling/tool use capabilities.

## Features

- Chat with Claude models with conversation history management
- Extended thinking mode for more thoughtful responses
- Tool use capabilities (function calling) for Claude to use external services
- Gmail integration for searching, reading, and sending emails
- Google Drive integration for file management
- Web search capabilities using Brave Search
- Configuration management with user profiles
- Session management to save and load conversations
- Support for all Claude 3 models

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd simple-anthropic-cli
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your API keys:
   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key
   BRAVE_API_KEY=your_brave_search_api_key
   ```

4. Set up Google OAuth credentials for Gmail and Drive (see [Authentication](#authentication) below)

## Usage

Start the CLI:

```bash
python simple_anthropic_cli.py
```

### Command-line Arguments

```
usage: simple_anthropic_cli.py [-h] [--api-key API_KEY] [--model MODEL] [--setup]
                           [--gmail-creds GMAIL_CREDS] [--gmail-token GMAIL_TOKEN]
                           [--drive-creds DRIVE_CREDS] [--drive-token DRIVE_TOKEN]
                           [--brave-api-key BRAVE_API_KEY] [--no-thinking] [--no-tools]
                           [--extended-output] [--debug]

options:
  -h, --help            show this help message and exit
  --api-key API_KEY     Anthropic API key
  --model MODEL         Model to use
  --setup               Run setup wizard on startup
  --gmail-creds GMAIL_CREDS
                        Path to Gmail credentials.json
  --gmail-token GMAIL_TOKEN
                        Path to Gmail token.json
  --drive-creds DRIVE_CREDS
                        Path to Drive credentials.json
  --drive-token DRIVE_TOKEN
                        Path to Drive token.json
  --brave-api-key BRAVE_API_KEY
                        Brave Search API key
  --no-thinking         Disable extended thinking
  --no-tools            Disable tool use
  --extended-output     Enable extended output (128k tokens)
  --debug               Enable debug logging
```

## CLI Commands

Here are some of the available commands in the CLI:

- `chat <message>` - Chat with Claude
- `thinking [on|off|show|hide|budget <number>]` - Configure extended thinking
- `tools [on|off|list]` - Configure tool use
- `model [model_name]` - Set or view the current model
- `extended_output [on|off]` - Configure extended output (128k tokens)
- `clear` - Clear the current conversation
- `save_conversation [filename]` - Save the current conversation
- `load_conversation <filename>` - Load a saved conversation
- `config [setting] [value]` - View or change configuration
- `status` - Check service status
- `exit` or `quit` - Exit the CLI

Type `help` to see all available commands, or `help <command>` for detailed help on a specific command.

### Email Commands

```
email_list [query]                 # List emails, with optional search query
email_read <email_id>              # Read a specific email
email_compose                      # Compose an email interactively
email_send <to> <subject> <body>   # Send an email directly
email_drafts [view|send] [id]      # Manage email drafts
```

### Drive Commands

```
drive_list [query]                 # List Google Drive files
drive_download <file_id> [path]    # Download a file
drive_create <type> <name>         # Create a document, spreadsheet, or folder
drive_shared                       # List files shared with you
drive_share <id> <email> [role]    # Share a file with someone
```

### Search Commands

```
web_search <query> [count]         # Search the web with Brave Search
local_search <query> [count]       # Search for local businesses
```

## Authentication

The CLI uses OAuth for Gmail and Google Drive. To set this up:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Gmail API and Drive API
4. Create OAuth 2.0 credentials (Desktop application type)
5. Download the credentials JSON file
6. Use the CLI's setup wizard to configure the paths to your credentials:
   ```
   simple-anthropic> setup
   ```
7. On first run, it will open a browser window for you to authorize access to your Google account

## Project Structure

```
simple-anthropic-cli/
├── simple_anthropic_cli.py   # Main CLI entry point
├── utils/                    # Utility modules
│   ├── anthropic_client_v2.py  # Enhanced Claude client
│   ├── config_utils.py       # Configuration management
│   ├── history_utils.py      # History management
│   ├── logging_utils.py      # Logging functionality
│   ├── security_utils.py     # Security utilities
│   └── cache.py              # Caching utilities
├── commands/                 # Command handlers
│   ├── chat_commands.py      # Chat-related commands
│   └── ...                   # Other command modules
├── gmail_service.py          # Gmail integration
├── drive_service.py          # Google Drive integration
├── brave_service.py          # Brave Search integration
└── README.md                 # Documentation
```

## Configuration

Configuration is stored in `~/.simple_anthropic_cli/config.json`. Key settings include:

- `model`: The Claude model to use
- `temperature`: Temperature setting (0.0 to 1.0)
- `max_tokens`: Maximum tokens in the response
- `thinking_enabled`: Whether to enable Claude's extended thinking
- `thinking_budget`: Token budget for extended thinking
- `use_tools`: Whether to enable tool use (function calling)
- `extended_output`: Whether to enable extended output (128k tokens)
- `gmail_credentials_path`: Path to Gmail credentials JSON
- `gmail_token_path`: Path to Gmail token JSON
- `drive_credentials_path`: Path to Drive credentials JSON
- `drive_token_path`: Path to Drive token JSON
- `brave_api_key`: Brave Search API key

## Requirements

- Python 3.7+
- Anthropic API key
- Google account (for Gmail and Drive integration)
- Brave Search API key (optional)

## License

[MIT License](LICENSE)