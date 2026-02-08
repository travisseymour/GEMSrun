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

import re
from textwrap import dedent

from munch import Munch
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont

from gemsrun import app_short_name
from gemsrun.session.version import __version__

# https://www.w3schools.com/html/tryit.asp?filename=tryhtml_table


class InfoDialog(QtWidgets.QDialog):
    def __init__(self, parent, db: Munch):
        super().__init__(parent)
        self.tab_widget = None
        self.variable_text = None
        self.view_text = None
        self.env_text = None
        self.main_layout = None
        self.db = db
        self.options = db.Global.Options

        self.init_ui()
        self.init_global_info()
        self.update_info()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_info)
        self.timer.start(1000)

    def init_ui(self):
        self.setMinimumSize(800, 600)
        self.setWindowTitle(f"{app_short_name} v{__version__} Information Window")

        self.setFont(QFont("Arial", 16))

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.env_text = QtWidgets.QTextEdit()
        self.view_text = QtWidgets.QTextEdit()
        self.variable_text = QtWidgets.QTextEdit()

        for text_edit in (self.env_text, self.view_text, self.variable_text):
            text_edit.setReadOnly(True)

        self.tab_widget = QtWidgets.QTabWidget(self)
        self.tab_widget.addTab(self.env_text, "Environment")
        self.tab_widget.addTab(self.view_text, "View")
        self.tab_widget.addTab(self.variable_text, "Variables")

        self.main_layout.addWidget(self.tab_widget)

    def init_global_info(self):
        tr = dedent(
            """
        <tr>
            <td>{}</td>
            <td>{}</td>
        </tr>
        """
        ).rstrip()

        info = """
        <style>
        table{
            border-collapse: separate;
            border-spacing: 10px; /* Apply cell spacing */
        }
        table, th, td{
            border: 1px solid #666;
            padding: 0.3em
        }
        table th, table td{
            padding: 5px; /* Apply cell padding */
        }
        </style>
        <h3>Environment Info</h3>
        <table style="width:100%">
        <tr><th>Property</th><th>Value</th></tr>
        """
        info = dedent(info).rstrip()

        other_info = {
            "Total Views": len(self.db.Views),
            "Total Objects": sum(len(view.Objects) for view in self.db.Views.values()),
            "Total Actions": sum(
                len(action)
                for action in [view.Actions for view in self.db.Views.values()]
            ),
        }

        # add info from global options
        for key, value in self.options.items():
            if key not in ["Id"]:
                info += tr.format(key, value)

        # add other info
        for key, value in other_info.items():
            info += tr.format(key, value)

        info += dedent(
            """
        </table>
        """
        )

        # show it
        self.env_text.setHtml(info)

    def show_view_info(self):
        view_id = self.parent().current_view_id
        view = self.db.Views[str(view_id)]

        # =============
        # Basic Info
        # ============

        info = """
        <style>
        table{
            border-collapse: separate;
            border-spacing: 10px; /* Apply cell spacing */
        }
        table, th, td{
            border: 1px solid #666;
            padding: 0.3em
        }
        table th, table td{
            padding: 5px; /* Apply cell padding */
        }
        </style>

        <h3>View Info</h3>
        <table style="width:100%">
        <tr><th>Property</th><th>Value</th></tr>
        """

        for key in ("Id", "Name", "Foreground", "Background", "Overlay"):
            info += f"<tr><td>{key}</td><td>{view[key]}</td></tr>\n"

        info += dedent(
            """
        </table>
        """
        )

        # =============
        # Object Info
        # ============

        info += """
        <h3>View Objects</h3>
        <table style="width:100%">
        <tr><th>Id</th><th>Name</th><th>Visible</th><th>Takeable</th><th>Draggable</th><th>ActionCount</th>
        <th>Triggers</th><th>Actions</th></tr>
        """

        for obj in view.Objects.values():
            info += (
                f"<tr><td>{obj.Id}</td><td>{obj.Name}</td><td>{obj.Visible}</td><td>{obj.Takeable}</td>"
                f"<td>{obj.Draggable}</td><td>{len(obj.Actions)}</td>"
                f"<td>{', '.join(set(self.func_name(action.Trigger) for action in obj.Actions.values()))}</td>"
                f"<td>{', '.join(set(self.func_name(action.Action) for action in obj.Actions.values()))}</td>"
                f"</tr>\n"
            )

        info += dedent(
            """
        </table>
        """
        )

        try:
            buffer = self.parent().view_window.key_buffer
            assert buffer
        except Exception:
            buffer = "<i>None</i>"

        info += dedent(
            f"""
        <h3>View String Buffer</h3>
        {buffer}
        """
        )

        # show it
        self.view_text.setHtml(info)

    def show_variables(self):
        variables = self.db.Variables

        info = """
        <style>
        table{
            border-collapse: separate;
            border-spacing: 10px; /* Apply cell spacing */
        }
        table, th, td{
            border: 1px solid #666;
            padding: 0.3em
        }
        table th, table td{
            padding: 5px; /* Apply cell padding */
        }
        </style>

        <h3>Variables</h3>
        <table style="width:100%">
        <tr><th>Variable</th><th>Value</th></tr>
        """

        for variable, value in variables.items():
            info += f"<tr><td>{variable}</td><td>{value}</td></tr>\n"

        info += dedent(
            """
        </table>
        """
        )

        # show it
        self.variable_text.setHtml(info)

    def func_name(self, call: str) -> str:
        try:
            return re.search(r"^[^\(]+", call).group(0)
        except Exception:
            return "???"

    def update_info(self):
        self.show_view_info()
        self.show_variables()
