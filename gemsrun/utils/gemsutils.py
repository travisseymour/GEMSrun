"""
GEMSrun: Environment Runner for GEMS (Graphical Environment Management System)
Copyright (C) 2025 Travis L. Seymour, PhD

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import hashlib
import inspect
import os
from pathlib import Path
import shutil
import socket
import tempfile
import time
import traceback

from PIL import Image

from gemsrun import log


def create_temporary_folder() -> Path:
    tmpdir = tempfile.gettempdir()
    temp_folder = Path(tmpdir, "gemsruntemp")
    # if it exists, recursively delete it
    if temp_folder.is_dir():
        shutil.rmtree(temp_folder)
    # if it still exists, continue trying to use it anyway
    # create new version of tmp folder
    temp_folder.mkdir(exist_ok=True)
    # if it didn't work (or we cant access it), fail
    assert temp_folder.is_dir()
    return temp_folder


def check_media(db_filename, database, media_folder) -> tuple:
    outcomelist = []

    cursor = database.cursor()
    # load all the views images
    cursor.execute("SELECT Foreground, Background, Overlay FROM views")
    all_records = cursor.fetchall()

    # define a helper function
    def file_ok(file_name: str):
        return (not file_name) or os.path.isfile(
            os.path.join(media_folder, os.path.basename(file_name))
        )

    # loop through and update outcomelist with any missing files
    for record in all_records:
        for file in record:
            if file_ok(file) is False:
                outcomelist.append(file)
    return tuple(set(outcomelist))


def func_name():
    """https://stackoverflow.com/questions/251464/how-to-get-a-function-name-as-a-string-in-python"""
    return traceback.extract_stack(None, 2)[0][2]


def func_params():
    """https://stackoverflow.com/questions/251464/how-to-get-a-function-name-as-a-string-in-python"""
    # for method, must dump self key and add frame's name (that's the function name)
    frame = inspect.currentframe().f_back
    # print(frame.f_code.co_name)
    args, _, _, values = inspect.getargvalues(frame)
    res = {i: values[i] for i in args}
    if "self" in res:
        del res["self"]

    return res


def check_connectivity(timeout: float = 3.0) -> bool:
    """
    Check internet connectivity by attempting a socket connection to reliable DNS servers.

    This approach is faster and more robust than HTTP requests:
    - No HTTP overhead
    - No rate limiting concerns
    - Uses only standard library
    - DNS servers have very high uptime (99.999%)
    """
    hosts = [
        ("8.8.8.8", 53),  # Google DNS
        ("1.1.1.1", 53),  # Cloudflare DNS
        ("208.67.222.222", 53),  # OpenDNS
    ]

    log.debug("starting connectivity check...")
    start = time.perf_counter()

    for host, port in hosts:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((host, port))
                elapsed = time.perf_counter() - start
                log.debug(
                    f"connectivity confirmed via {host}:{port} in {elapsed:.4f} sec."
                )
                return True
        except OSError:
            continue

    elapsed = time.perf_counter() - start
    log.warning(
        f"connectivity check failed after {elapsed:.4f} sec (tried {len(hosts)} hosts)"
    )
    return False


def string_hash(s: str) -> str:
    ho = hashlib.md5(s.strip().encode())
    return ho.hexdigest()


def get_image_dims(img_file: Path) -> tuple[int, int]:
    im = Image.open(img_file)
    return im.size


def boundary(min_value: int | float, my_value: int | float, max_value: int | float):
    if my_value < min_value:
        return min_value
    elif my_value > max_value:
        return max_value
    else:
        return my_value


if __name__ == "__main__":
    print(check_connectivity("https://www.google.com"))
