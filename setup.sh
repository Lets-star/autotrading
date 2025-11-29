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

# Create venv
if [ ! -d "venv" ]; then
    print_msg "Creating virtual environment (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        print_error "Failed to create virtual environment."
        exit 1
    fi
else
    print_msg "Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate

print_msg "Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

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
print_msg "IMPORTANT: Please edit the .env file to add your API keys:"
echo "  - API_KEY"
echo "  - API_SECRET"
print_msg "To run the application: ./run.sh"
