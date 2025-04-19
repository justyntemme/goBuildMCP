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


@mcp.tool()
def run(
    project_dir: str, args: str = "", timeout_seconds: int = 60
) -> Tuple[str, bool]:
    """
    Run a Go executable from the specified project directory for max 5 seconds

    Args:
        project_dir: Directory containing the Go executable
        args: Command-line arguments to pass to the executable (space-separated)
        timeout_seconds: Maximum execution time in seconds (not used - always exits after 5 sec)

    Returns:
        Tuple containing (output, success)
    """

    import subprocess
    import os
    import shlex
    import time
    import signal
    import psutil  # Make sure this is installed
    from pathlib import Path

    # Initialize output and status
    output_lines = []
    success = False
    process = None

    # Validate project directory
    project_path = Path(project_dir).resolve()
    if not project_path.is_dir():
        return f"Error: Directory '{project_dir}' does not exist", False

    try:
        # Find the executable
        executable = None
        executables = []

        if os.name == "nt":  # Windows
            for exe in project_path.glob("*.exe"):
                if exe.is_file():
                    executables.append(exe)
        else:  # Unix-like
            for file in project_path.iterdir():
                if (
                    file.is_file()
                    and os.access(file, os.X_OK)
                    and not file.name.endswith(".go")
                ):
                    executables.append(file)

        # Handle executable selection (same as before)
        if len(executables) > 1:
            dir_name = project_path.name
            for exe in executables:
                if exe.stem == dir_name:
                    executable = exe
                    break
            if executable is None:
                executable = executables[0]
                output_lines.append(
                    f"Multiple executables found. Using: {executable.name}"
                )
        elif len(executables) == 1:
            executable = executables[0]

        # Try building if no executable found
        if executable is None:
            output_lines.append("No executable found. Attempting to build first...")
            build_output, build_success = build(project_dir)
            output_lines.append(build_output)

            if not build_success:
                return "\n".join(output_lines), False

            # Try to find the executable again
            executables = []
            if os.name == "nt":  # Windows
                for exe in project_path.glob("*.exe"):
                    if exe.is_file():
                        executables.append(exe)
            else:  # Unix-like
                for file in project_path.iterdir():
                    if (
                        file.is_file()
                        and os.access(file, os.X_OK)
                        and not file.name.endswith(".go")
                    ):
                        executables.append(file)

            if executables:
                executable = executables[0]
            else:
                return (
                    f"Error: Unable to find or build an executable in '{project_dir}'",
                    False,
                )

        # Prepare command line arguments
        cmd = [str(executable)]
        if args:
            cmd.extend(shlex.split(args))

        output_lines.append(f"Running: {' '.join(cmd)}")

        # Start the process with non-blocking I/O
        process = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Function to kill process and children
        def kill_process_tree(pid):
            try:
                # Get the parent process
                parent = psutil.Process(pid)
                # Get all children recursively
                children = parent.children(recursive=True)

                # Kill children first
                for child in children:
                    try:
                        child.kill()
                    except:
                        pass

                # Kill the parent
                parent.kill()

                # Wait for processes to terminate
                gone, still_alive = psutil.wait_procs(children + [parent], timeout=1)

                # Force kill any remaining processes
                for p in still_alive:
                    try:
                        p.kill()
                    except:
                        pass

            except Exception as e:
                output_lines.append(f"Error killing process tree: {str(e)}")
                # Fallback: try direct kill
                try:
                    os.kill(pid, signal.SIGKILL if os.name != "nt" else signal.SIGTERM)
                except:
                    pass

        start_time = time.time()
        MAX_RUNTIME = 5  # Always exit after 5 seconds
        stdout_lines = []
        stderr_lines = []

        # Non-blocking output reading
        import select
        import io

        # Make sure stdout/stderr are non-blocking
        if os.name != "nt":  # Unix-like
            import fcntl

            fcntl.fcntl(process.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
            fcntl.fcntl(process.stderr.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

        # For Windows, we'll use a polling approach
        def read_nonblocking(stream):
            try:
                if os.name == "nt":  # Windows
                    from msvcrt import get_osfhandle
                    from win32pipe import PeekNamedPipe
                    from win32file import ReadFile

                    handle = get_osfhandle(stream.fileno())
                    try:
                        _, avail, _ = PeekNamedPipe(handle, 0)
                        if avail > 0:
                            return stream.readline()
                    except:
                        return ""
                else:  # Unix
                    return stream.readline()
            except:
                return ""
            return ""

        # Main execution loop
        while True:
            # Check if we've exceeded MAX_RUNTIME
            elapsed = time.time() - start_time
            if elapsed > MAX_RUNTIME:
                output_lines.append(
                    f"Reached maximum runtime of {MAX_RUNTIME} seconds, terminating..."
                )
                break

            # Check if process has completed naturally
            exit_code = process.poll()
            if exit_code is not None:
                output_lines.append(f"Process exited with code {exit_code}")
                success = exit_code == 0
                break

            # Read any available output
            if os.name == "nt":  # Windows
                # Use polling on Windows
                stdout_line = read_nonblocking(process.stdout)
                if stdout_line:
                    stdout_lines.append(stdout_line.rstrip())

                stderr_line = read_nonblocking(process.stderr)
                if stderr_line:
                    stderr_lines.append(stderr_line.rstrip())
            else:  # Unix
                # Use select on Unix
                rlist, _, _ = select.select(
                    [process.stdout, process.stderr], [], [], 0.1
                )
                if process.stdout in rlist:
                    stdout_line = process.stdout.readline()
                    if stdout_line:
                        stdout_lines.append(stdout_line.rstrip())

                if process.stderr in rlist:
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        stderr_lines.append(stderr_line.rstrip())

            # Short sleep to avoid CPU spin
            time.sleep(0.1)

        # Forcibly terminate the process if it's still running
        if process.poll() is None:
            output_lines.append("Forcibly terminating process...")
            try:
                # Try the clean function first
                kill_process_tree(process.pid)
            except:
                # Fall back to simpler methods
                try:
                    process.kill()
                except:
                    pass

            # Wait a bit to ensure it's dead
            time.sleep(0.5)

            # Double-check it's dead
            if process.poll() is None:
                output_lines.append("Warning: Process may still be running!")

        # Collect any remaining output
        try:
            stdout, stderr = process.communicate(timeout=1)
            if stdout:
                stdout_lines.extend(stdout.splitlines())
            if stderr:
                stderr_lines.extend(stderr.splitlines())
        except:
            pass

        # Add output to the response
        if stdout_lines:
            output_lines.append("Standard Output:")
            output_lines.extend(stdout_lines)

        if stderr_lines:
            output_lines.append("Standard Error:")
            output_lines.extend(stderr_lines)

        # Consider the run successful if we completed normally or terminated as planned
        if success is False:  # Only change if not already set
            success = True
            output_lines.append(
                "Process ran and was terminated after 5 seconds as planned"
            )

    except Exception as e:
        output_lines.append(f"Unexpected error during execution: {str(e)}")
        success = False

    finally:
        # Make absolutely sure the process is dead
        if process and process.poll() is None:
            try:
                # One last attempt to kill the process
                process.kill()
            except:
                pass

    # Join all output lines into a single string
    output_str = "\n".join(output_lines)
    return output_str, success
