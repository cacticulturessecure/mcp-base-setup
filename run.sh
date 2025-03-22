#!/bin/bash

# SimpleAnthropicCLI Runner
clear
echo "======================================"
echo " SimpleAnthropicCLI v4 Runner"
echo "======================================"
echo ""

# Check Python installation
if command -v python3 &>/dev/null; then
    echo "✓ Python 3 is installed"
else
    echo "✘ Python 3 is required but not installed"
    exit 1
fi

# Check for uv-ollama-env and use it if available
if [ -d "$HOME/uv-ollama-env" ]; then
    echo "Using existing uv-ollama-env environment"
    source "$HOME/uv-ollama-env/bin/activate"
else
    # Set up virtual environment if needed
    VENV_DIR="$HOME/anthropic-cli-env"
    if [ ! -d "$VENV_DIR" ]; then
        echo "Setting up virtual environment..."
        python3 -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip
        pip install -r requirements.txt
        echo "✓ Virtual environment created at $VENV_DIR"
    else
        source "$VENV_DIR/bin/activate"
    fi
fi

# Check for credentials directory
CREDS_DIR="$(pwd)/credentials"
if [ ! -d "$CREDS_DIR" ]; then
    echo "Creating credentials directory..."
    mkdir -p "$CREDS_DIR"
    echo "✓ Credentials directory created at $CREDS_DIR"
    echo "  You will need to add your Google API credentials to this directory"
    echo "  or configure them through the CLI"
fi

# The Python script will automatically locate the .env file in various locations
echo "✓ Using environment variables from existing .env file"

# Run the CLI
echo "Starting SimpleAnthropicCLI..."
echo ""
python3 simple_anthropic_cli.py "$@"