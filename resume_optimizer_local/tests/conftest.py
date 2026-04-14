"""
Add the resume_optimizer_local package directory to sys.path so tests can
import source modules without an install step.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
