#!/usr/bin/env python3
"""
Browser Recording Script using Playwright Codegen

This script launches Playwright codegen for users to record browser interactions.
The recorded code can then be used in the LangGraph flow.

Usage:
    python app/record_browser.py [url]

If no URL is provided, it will start with a blank page.
"""

import sys
import subprocess
import os

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "about:blank"

    print(f"Starting Playwright codegen for URL: {url}")
    print("Perform your browser actions in the opened window.")
    print("When done, copy the generated code from the terminal and save it for use in the automation flow.")
    print("Press Ctrl+C to stop recording.")

    try:
        # Run playwright codegen
        cmd = ["playwright", "codegen", "--target", "python", url]
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nRecording stopped.")
    except subprocess.CalledProcessError as e:
        print(f"Error running codegen: {e}")

if __name__ == "__main__":
    main()
