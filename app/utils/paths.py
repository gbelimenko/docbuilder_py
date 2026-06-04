import os

# Resolve paths relative to this file
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(APP_DIR)

LOGS_DIR = os.path.join(ROOT_DIR, "logs")
CONFIGS_DIR = os.path.join(ROOT_DIR, "configs")

def ensure_dirs():
    """Ensure standard directories exist."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(CONFIGS_DIR, exist_ok=True)

def resolve_dynamic_path(original_path: str, config_path: str = "") -> str:
    """
    Resolves a file path dynamically. If the path exists, it is returned.
    If not, it looks for the file in the same directory as the config_path,
    the project-level 'ref' directory, or the current working directory.
    Supports a fallback for Word templates if the original is missing.
    """
    if not original_path:
        return ""
        
    # Standardize path separators
    normalized_path = os.path.normpath(original_path)
    if os.path.exists(normalized_path):
        return normalized_path

    # Extract basename (handles Windows UNC and standard backslashes/slashes)
    filename = original_path.replace("\\", "/").split("/")[-1]
    if not filename:
        return original_path

    # Search candidates directories
    search_dirs = []
    if config_path:
        config_dir = os.path.dirname(os.path.abspath(config_path))
        search_dirs.append(config_dir)
        # Also try parent or subdirs relative to config
        search_dirs.append(os.path.join(config_dir, "ref"))
        search_dirs.append(os.path.join(config_dir, "..", "ref"))
        
    search_dirs.append(os.path.join(ROOT_DIR, "ref"))
    search_dirs.append(os.getcwd())
    
    # Try finding exact filename
    for sdir in search_dirs:
        if not sdir or not os.path.isdir(sdir):
            continue
        candidate = os.path.normpath(os.path.join(sdir, filename))
        if os.path.exists(candidate):
            return candidate

    # Word Template Fallback: If not found and original_path is docx/docm
    is_word = filename.lower().endswith((".docx", ".docm"))
    if is_word:
        for sdir in search_dirs:
            if not sdir or not os.path.isdir(sdir):
                continue
            try:
                files = os.listdir(sdir)
                word_files = [f for f in files if f.lower().endswith((".docx", ".docm"))]
                if len(word_files) == 1:
                    candidate = os.path.normpath(os.path.join(sdir, word_files[0]))
                    return candidate
            except Exception:
                pass

    return original_path

