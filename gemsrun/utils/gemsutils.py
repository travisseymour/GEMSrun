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

from gemsrun import log
import os
from typing import Union
import shutil
import tempfile
import traceback
import inspect
import urllib.request
import urllib.error
import hashlib
from pathlib import Path
from PIL import Image
import timeit


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
    allrecords = cursor.fetchall()

    # define a helper function
    def fileOK(fn):
        return (not fn) or os.path.isfile(os.path.join(media_folder, os.path.basename(fn)))

    # loop through and update outcomelist with any missing files
    for arecord in allrecords:
        for afile in arecord:
            if fileOK(afile) is False:
                outcomelist.append(afile)
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


def check_connectivity(reference):
    try:
        log.debug("starting to check connectivity...")
        start = timeit.default_timer()
        response = urllib.request.urlopen(reference, timeout=1)
        log.debug(f"web response was {response}")
        log.debug(f"finished checking connectivity after {timeit.default_timer() - start:0.4f} sec.")
        return True
    except (TimeoutError, urllib.error.URLError) as e:  # <-- Fix here
        log.warning(f"fail to check connectivity! {e}")
        return False


def string_hash(s: str) -> str:
    ho = hashlib.md5(s.strip().encode())
    return ho.hexdigest()


def get_image_dims(img_file: Path) -> tuple:
    im = Image.open(img_file)
    sz = im.size
    return sz


def boundary(min_value: Union[int, float], my_value: Union[int, float], max_value: Union[int, float]):
    if my_value < min_value:
        return min_value
    elif my_value > max_value:
        return max_value
    else:
        return my_value


if __name__ == "__main__":
    print(check_connectivity("https://www.google.com"))
