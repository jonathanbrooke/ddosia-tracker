def log_message(message):
    print(f"[LOG] {message}")

def handle_error(error):
    print(f"[ERROR] {error}")

def create_directory(path):
    import os
    if not os.path.exists(path):
        os.makedirs(path)
        log_message(f"Created directory: {path}")
    else:
        log_message(f"Directory already exists: {path}")