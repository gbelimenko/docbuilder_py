import sys
import os
import logging

# Adjust path to import correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.paths import ensure_dirs, LOGS_DIR
from app.utils.logging_config import setup_logging
from app.gui.main_window import MainWindow

def main():
    # 1. Initialize paths and logging
    ensure_dirs()
    setup_logging(LOGS_DIR)
    
    logger = logging.getLogger("DocBuilder.Main")
    logger.info("Initializing DocBuilder Python Application...")

    # 2. Create and show window
    window = MainWindow()
    
    # 3. Run event loop
    logger.info("Application event loop started.")
    window.mainloop()

if __name__ == "__main__":
    main()
