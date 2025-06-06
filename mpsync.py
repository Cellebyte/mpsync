"""
mpsync is a tool that watches a folder for changes and synchronizes
them to a micropython board.

Author: Thilo Michael (uhlomuhlo@gmail.com)
"""

import argparse
from pathlib import PosixPath
from typing import Optional, Union

from mp.conbase import ConError
from mp.mpfexp import MpFileExplorer, MpFileExplorerCaching, RemoteIOError
from mp.pyboard import PyboardError


class MPSync:
    """
    The class that handles the the synchronizing between the folder and the MicroPython
    board.
    """

    """Number of times mpfs should try to connect to a board before giving up."""
    CONNECT_TRIES = 5

    """Protocol for mpfs to use. Maybe used in the future to support telnet connections?"""
    MPF_PROTOCOL = "ser"

    """Time to wait after filesystem changes before uploading begins."""
    WAITING_TIME = 0.5

    def __init__(
        self, folder=".", port="/dev/ttyUSB0", verbose=False, reset=False, caching=False
    ):
        self.folder = folder
        self.port = port
        self.reset = reset
        self.caching = caching
        self._explorer: Optional[Union[MpFileExplorer, MpFileExplorerCaching]] = None
        self.verbose = verbose
        self._error = []
        self._ts = 0

    @property
    def explorer(self) -> Union[MpFileExplorer, MpFileExplorerCaching]:
        if self._explorer is None:
            raise Exception("unconnected, please connect!")
        return self._explorer

    def _copy_file(self, file: PosixPath):
        dst = file.as_posix().replace(self.folder, "")
        print(f"Copying {dst}")
        self.explorer.put(file, dst)

    def _create_folder(self, folder: PosixPath):
        dst = folder.as_posix().replace(self.folder, "")
        print(f"Creating folder {dst}")
        try:
            self.explorer.md(dst)
        except RemoteIOError as e:
            print(e)

    def _delete(self, path: PosixPath):
        dst = path.as_posix().replace(self.folder, "")
        print(f"Deleting {dst}")
        self.explorer.rm(dst)

    def disconnect(self):
        if self._explorer is not None:
            try:
                self._explorer.close()
                self._explorer = None
                return True
            except RemoteIOError as e:
                print(e)
        return False

    def connect(self):
        """Connects to a micropython board. This has to be called before copying files
        to the board."""
        port_path = PosixPath(self.port)
        try:
            self.disconnect()
            if not port_path.exists() or port_path.is_dir():
                print(f"Port '{self.port}' does not exist or is a folder!")
                return False
            for i in range(self.CONNECT_TRIES):
                if self.caching:
                    self._explorer = MpFileExplorerCaching(
                        f"{self.MPF_PROTOCOL}:{self.port}", reset=self.reset
                    )
                else:
                    self._explorer = MpFileExplorer(
                        f"{self.MPF_PROTOCOL}:{self.port}", reset=self.reset
                    )
                if self.explorer:
                    print("Connected to %s" % self.explorer.sysname)
                    return True
                print(f"could not connect to {self.port} [{i}/{self.CONNECT_TRIES}]")
        except (PyboardError, ConError, AttributeError) as e:
            print(str(e))
        print(f"could not connect to board {self.port}!")
        return False

    def __enter__(self):
        if self.connect():
            return self
        raise Exception("can't connect")

    def __exit__(self, _, __, ___):
        if self.disconnect():
            return
        raise Exception("can't disconnect")

    def sync(self, f: Optional[PosixPath] = None):
        if not f:
            f = PosixPath(self.folder)
        for entry in f.glob("*"):
            if entry.is_dir():
                self._create_folder(entry)
                self.sync(entry)
            elif entry.is_file():
                self._copy_file(entry)
        return


def parse_args():
    parser = argparse.ArgumentParser(
        description="A tool that continously synchronizes "
        "a folder to a MicroPython board."
    )
    parser.add_argument(
        "-f",
        "--folder",
        help="The folder that should be used to synchronize. "
        "Default is the current working directory.",
        default=None,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="Serial port of the MicroPython board.",
        default="/dev/ttyUSB0",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Print debug information from mpfshell.",
        default=False,
        action="store_true",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.folder:
        args.folder = PosixPath().cwd().as_posix()

    with MPSync(folder=args.folder, port=args.port, verbose=args.verbose) as mps:
        print(f"Start syncing folder '{args.folder}' to board at '{args.port}'")
        mps.sync()
    return


if __name__ == "__main__":
    main()
