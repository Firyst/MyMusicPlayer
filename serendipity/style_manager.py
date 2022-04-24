"""
Simple style manager for simplify icon/style loading.
"""

from PyQt5.QtGui import QPalette, QIcon, QPixmap, QColor
import json
import os

STYLES_DIR = os.path.join("..", "styles")


class StyleManager:
    def __init__(self, style):
        self.icons = dict()
        self.style = ""
        self.palette = QPalette()
        self.dir = os.path.join(STYLES_DIR, style)

    def load_icons(self, icon_names):
        """
        Load icons with specified names (iterable).
        """
        for icon_name in icon_names:
            icon = QIcon()
            icon.addPixmap(QPixmap(os.path.join(self.dir, icon_name + ".png")), QIcon.Normal, QIcon.Off)
            self.icons[icon_name] = icon

    def get_icon(self, name):
        """
        Loads icon (if necessary) and returns it.
        """
        if name not in self.icons:
            self.load_icons([name])
        return self.icons[name]

    def get_pixmap(self, name):
        """
        Loads a picture and return QPixmap object.
        """
        return QPixmap(os.path.join(self.dir, name))

    def load_style(self, filename):
        """
        Just read a QSS file.
        """
        with open(os.path.join(self.dir, filename)) as f:
            self.style = self.style + f.read() + '\n'

    def load_colors(self, filename):
        if self.style:
            with open(os.path.join(self.dir, filename)) as j:
                colors = json.loads(j.read())
                for color_name in colors:
                    color = tuple(map(str, colors[color_name]))
                    if len(color) == 4:
                        self.style = self.style.replace(color_name, f"rgba({', '.join(color)})")
                    else:
                        self.style = self.style.replace(color_name, f"rgb({', '.join(color)})")

    def load_palette(self, filename):
        """
        Create QPalette from JSON file.
        """
        new_palette = QPalette()
        with open(os.path.join(self.dir, filename)) as j:
            palette = json.loads(j.read())
            for color_role in palette:
                role = eval(f"QPalette.{color_role}")
                color = palette[color_role]
                new_palette.setColor(role, QColor(color[0], color[1], color[2], color[3]))
        self.palette = new_palette
        return new_palette