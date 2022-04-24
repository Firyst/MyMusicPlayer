from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap
import sys

from PyQt5.QtWidgets import QApplication


class MyQuestionDialog(QtWidgets.QDialog):
    def __init__(self, parent, label_text, title, styles):
        super().__init__()
        self.parent = parent

        self.ok = False

        self.resize(300, 150)
        self.vertical_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout = QtWidgets.QHBoxLayout()
        self.setWindowTitle(title)

        self.label = QtWidgets.QLabel(self)
        self.label.setObjectName("label")
        self.label.setText(label_text)
        self.main_layout.addWidget(self.label)

        self.vertical_layout.addLayout(self.main_layout)
        self.buttons_layout = QtWidgets.QHBoxLayout()

        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.buttons_layout.addItem(spacer)
        self.button_no = QtWidgets.QPushButton("Cancel")
        self.button_no.setObjectName("button_no")
        self.button_no.setFocusPolicy(Qt.NoFocus)
        self.button_no.clicked.connect(self.end)
        self.buttons_layout.addWidget(self.button_no)

        self.button_ok = QtWidgets.QPushButton("Confirm")
        self.button_ok.setObjectName("button_ok")
        self.button_ok.setFocusPolicy(Qt.NoFocus)
        self.button_ok.clicked.connect(self.confirm)
        self.buttons_layout.addWidget(self.button_ok)

        self.vertical_layout.addLayout(self.buttons_layout)
        self.vertical_layout.setStretch(0, 1)

        # self.image.setPixmap(pm)
        self.setStyleSheet(styles.style)

    def confirm(self):
        self.ok = True
        self.end()

    def end(self):
        self.close()

