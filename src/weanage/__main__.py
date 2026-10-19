import multiprocessing

from .cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # needed for process pools in the frozen app
    main()
