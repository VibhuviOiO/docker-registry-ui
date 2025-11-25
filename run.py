#!/usr/bin/env python3
"""
Docker Registry UI - Entry point

Usage:
  READ_ONLY=true python run.py
  READ_ONLY=false python run.py
"""

from app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
