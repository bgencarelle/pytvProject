#!/bin/bash
#
# runPytv.sh
# Creates venv, installs dependencies, and runs PyTV.
#
echo "Starting PyTV..."
VENV_NAME=".venv"

# Check if venv exists, create if not
if [ ! -d "$VENV_NAME" ]; then
  echo "Creating virtual environment at $VENV_NAME..."
  python3 -m venv $VENV_NAME
  if [ $? -ne 0 ]; then
    echo "Failed to create venv. Make sure python3-venv is installed."
    exit 1
  fi
fi

# Activate venv
source $VENV_NAME/bin/activate

# Install/update requirements
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
  echo "Dependency installation failed. See errors above."
  echo "Make sure you have installed the *system* dependencies (GStreamer, SDL2) first."
  echo "See README.md for installation instructions."
  exit 1
fi

# Run the main application
echo "Launching main.py..."
python main.py

