#!/usr/bin/env python3
"""
Dummy Backend for AHK V2 STDIO Communication

This script reads input from STDIN, processes it, and writes the response to STDOUT.
Currently implements a simple echo functionality.
"""

import sys


def process_input(message: str) -> str:
    """
    Process the input message and return a response.
    
    Currently just echoes the input back. Replace this function
    with your actual backend logic.
    
    Args:
        message: The input message from the AHK frontend
        
    Returns:
        The processed response to send back
    """
    # Simple echo - modify this for your actual backend logic
    return f"Echo: {message.upper()}"


def main():
    """Main loop - read from STDIN, process, write to STDOUT."""
    # Ensure stdout is unbuffered for real-time communication
    sys.stdout.reconfigure(line_buffering=True)
    
    while True:
        try:
            # Read a line from STDIN
            line = sys.stdin.readline()
            
            # Check for EOF or empty line (process terminated)
            if not line:
                break
            
            # Strip whitespace
            message = line.strip()
            
            # Check for exit command
            if message == "__EXIT__":
                break
            
            # Skip empty messages
            if not message:
                continue
            
            # Process the input and get response
            response = process_input(message)
            
            # Write response to STDOUT
            print(response, flush=True)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            # Send error back to frontend
            print(f"Error: {str(e)}", flush=True)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
