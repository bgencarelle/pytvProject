#!/bin/bash
#
# PyTV Bootstrap Script
#
# This script will set up the entire PyTV environment from scratch:
# 1. Clones or updates the Git repository.
# 2. Installs all system dependencies for macOS (via Homebrew) or Linux (via APT).
# 3. Creates the 57 channel directories (movies/chan_01 to movies/chan_57).
# 4. Creates a Python virtual environment (.venv) and installs Python packages.
#

# Exit immediately if any command fails
set -e

# --- 1. Get Project Files from Git ---

REPO_URL="https://github.com/bgencarelle/pytvProject.git"
PROJECT_DIR="pytvProject"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "ERROR: Git is not installed. Please install Git to continue."
    exit 1
fi

if [ -d "$PROJECT_DIR" ]; then
    echo "Directory '$PROJECT_DIR' already exists. Pulling latest changes..."
    cd "$PROJECT_DIR"
    git pull
else
    echo "Cloning repository from $REPO_URL..."
    git clone "$REPO_URL"
    cd "$PROJECT_DIR"
fi

echo "Successfully updated project."


# --- 2. Install System Dependencies ---

echo "Detecting OS and installing system dependencies..."

# Check for python3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed. Please install Python 3 to continue."
    exit 1
fi

case "$(uname -s)" in
   Darwin)
     echo "Detected macOS."
     if ! command -v brew &> /dev/null; then
        echo "ERROR: Homebrew (brew) is not installed."
        echo "Please install Homebrew first: https://brew.sh/"
        exit 1
     fi

     echo "Updating Homebrew..."
     brew update

     echo "Installing GStreamer dependencies..."
     brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad pygobject3

     echo "Installing Pygame (SDL) dependencies..."
     brew install sdl2 sdl2_image sdl2_mixer sdl2_ttf
     ;;

   Linux)
     echo "Detected Linux."
     if ! command -v apt-get &> /dev/null; then
        echo "ERROR: 'apt-get' not found. This script supports Debian-based Linux (e.g., Ubuntu, Raspberry Pi OS)."
        echo "Please install the dependencies manually."
        exit 1
     fi

     echo "Updating APT package list..."
     sudo apt-get update

     echo "Installing GStreamer dependencies..."
     sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad

     echo "Installing Pygame (SDL) dependencies..."
     sudo apt-get install -y libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0

     echo "Installing Python venv and pip..."
     sudo apt-get install -y python3-venv python3-pip
     ;;

   *)
     echo "ERROR: Unsupported operating system: $(uname -s)."
     echo "Please install the GStreamer and SDL2 dependencies manually."
     exit 1
     ;;
esac

echo "System dependencies installed."


# --- 3. Create Channel Directories (01-57) ---

echo "Creating 57 channel directories (movies/chan_01 to movies/chan_57)..."
mkdir -p movies

for i in $(seq 1 57); do
    # Format the number with a leading zero (e.g., 01, 08, 57)
    CHAN_DIR=$(printf "chan_%02d" $i)

    # Create the directory
    mkdir -p "movies/$CHAN_DIR"

    # Add a .gitkeep file so the empty directory can be tracked by Git
    touch "movies/$CHAN_DIR/.gitkeep"
done

echo "Channel directories created."


# --- 4. Create Python Environment & Install Packages ---

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment at '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment '$VENV_DIR' already exists."
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

echo "Making runPytv.sh executable..."
if [ -f "runPytv.sh" ]; then
    chmod +x runPytv.sh
else
    echo "Warning: runPytv.sh not found. Skipping chmod."
fi

echo ""
echo "-------------------------------------"
echo " Bootstrap Complete!"
echo "-------------------------------------"
echo ""
echo "To run the application:"
echo "1. Add your video files to the 'movies/chan_NN' folders."
echo "2. Run:   bash runPytv.sh"
echo ""

