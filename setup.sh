#!/bin/bash

# Function to print messages
print_msg() {
    echo -e "\033[1;32m$1\033[0m"
}

print_error() {
    echo -e "\033[1;31m$1\033[0m"
}

print_warning() {
    echo -e "\033[1;33m$1\033[0m"
}

# Check for python3
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed."
    exit 1
fi

# Check for poetry
if ! command -v poetry &> /dev/null; then
    print_warning "Poetry not found. Attempting to install..."
    if command -v curl &> /dev/null; then
        curl -sSL https://install.python-poetry.org | python3 -
        export PATH="$HOME/.local/bin:$PATH"
    else
        print_error "curl not found. Please install Poetry manually."
        exit 1
    fi
fi

print_msg "Installing dependencies with Poetry..."
poetry install

if [ $? -ne 0 ]; then
    print_error "Failed to install dependencies."
    exit 1
fi

# Setup .env
if [ ! -f .env ]; then
    print_msg "Creating .env file..."
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        print_warning ".env.example not found. Creating empty .env"
        touch .env
    fi
else
    print_msg ".env file already exists."
fi

# Make scripts executable
chmod +x run.sh

# Instructions
print_msg "Setup completed successfully!"
print_msg "Note: If you just installed Poetry, you may need to restart your shell or add ~/.local/bin to your PATH to use 'poetry' command manually."
print_msg "IMPORTANT: Please edit the .env file to add your API keys:"
echo "  - API_KEY"
echo "  - API_SECRET"
print_msg "Or create .streamlit/secrets.toml for Streamlit-specific secrets."
print_msg "To run the application: ./run.sh"
