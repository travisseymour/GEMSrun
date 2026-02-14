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

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import hashlib
import inspect
import os
from pathlib import Path
import shutil
import tempfile
import timeit
import traceback

from PIL import Image
import requests

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


def _do_connectivity_request(url: str, timeout: float) -> bool:
    """
    Perform the actual HTTP HEAD request. Called within a thread pool
    so that DNS resolution hangs can be interrupted by the executor timeout.
    """
    response = requests.head(url, timeout=(timeout, timeout), allow_redirects=True)
    return response.status_code < 500


def check_connectivity(url: str, timeout: float = 3.0) -> bool:
    """
    Check internet connectivity by making a HEAD request to the given URL.

    Uses a ThreadPoolExecutor with a hard timeout to ensure we never hang
    longer than `timeout` seconds, even if DNS resolution stalls.
    """
    log.debug(f"starting to check connectivity {url}...")
    start = timeit.default_timer()

    executor = None
    try:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_do_connectivity_request, url, timeout)
        result = future.result(timeout=timeout + 0.5)
        log.debug(f"finished checking connectivity after {timeit.default_timer() - start:0.4f} sec.")
        return result
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            log.debug("connectivity confirmed but remote limited requests (HTTP 429)")
            return True
        log.warning(f"fail to check connectivity! {e}")
        return False
    except FuturesTimeoutError:
        log.warning(f"connectivity check timed out after {timeout}s (possibly DNS resolution hung)")
        return False
    except (requests.exceptions.RequestException, OSError) as e:
        log.warning(f"fail to check connectivity! {e}")
        return False
    except Exception as e:
        log.warning(f"unexpected error during connectivity check: {e}")
        return False
    finally:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)


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
