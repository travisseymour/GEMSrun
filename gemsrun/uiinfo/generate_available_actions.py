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

from pathlib import Path
from pprint import pprint
import re
import textwrap

# NOTE: You Must PEP8 the code in pycharm first, regex patterns assume you will!

FUNC_PATTERN = r"def ([A-Za-z]+)\(([^\)]+)\)"
# group1: 'VarValueIsNot'
# group2: 'self, varname: str, value: float'
PARAM_PATTERN = r"([a-z_]+: [A-Za-z]+)+"
PARAM_PATTERN2 = r"([a-z_]+: [A-Za-z]+( *= *[\w\.\"]+)*)+"  # allows defaults
# group1: 'font_size: int'
# group2: ' = 1'
# ---
# group1: 'varname: str'
# group2: ' = "Sara"'
INFO_PATTERN = r"def ([A-Za-z]+)[^\n]+\n[^']+'''([^'}]+)'''"  # needs multiline and dotall


# group1: 'VarValueIs'
# group2: 'This condition returns True if the user created token [varname] exists and currently has the value [value].
#         ':scope viewobjectglobalpocket    :mtype condition


def fix_param(parameters: list) -> list:
    res = []
    for parameter in parameters:
        left, right = parameter
        name, _type = left.split(":")
        _type = _type.split("=")[0]
        name, _type = name.strip(), _type.strip()
        if name == "skiplog":
            continue
        default = right.split("=")[-1].strip()
        if default:
            if _type in ("int", "float"):
                default = eval(default)
            elif _type == "bool" and default in ("True", "False"):
                default = eval(default)
        item = dict(Name=name, Type=_type, Default=default)
        res.append(item)
    return res


def format_info(func_info_text: str) -> dict:
    text = func_info_text.strip()
    text = textwrap.dedent(text)
    text = text.replace("\n", "").replace("    ", " ").replace("  ", " ")
    try:
        help = re.search(r"^[^:]+", text, flags=re.DOTALL).group()
        scope = re.search(r":scope *([A-Za-z]+)", text).group(1)
        mtype = re.search(r":mtype *([A-Za-z]+)", text).group(1)
    except AttributeError:
        return {}

    help, scope, mtype = help.strip(), scope.strip(), mtype.strip()
    return dict(Help=help, Scope=scope, Mtype=mtype)


# get viewplanel code which has func defs in it
code = Path("../gui/viewpanel.py").read_text()
# use regex to extract func defs and info
func_defs = re.findall(pattern=FUNC_PATTERN, string=code)
func_infos = re.findall(pattern=INFO_PATTERN, string=code, flags=re.MULTILINE | re.DOTALL)

# convert func_defs to a dict and...
func_defs = dict(func_defs)
# ...parse parameter list and
func_defs = {k: re.findall(pattern=PARAM_PATTERN2, string=v) for k, v in func_defs.items()}
# ...convert them into cleaned up dictionaries
func_defs = {k: fix_param(v) for k, v in func_defs.items()}

# convert func infos to a dict and ...
func_infos = dict(func_infos)
# ... remove any without proper scope and mtype markers
func_infos = {k: v for k, v in func_infos.items() if ":scope" in v and ":mtype" in v}
# ... remove any for which we don't have a func def
func_infos = {k: v for k, v in func_infos.items() if k in func_defs}

# ... convert info into dict
func_infos = {k: format_info(v) for k, v in func_infos.items()}

# show intermediates
# pprint(func_infos)
# print(f'\n{"=" * 40}')
# pprint(func_defs)

# combine
for func in func_infos:
    func_infos[func]["Definition"] = func_defs[func]

# show final
print(f"\n{'@' * 40}")
a = ""
with open("actionmethodinfo.py", "w") as outfile:
    outfile.write("func_infos = \\\n")
    pprint(func_infos, width=180, stream=outfile)
# print(f'func_infos = \\\n{str(func_infos)}')
print("\nSee file actionmethodinfo.py for result of this operation.")
print("\nNOTE: ANY METHOD NOT IN THAT LIST IS NOT PROPERLY FORMATTED (MAYBE MISSING HELP AND SCOPE?)")
