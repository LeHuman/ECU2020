"""Misc. utility functions"""

import hashlib
import os
import shutil
import glob
import errno
import subprocess
from pathlib import Path
from os.path import join as join_path

import script.text as Text


def encode_log_map(path: str) -> None:
    """Encodes the last generated log map into a z-lib compressed C binary array

    Args:
        path (str): Path to store the C file containing the array
    """
    print("Encoding LogMap 📃\n")
    subprocess.Popen(
        [
            "python",
            "bin2cc.py",
            "-i",
            "log_lookup.json",
            "-o",
            f"{path}\\log_lookup.cpp",
            "-v",
            "log_lookup",
        ]
    ).wait()


def check_git_submodules(file_types: str) -> None:
    """Checks for missing or uninitalized submodules within project

    Args:
        file_types (str): File types to expect in submodules
    """
    err = False
    try:
        response = subprocess.check_output("git config -f .gitmodules -l", stderr=subprocess.STDOUT, shell=True)
        submodules = tuple(line.split("=")[1] for line in response.decode("utf-8").splitlines() if ".url=" not in line)
        for module in submodules:
            if (
                not os.path.exists(module)
                or not os.path.isdir(module)
                or not list(1 for ext in file_types if len(glob.glob(f"**{os.path.sep}*{ext}", root_dir=module, recursive=True)))
            ):
                print(Text.warning("Submodule does not exist, or contains no source files : " + module))
                err = True
    except subprocess.CalledProcessError:
        print(Text.error("Failed to check for git submodules"))
    if err:
        print(Text.important("\nConsider running " + Text.red("git pull --recurse-submodules")))
        print(Text.important("or " + Text.red("git submodule update --init")) + Text.important(" if repo has just been cloned\n"))


LIB_BLACKLIST = join_path("libraries", ".blacklist")


def get_library_blacklist() -> dict[str, list]:
    """Get the library folder blacklist based on core model

    Returns:
        dict[str, list]: folder blacklist as a dict
    """
    blacklist: dict[str, list] = {}
    with open(LIB_BLACKLIST, "r", encoding="utf-8") as file:
        currentModel = ""
        for line in file.readlines():
            if line[0] == ".":
                currentModel = line.split(" ")[0][1:]
                if currentModel not in blacklist:
                    blacklist[currentModel] = []
            else:
                for token in line.split(" "):
                    token = token.strip(" \n")
                    if not token or token[0] == "#":
                        break
                    elif os.path.exists(join_path(os.path.dirname(LIB_BLACKLIST), token)):
                        blacklist[currentModel].append(join_path(os.path.dirname(LIB_BLACKLIST), token))
    return blacklist


FILES_CHANGED = False


def sync_file(filePath: str, offset: str, rawpath: str, workingFilePath: str = None, suppress: bool = False) -> bool:
    """Syncs a file between directories

    Args:
        filePath (str): Path to the original file
        offset (str): Path offset to prepend to the rawpath to get the filepath
        rawpath (str): Path to the directory the original file is in
        workingFilePath (str, optional): Path to the file to sync to. Defaults to offset + filepath.
        suppress (bool, optional): Suppress log messages. Defaults to False.

    Returns:
        bool: Whether the file was synced
    """
    workingFilePath = workingFilePath or f"{offset}{filePath}"

    new = hashFile(filePath)
    old = hashFile(workingFilePath)
    if old == "":
        old = 0

    if not os.path.exists(workingFilePath) or new != old:
        global FILES_CHANGED
        FILES_CHANGED = True
        touch(f"{offset}{rawpath}")
        shutil.copyfile(filePath, workingFilePath)
        if not suppress:
            print(f"Sync File: {os.path.basename(workingFilePath)}")
        return True
    return False


def touch(rawpath: str) -> None:
    """Creates a directory tree

    Args:
        rawpath (str): Path to generate
    """
    try:
        Path(rawpath).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


RAM_MEMO = False


def available_ram() -> bool:
    """Get The amount of RAM available in GBs

    Returns:
        bool: RAM in GBs
    """
    global RAM_MEMO
    if not RAM_MEMO:
        out = subprocess.check_output("wmic OS get FreePhysicalMemory /Value", stderr=subprocess.STDOUT, shell=True)
        RAM_MEMO = round(
            int(str(out).strip("b").strip("'").replace("\\r", "").replace("\\n", "").replace("FreePhysicalMemory=", "")) / 1048576, 2
        )
    return RAM_MEMO


LOW_RAM = 4
BUF_SIZE = 65536


def hashFile(filePath: str) -> str:
    """Hashes a file

    Args:
        filePath (str): Path to the file to hash

    Returns:
        str: HEX string of the file's hash
    """
    if os.path.exists(filePath):
        if available_ram() <= LOW_RAM:
            sha256 = hashlib.sha256()
            with open(filePath, "rb") as f:
                while True:
                    data = f.read(BUF_SIZE)
                    if not data:
                        break
                    sha256.update(data)
            return sha256.digest()
        else:
            with open(filePath, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
    return ""
