#!/bin/bash

# 1. Go to the project folder quietly
cd /home/miniproject/Downloads/mindsql


# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Run the python script with whatever arguments you typed
# "$@" means "pass all arguments like 'shell' or 'connect' to Python"
python3 main.py "$@"
