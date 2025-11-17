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
import ssl
import tempfile
import timeit
import traceback
import urllib.error
import urllib.request

import certifi
from PIL import Image

from gemsrun import log

_SSL_CONTEXT: ssl.SSLContext | None = None


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
        return (not file_name) or os.path.isfile(os.path.join(media_folder, os.path.basename(file_name)))

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


def _get_ssl_context() -> ssl.SSLContext:
    """
    Build an SSL context backed by certifi's CA bundle so HTTPS checks work even
    on platforms (e.g., python.org macOS builds) that ship without system CAs.
    """
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        context = ssl.create_default_context()
        try:
            context.load_verify_locations(certifi.where())
        except Exception as e:  # pragma: no cover - defensive logging
            log.debug(f"unable to load certifi CA bundle for connectivity check ({e})")
        _SSL_CONTEXT = context
    return _SSL_CONTEXT


def check_connectivity(url: str):
    try:
        log.debug(f"starting to check connectivity {url}...")
        start = timeit.default_timer()
        response = urllib.request.urlopen(url, timeout=1, context=_get_ssl_context())
        log.debug(f"web response was {response}")
        log.debug(f"finished checking connectivity after {timeit.default_timer() - start:0.4f} sec.")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 429:
            log.debug("connectivity confirmed but remote limited requests (HTTP 429)")
            return True
        log.warning(f"fail to check connectivity! {e}")
        return False
    except (TimeoutError, urllib.error.URLError, ssl.SSLError) as e:  # <-- Fix here
        log.warning(f"fail to check connectivity! {e}")
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
