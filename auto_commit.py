import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os

class GitAutoCommit(FileSystemEventHandler):
    def __init__(self, path='.'):
        self.path = path
        # Initialize a set to track files that have been modified
        self.modified_files = set()
        # Minimum time between commits in seconds
        self.commit_cooldown = 5
        self.last_commit_time = 0

    def on_modified(self, event):
        if event.is_directory:
            return

        # Get relative path
        try:
            relative_path = os.path.relpath(event.src_path, self.path)
        except ValueError:
            return

        # Ignore certain files and directories
        if (relative_path.startswith('.git/') or
            relative_path.startswith('venv/') or
            relative_path.startswith('__pycache__/') or
            relative_path.endswith('.pyc') or
            relative_path == 'auto_commit.py'):
            return

        # Add the modified file to our set
        self.modified_files.add(relative_path)
        
        # Check if enough time has passed since last commit
        current_time = time.time()
        if current_time - self.last_commit_time >= self.commit_cooldown:
            self.commit_changes()

    def commit_changes(self):
        if not self.modified_files:
            return

        try:
            # Convert set to list for the commit message
            files_to_commit = list(self.modified_files)
            
            # Git add
            subprocess.run(['git', 'add'] + files_to_commit, check=True)
            
            # Create commit message
            commit_message = f"Auto-commit: Updated {', '.join(files_to_commit)}"
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            
            # Push to GitHub
            subprocess.run(['git', 'push'], check=True)
            
            print(f"Successfully committed and pushed changes for: {', '.join(files_to_commit)}")
            
            # Clear the set of modified files
            self.modified_files.clear()
            # Update last commit time
            self.last_commit_time = time.time()
            
        except subprocess.CalledProcessError as e:
            print(f"Error during git operations: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Path to watch (current directory)
    path = "."
    
    # Create event handler and observer
    event_handler = GitAutoCommit(path)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    
    # Start watching
    print("Starting auto-commit service...")
    print("Watching for file changes (Press Ctrl+C to stop)")
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nAuto-commit service stopped")
    
    observer.join() 