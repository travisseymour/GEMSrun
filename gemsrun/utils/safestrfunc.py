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

import ast
import re
import regex

"""
This module contains tools that allow for the safe eval()'ing of method calls.
The focus of this module is making sure function parameters are only constant types.
This thwarts attempts to insert arbitrary Python expressions/calls as function parameters.
It limits arguments to constants of basic types such as ints, float, strings, etc. It allows lists and tuples,
but only those that only contain constants (checks recursively).
"""

FUNK_PATTERN = re.compile(r"(\w+)\((.*?), (.*?)\)$")


def get_param(param: str) -> str:
    """
    takes a parameter argument and returns only the argument value,
    just in case the parameter name is included.
    E.g., 'enabled=True' and 'True' both return 'True'
    """
    try:
        return re.sub(r"^ *\w+ *= *", "", param.strip())
    except IndexError:
        return param


def func_str_parts(cmd: str) -> tuple:
    """
    returns the function name and parameter list from a call within a string.
    E.g.,
    func_str_parts("OpenDoor(key='home', knob_right=True, combination=[3,4,2,3])")
    returns
    'OpenDoor', ["key='home'", 'knob_right=True', 'combination=[3,4,2,3]']
    """
    FUNK_PATTERN = re.compile(r"(\w+)\s*\((.*?)\)$")  # works
    SPLIT_PATTERN = regex.compile(r'"[^"]*"(*SKIP)(*FAIL)|,\s*')  # works
    func = FUNK_PATTERN.match(cmd.strip().replace("[", '"(LEFT) ').replace("]", ' (RIGHT)"'))  # trying to fix lists
    fn = func.group(1)
    params = func.group(2)
    param_list = SPLIT_PATTERN.split(params)
    param_list = [item.replace('"(LEFT) ', "[").replace(' (RIGHT)"', "]") for item in param_list]

    return fn, param_list


def remove_seq_boundaries(seq_str: str) -> str:
    """
    Removes all Python sequence identifiers.
    E.g.,
    remove_seq_boundaries("[1,2,2]")
    returns
    "1,2,2"
    """
    return re.sub(r"[\[\]\(\)\{\}]", "", seq_str.strip())


def is_safe_value(value_str: str) -> bool:
    """
    Returns True if value_str is of type ast.Constant, otherwise False.
    If value_str is a sequence, recursively checks to make sure that all items
    are of ast.Constant, otherwise False.
    """
    if not value_str.strip():
        return True

    try:
        tree = ast.parse(value_str, "<stdin>")
        ast_value_type = type(tree.body[0].__dict__["value"])
    except SyntaxError:
        print(f"ERROR: {value_str} is a mal-formed Python value.")
        return False

    if ast_value_type is ast.Constant:
        return True
    elif ast_value_type in (ast.List, ast.Tuple):
        _seq = re.split(r" *, *", remove_seq_boundaries(value_str))

        return all((is_safe_value(item) for item in _seq))
    else:
        return False


if __name__ == "__main__":
    print("THESE SHOULD RETURN TRUE\n--------------------------")
    print(is_safe_value("4"))
    print(is_safe_value("3.3 "))
    print(is_safe_value('"Hello, you ok?"'))
    print(is_safe_value("[1,2, 3]"))
    print(is_safe_value('("a", "b", 3.0)'))
    print(is_safe_value('("a", "b", ["hello", 23])'))

    print("\nTHESE SHOULD RETURN FALSE\n--------------------------")
    print(is_safe_value('("a", "b", datetime.datetime.now())'))
