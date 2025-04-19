"""
FastMCP Desktop Example

A simple example that exposes the desktop directory as a resource.
"""

from pathlib import Path
from typing import Tuple
from mcp.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("go-builder")


@mcp.tool()
def build(project_dir: str) -> Tuple[str, bool]:
    """Build go Project in project_dir param and reply with success/fail"""

    import subprocess
    import os
    from pathlib import Path

    # Initialize output and status
    output_lines = []
    success = False

    # Validate project directory
    project_path = Path(project_dir).resolve()
    if not project_path.is_dir():
        return f"Error: Directory '{project_dir}' does not exist", False

    try:
        # Check for Go files
        go_files = list(project_path.glob("**/*.go"))
        if not go_files:
            return f"Error: No Go source files found in '{project_dir}'", False

        # Run go build
        output_lines.append(f"Building Go project in {project_dir}...")

        # Check for go.mod file and handle dependencies if needed
        go_mod_path = project_path / "go.mod"
        if go_mod_path.exists():
            output_lines.append("Found go.mod file, running 'go mod tidy'")
            tidy_process = subprocess.run(
                ["go", "mod", "tidy"], cwd=project_dir, capture_output=True, text=True
            )

            if tidy_process.returncode != 0:
                output_lines.append(
                    f"Warning during 'go mod tidy': {tidy_process.stderr.strip()}"
                )

        # Run the actual build
        build_process = subprocess.run(
            ["go", "build", "-v", "."], cwd=project_dir, capture_output=True, text=True
        )

        # Process build output
        if build_process.stdout:
            output_lines.append(build_process.stdout.strip())

        # Check build status
        if build_process.returncode == 0:
            success = True
            output_lines.append("Build successful ✓")

            # Try to identify the executable
            # For Windows, look for .exe files
            # For Unix, look for executable permissions
            executables = []

            if os.name == "nt":  # Windows
                for exe in project_path.glob("*.exe"):
                    if exe.is_file():
                        executables.append(exe.name)
            else:  # Unix-like
                for file in project_path.iterdir():
                    if (
                        file.is_file()
                        and os.access(file, os.X_OK)
                        and not file.name.endswith(".go")
                    ):
                        executables.append(file.name)

            if executables:
                output_lines.append(f"Executable(s) created: {', '.join(executables)}")
            else:
                # The executable might have been created in the GOPATH/bin directory
                output_lines.append(
                    "Note: No executables found in the project directory. "
                    "Check your GOPATH/bin directory if you're using 'go install'."
                )
        else:
            # Build failed
            success = False
            output_lines.append("Build failed ✗")
            if build_process.stderr:
                output_lines.append(f"Error details:\n{build_process.stderr.strip()}")

    except subprocess.SubprocessError as e:
        output_lines.append(f"Error executing Go build command: {str(e)}")
        success = False
    except Exception as e:
        output_lines.append(f"Unexpected error during build process: {str(e)}")
        success = False

    # Join all output lines into a single string
    output_str = "\n".join(output_lines)
    return output_str, success
