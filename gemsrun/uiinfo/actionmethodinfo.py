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

func_infos = {
    "AllowTake": {
        "Definition": [{"Default": "", "Name": "object_id", "Type": "int"}],
        "Help": "This action causes GEMS to make <i>takeable</i> the object identified as <b><i>ObjectId</i></b>.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "ClearKeyBuffer": {
        "Definition": [],
        "Help": "This action clears all characters currently in the keyboard buffer.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "DelVariable": {
        "Definition": [{"Default": "", "Name": "variable", "Type": "str"}],
        "Help": "This action removes the user created token <b><i>variable</i></b>, assuming it exists.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "DisallowTake": {
        "Definition": [{"Default": "", "Name": "object_id", "Type": "int"}],
        "Help": "This action causes GEMS to make <i>untakeable</i> the object identified as <b><i>ObjectId</i></b>.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "DroppedOn": {
        "Definition": [{"Default": "", "Name": "object_id", "Type": "int"}],
        "Help": "This trigger fires when <b><i>Object</i></b> is dragged and then dropped onto the associated object.",
        "Mtype": "trigger",
        "Scope": "objectpocket",
    },
    "HasTotalTimePassed": {
        "Definition": [{"Default": "", "Name": "seconds", "Type": "float"}],
        "Help": "This condition returns <i>True</i> if at least <b><i>Seconds</i></b> seconds has passed since the "
        "current GEMS environment was started.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "HasViewTimePassed": {
        "Definition": [{"Default": "", "Name": "seconds", "Type": "float"}],
        "Help": "This condition returns <i>True</i> if at least <b><i>Seconds</i></b> seconds has passed since the "
        "current view was displayed.",
        "Mtype": "condition",
        "Scope": "viewobject",
    },
    "HideImage": {
        "Definition": [{"Default": "", "Name": "image_file", "Type": "str"}],
        "Help": "This action removes the image based on <b><i>ImageFile</i></b>, assuming it currently being "
        "displayed.",
        "Mtype": "action",
        "Scope": "viewobjectpocket",
    },
    "HideMouse": {
        "Definition": [],
        "Help": "This action hides the mouse cursor.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "HideObject": {
        "Definition": [{"Default": "", "Name": "object_id", "Type": "int"}],
        "Help": "This action causes GEMS to make invisible the object identified as <b><i>Ob<jectId/i></b>.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "HidePockets": {
        "Definition": [],
        "Help": "This action hides all active pockets.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "InputDialog": {
        "Definition": [
            {"Default": "", "Name": "prompt", "Type": "str"},
            {"Default": "", "Name": "variable", "Type": "str"},
            {"Default": "", "Name": "title", "Type": "str"},
            {"Default": "", "Name": "default", "Type": "str"},
        ],
        "Help": "This action causes GEMS to display an input dialog box containing the query <b><i>Prompt</i></b> "
        "and the title <b><i>Title</i></b>. The dialog box will "
        "remain until the user presses the SUBMIT button. The entered text will be associated with the user variable "
        "<b><i>Variable</i></b> and will be "
        "initialized with the default value of <b><i>Default</i></b>.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "KeyBufferContains": {
        "Definition": [{"Default": "", "Name": "characters", "Type": "str"}],
        "Help": "This condition returns <i>True</i> when the keyboard buffer contains the characters in "
        "<b><i>Characters</i></b>. Use only these characters",
        "Mtype": "condition",
        "Scope": "viewglobal",
    },
    "KeyBufferContainsIgnoreCase": {
        "Definition": [{"Default": "", "Name": "characters", "Type": "str"}],
        "Help": "This condition returns <i>True</i> when the keyboard buffer contains the characters in "
        "<b><i>Characters</i></b>, ignoring case. Use only "
        "these characters",
        "Mtype": "condition",
        "Scope": "viewglobal",
    },
    "KeyPress": {
        "Definition": [{"Default": "", "Name": "key", "Type": "str"}],
        "Help": "This trigger fires when <b><i>Key</i></b> is entered on the keyboard.",
        "Mtype": "trigger",
        "Scope": "viewglobal",
    },
    "MouseClick": {
        "Definition": [],
        "Help": "This trigger fires whenever the mouse is <i>left</i>-clicked on an object or pocket.",
        "Mtype": "trigger",
        "Scope": "objectpocket",
    },
    "NavBottom": {
        "Definition": [],
        "Help": "This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Bottom</i></b> "
        "edge of the view.",
        "Mtype": "trigger",
        "Scope": "view",
    },
    "NavLeft": {
        "Definition": [],
        "Help": "This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Left</i></b> "
        "edge of the view.",
        "Mtype": "trigger",
        "Scope": "view",
    },
    "NavRight": {
        "Definition": [],
        "Help": "This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Right</i></b> "
        "edge of the view.",
        "Mtype": "trigger",
        "Scope": "view",
    },
    "NavTop": {
        "Definition": [],
        "Help": "This trigger fires whenever the mouse is <i>left</i>-clicked towards the <b><i>Top</i></b> "
        "edge of the view.",
        "Mtype": "trigger",
        "Scope": "view",
    },
    "PlaySound": {
        "Definition": [
            {"Default": "", "Name": "sound_file", "Type": "str"},
            {"Default": True, "Name": "asynchronous", "Type": "bool"},
            {"Default": False, "Name": "loop", "Type": "bool"},
        ],
        "Help": "This action instructs GEMS to play the audio in <b><i>SoundFile</i></b>. "
        "If <b><i>Asynchronous</i></b> is <i>True</i>, the soundfile plays and returns "
        "control immediately to GEMS. Otherwise, GEMS is blocked until the sound finishes. "
        'If <b><i>Loop</i></b> is "True", the soundfile will loop continually '
        "(MacOS Only).",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "PortalTo": {
        "Definition": [{"Default": "", "Name": "view_id", "Type": "int"}],
        "Help": "This action causes GEMS to load <b><i>ViewId</i></b>.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "Quit": {
        "Definition": [],
        "Help": "This action terminates the current GEMS environment.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "SayText": {
        "Definition": [{"Default": "", "Name": "message", "Type": "str"}],
        "Help": "This action causes GEMS to speak the given <b><i>Message</i></b> using the default Google "
        "Text-To-Speech voice.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "SetVariable": {
        "Definition": [
            {"Default": "", "Name": "variable", "Type": "str"},
            {"Default": "", "Name": "value", "Type": "str"},
        ],
        "Help": "This action set the user created token <b><i>Variable</i></b> to <b><i>Value</i></b>. "
        "If <b><i>Variable</i></b> does not exist, it will first be "
        "created.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "ShowImage": {
        "Definition": [
            {"Default": "", "Name": "image_file", "Type": "str"},
            {"Default": 0, "Name": "left", "Type": "int"},
            {"Default": 0, "Name": "top", "Type": "int"},
            {"Default": 0.0, "Name": "duration", "Type": "float"},
        ],
        "Help": "This action loads and displays <b><i>ImageFile</i></b> at (<b><i>Left</i></b>, <b><i>Top</i></b>) "
        "for <b><i>Duration</i></b> seconds [default = 0 = "
        "forever]. The image is removed when the view is changed.",
        "Mtype": "action",
        "Scope": "viewobjectpocket",
    },
    "ShowMouse": {
        "Definition": [],
        "Help": "This action unhides the mouse cursor, assuming it is currently hidden.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "ShowObject": {
        "Definition": [{"Default": "", "Name": "object_id", "Type": "int"}],
        "Help": "This action causes GEMS to make visible the object identified as <b><i>Object_Id</i></b>.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "ShowPockets": {
        "Definition": [],
        "Help": "This action unhides all active pockets, assuming they are currently hidden.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "ShowURL": {
        "Definition": [{"Default": "", "Name": "url", "Type": "str"}],
        "Help": "This action shows a custom browser window over the current view and loads the page at the supplied "
        "<b><i>URL</i></b>. The window remains atop the GEMS "
        "environment until dismissed by the user (close button).",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "StopAllSounds": {
        "Definition": [],
        "Help": "This action instructs GEMS to stop playing all currently playing audio (MacOS Only).",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "StopAllVideos": {
        "Definition": [],
        "Help": "This action instructs GEMS to stop playing any video that is currently playing.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "StopSound": {
        "Definition": [{"Default": "", "Name": "sound_file", "Type": "str"}],
        "Help": "This action instructs GEMS to stop playing audio based on <b><i>SoundFile</i></b>, assuming it is "
        "currently playing (MacOS Only).",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "StopVideo": {
        "Definition": [{"Default": "", "Name": "video_file", "Type": "str"}],
        "Help": "This action instructs GEMS to stop playing the video in <b><i>VideoFile</i></b>, assuming it is "
        "currently playing..",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "TextBox": {
        "Definition": [
            {"Default": "", "Name": "message", "Type": "str"},
            {"Default": "", "Name": "left", "Type": "int"},
            {"Default": "", "Name": "top", "Type": "int"},
            {"Default": "", "Name": "duration", "Type": "float"},
            {"Default": "", "Name": "fgcolor", "Type": "str"},
            {"Default": "", "Name": "bgcolor", "Type": "str"},
            {"Default": "", "Name": "font_size", "Type": "int"},
            {"Default": False, "Name": "bold", "Type": "bool"},
        ],
        "Help": "This action causes GEMS to draw a textbox over the view containing the text "
        "in <b><i>Message</i></b>. The message will be positioned at (<b><i>Left</i></b>, "
        "<b><i>Top</i></b>) in pixels. After <b><i>Duration</i></b> seconds [default = 0 = forever], "
        "the textbox will be removed. Use the provided font styling "
        "parameters to style the textbox as desired. Note that if left, top == -1, -1 then box will be drawn "
        "at the current cursor location, which could allow for "
        "popup context-like effects when an object is created.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "TextBoxHTML": {
        "Definition": [
            {"Default": "", "Name": "message", "Type": "str"},
            {"Default": "", "Name": "left", "Type": "int"},
            {"Default": "", "Name": "top", "Type": "int"},
            {"Default": "", "Name": "duration", "Type": "float"},
            {"Default": "", "Name": "fgcolor", "Type": "str"},
            {"Default": "", "Name": "bgcolor", "Type": "str"},
            {"Default": "", "Name": "font_size", "Type": "int"},
            {"Default": False, "Name": "bold", "Type": "bool"},
        ],
        "Help": "This action causes GEMS to draw a textbox over the view containing the HTML-formatted text "
        "in <b><i>Message</i></b>. The message will be positioned at (<b><i>Left</i></b>, <b><i>Top</i></b>) "
        "in pixels. After <b><i>Duration</i></b> seconds "
        "[default = 0 = forever], the textbox will be removed. Use the "
        "provided font styling parameters to style the textbox as desired. Note that the markup accepted by the "
        "action is limited and is described at <a "
        'href="bit.ly/wxpmarkup">bit.ly/wxpmarkup</a>. Note that if left, top == -1, -1 then box will be drawn '
        "at the current cursor location, which could allow for popup context-like effects when an object "
        'is created. <font color="red">This Is Not Currently Implemented!</font>',
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "TextDialog": {
        "Definition": [
            {"Default": "", "Name": "message", "Type": "str"},
            {"Default": "", "Name": "title", "Type": "str"},
            {"Default": "", "Name": "dialog_kind", "Type": "str"},
        ],
        "Help": "This action causes GEMS to display an input dialog box containing <b><i>Message</i></b>, with "
        "the title <b><i>Title</i></b>. The parameter <b><i>DialogKind</i></b> will determine the icon type "
        "displayed in the dialog box. The dialog box will remain until the user presses the SUBMIT button.",
        "Mtype": "action",
        "Scope": "viewobjectglobalpocket",
    },
    "TotalTimePassed": {
        "Definition": [{"Default": "", "Name": "seconds", "Type": "float"}],
        "Help": "This trigger fires when at least <b><i>Seconds</i></b> seconds has passed since the current "
        "GEMS environment was started.",
        "Mtype": "trigger",
        "Scope": "global",
    },
    "VarCountEq": {
        "Definition": [{"Default": "", "Name": "count", "Type": "int"}],
        "Help": "This condition returns <i>True</i> if the number of user created variables <u>equals</u> "
        "<b><i>Count</i></b>.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "VarCountGtEq": {
        "Definition": [{"Default": "", "Name": "count", "Type": "int"}],
        "Help": "This condition returns <i>True</i> if the number of user created variables is <u>greater than or "
        "equal to</u> <b><i>Count</i></b>.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "VarCountLtEq": {
        "Definition": [{"Default": "", "Name": "count", "Type": "int"}],
        "Help": "This condition returns <i>True</i> if the number of user created variables is <u>less than or equal "
        "to</u> <b><i>Count</i></b>.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "VarExists": {
        "Definition": [{"Default": "", "Name": "variable", "Type": "str"}],
        "Help": "This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> currently exists.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "VarMissing": {
        "Definition": [{"Default": "", "Name": "variable", "Type": "str"}],
        "Help": "This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> <u>does not</u> "
        "currently exists.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "VarValueIs": {
        "Definition": [
            {"Default": "", "Name": "variable", "Type": "str"},
            {"Default": "", "Name": "value", "Type": "str"},
        ],
        "Help": "This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> exists and "
        "currently has the value <b><i>value</i></b>.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "VarValueIsNot": {
        "Definition": [
            {"Default": "", "Name": "variable", "Type": "str"},
            {"Default": "", "Name": "value", "Type": "str"},
        ],
        "Help": "This condition returns <i>True</i> if the user created token <b><i>Variable</i></b> currently "
        "<u>does not have</u> the value <b><i>value</i></b> or "
        "does not exist.",
        "Mtype": "condition",
        "Scope": "viewobjectglobalpocket",
    },
    "ViewTimePassed": {
        "Definition": [{"Default": "", "Name": "seconds", "Type": "float"}],
        "Help": "This trigger fires when at least <b><i>Seconds</i></b> seconds has passed since the current view "
        "was displayed.",
        "Mtype": "trigger",
        "Scope": "view",
    },
}
