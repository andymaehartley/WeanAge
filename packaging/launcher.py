"""Entry point for the single-file app (PyInstaller needs an absolute import here)."""

import multiprocessing

from weanage.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # lets the worker processes start inside the frozen app
    main()
