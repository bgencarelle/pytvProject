#!/bin/bash
#
# runPytv.sh
# Activates venv and runs PyTV.
# Assumes bootstrap.sh has already been run.
#
echo "Starting PyTV..."
VENV_NAME=".venv"

# Check if venv exists
if [ ! -d "$VENV_NAME" ]; then
  echo "Virtual environment not found at $VENV_NAME."
  echo "Please run the bootstrap.sh script first."
  exit 1
fi

# Activate venv
source $VENV_NAME/bin/activate

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "main.py not found. Make sure you are in the pytvProject directory."
    exit 1
fi

# Run the main application
echo "Launching main.py..."
# The main.py script will automatically run the playlist_builder
python main.py