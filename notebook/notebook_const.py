import os
import sys

# Set project root
# Assuming this file is located in /workspace/notebook/
# This calculates the parent directory of the directory containing this file
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
