from PyQt5.QtCore import Qt
import sys

# -----------
# File dialog
# -----------

if sys.platform == "darwin":
    fileFormats = "UFO Fonts (*.ufo)"
else:
    fileFormats = "UFO Fonts (metainfo.plist)"

# ---------
# Font size
# ---------

if sys.platform == "darwin":
    headerPointSize = 11
else:
    headerPointSize = 8

# ----
# Keys
# ----

if sys.platform == "darwin":
    deleteKey = Qt.Key_Backspace
else:
    deleteKey = Qt.Key_Delete
