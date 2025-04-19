#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("go-build-mcp")

class GoBuildHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()
        
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            self._set_headers()
            self.wfile.write(json.dumps({"error": "Empty request"}).encode())
            return

        # Parse the request body
        request_body = self.rfile.read(content_length).decode("utf-8")
        try:
            request_data = json.loads(request_body)
        except json.JSONDecodeError:
            self._set_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        # Get the directory path from the request
        directory_path = request_data.get("path")
        if not directory_path:
            self._set_headers()
            self.wfile.write(json.dumps({"error": "Missing 'path' parameter"}).encode())
            return

        # Ensure the directory exists
        if not os.path.isdir(directory_path):
            self._set_headers()
            self.wfile.write(json.dumps({
                "buildSuccess": False,
                "output": f"Directory does not exist: {directory_path}"
            }).encode())
            return

        # Try to build the Go application
        logger.info(f"Building Go project in: {directory_path}")
        result = self._build_and_run(directory_path)
        
        # Send response
        self._set_headers()
        self.wfile.write(json.dumps(result).encode())

    def _build_and_run(self, directory_path):
        """Build and run the Go application in the specified directory"""
        # Store current directory so we can return to it
        original_dir = os.getcwd()
        
        try:
            # Log the directory we're changing to
            logger.info(f"Changing to directory: {directory_path}")
            os.chdir(directory_path)
            
            # Verify we're in the right directory
            current_dir = os.getcwd()
            logger.info(f"Current working directory: {current_dir}")
            
            if not os.path.samefile(current_dir, directory_path):
                return {
                    "buildSuccess": False,
                    "output": f"Failed to change to correct directory. Expected: {directory_path}, Actual: {current_dir}"
                }
            
            # Run go build
            logger.info("Running: go build .")
            build_process = subprocess.run(
                ["go", "build", "."],
                capture_output=True,
                text=True
            )
            
            # Check if build was successful
            if build_process.returncode != 0:
                return {
                    "buildSuccess": False,
                    "output": build_process.stderr
                }
            
            # Find the binary (the one that was just created)
            binary_name = None
            
            # First try to determine binary name from directory name (common convention)
            dir_binary = os.path.basename(os.path.normpath(directory_path))
            if os.path.isfile(dir_binary) and os.access(dir_binary, os.X_OK):
                binary_name = dir_binary
                logger.info(f"Found binary based on directory name: {binary_name}")
            
            # If that fails, look for executables
            if binary_name is None:
                logger.info("Searching for executable files in directory")
                go_mod_time = 0
                if os.path.exists("go.mod"):
                    go_mod_time = os.path.getmtime("go.mod")
                    
                for file in os.listdir("."):
                    file_path = os.path.join(".", file)
                    if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                        # Check if this is a recently created/modified file (likely our binary)
                        if go_mod_time == 0 or os.path.getmtime(file_path) > go_mod_time:
                            binary_name = file
                            logger.info(f"Found binary by executable check: {binary_name}")
                            break
            
            if not binary_name:
                return {
                    "buildSuccess": True,
                    "output": "Build successful, but couldn't find the binary to execute."
                }
            
            # Run the binary
            logger.info(f"Running binary: {binary_name}")
            run_process = subprocess.run(
                [f"./{binary_name}"],
                capture_output=True,
                text=True
            )
            
            # Combine stdout and stderr
            output = run_process.stdout
            if run_process.stderr:
                output += "\n" + run_process.stderr
            
            return {
                "buildSuccess": True,
                "output": output
            }
        finally:
            # Always return to the original directory
            logger.info(f"Returning to original directory: {original_dir}")
            os.chdir(original_dir)

# Create a proper class-based server object that Claude Desktop can detect
class MCPServer:
    def __init__(self):
        self.handler = GoBuildHandler
    
    def run(self, port=8080):
        server_address = ("", port)
        httpd = HTTPServer(server_address, self.handler)
        logger.info(f"Starting Go Build MCP server on port {port}")
        httpd.serve_forever()

# Create the standard server object that Claude Desktop will look for
mcp = MCPServer()
server = mcp  # Alternative name

# For command-line execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP server for building and running Go applications")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the server on")
    args = parser.parse_args()
    
    try:
        mcp.run(args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped")
        sys.exit(0)