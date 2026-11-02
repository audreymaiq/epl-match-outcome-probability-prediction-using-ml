"""Shared pytest fixtures for all test suites."""
import sys
import os

# Ensure backend root is on PYTHONPATH so imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
