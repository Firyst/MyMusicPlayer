"""
Setup window for desktop installation
"""


from PyQt5.QtWidgets import QMainWindow, QFileDialog, QMessageBox
from serendipity.main import Playlist
from database_operator import MusicDatabase
from PyQt5 import uic
import os
import sqlite3
import json

CFG_PATH = os.path.join('..', 'config.json')

class SetupWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(os.path.join('ui', 'setup.ui'), self)
        # self.setStyleSheet("QWidget{font-family: " + QLabel().font().family() + "}")

        self.local_setup_button.clicked.connect(self.local_setup)
        self.select_folder_button1.clicked.connect(self.open_folder_dialog)
        self.local_install_finish.clicked.connect(self.finish_local_setup)
        self.back_button1.clicked.connect(self.go_to_menu)
        self.folder_input1.textChanged.connect(self.button_switch1)
        self.data = dict()

    def local_setup(self):
        self.pages.setCurrentIndex(1)

    def go_to_menu(self):
        self.pages.setCurrentIndex(0)

    def open_folder_dialog(self):
        file = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        self.folder_input1.setText(os.path.abspath(file))

    def button_switch1(self):
        # switch go button during local install
        self.local_install_finish.setEnabled(os.path.isdir(self.folder_input1.text()))
        if os.path.isdir(self.folder_input1.text()):
            self.data["storage"] = self.folder_input1.text()

    def finish_local_setup(self):
        try:
            os.mkdir(os.path.join(self.data["storage"], "cache"))
            print("Setup done!")
            self.init_local_db()
        except PermissionError:
            dialog = QMessageBox.critical(self, "Error", "No permission to write in selected folder.", QMessageBox.Ok)
        except FileNotFoundError:
            dialog = QMessageBox.critical(self, "Error", "Folder seems not present.", QMessageBox.Ok)
        except FileExistsError:
            print("Setup done!")
            self.init_local_db()

    def init_local_db(self):
        test_db = MusicDatabase(os.path.join(self.data["storage"], "local.db"))
        try:
            if test_db.get_playlist(1):
                print("DB already exists and is valid.")
                self.close()
            else:
                raise sqlite3.OperationalError
        except sqlite3.OperationalError:
            print("Creating new db.")
            try:
                test_db.create_db_structure()
                test_db.add_playlist(Playlist(0, "My tracks", description="All saved tracks."))
                test_db.close()
            except sqlite3.OperationalError or KeyError or ValueError or IndexError or TypeError:
                # some error occurred :(
                dialog = QMessageBox.critical(self, "Error", "Something went wrong. Try cleaning target folder.",
                                              QMessageBox.Ok)
                return 0
        # update config
        with open(CFG_PATH, 'r') as f:
            cur_config = json.loads(f.read())
        cur_config["first_run"] = False
        cur_config["storage"] = self.data["storage"]
        with open(CFG_PATH, 'w') as f:
            f.write(json.dumps(cur_config))
        self.close()
