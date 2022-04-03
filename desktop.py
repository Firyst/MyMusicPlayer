from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QTextEdit, QLayout, \
    QAbstractScrollArea, QVBoxLayout, QTextBrowser, QHBoxLayout
from PyQt5.QtGui import QIcon, QPixmap, QFontMetrics, QFont, QTextCursor
import sys
from main import get_scrappers
from threading import Thread

test_data = []

def upd2(value):
    ex.add_search_result(value)


result_cache = []

def run_scrapper(req, scrapper_func, button):
    print('running search with ', scrapper_func)
    global result_cache
    result = scrapper_func(req)
    for r in result:
        result_cache.append(r)
        button.click()


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('desktop.ui', self)
        self.search_button.clicked.connect(self.start_search)

        self.set_search_label('Nothing here yet...')
        self.cos.clicked.connect(self.upd)

    def upd(self):
        t = result_cache.pop()
        print(t)
        self.add_search_result(t[0])

    def start_search(self):
        self.set_search_label('Searching...')
        search_text = self.search_request.text()
        if search_text:
            for scrapper in get_scrappers().values():
                Thread(target=run_scrapper, args=(search_text, scrapper, self.cos)).start()

    def set_search_label(self, label_text):
        # sets a label in results field
        lbl = QLabel(label_text)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.search_scroll_area.setWidget(lbl)

    def add_search_result(self, show_name):
        widg = self.search_scroll_area.widget()
        if isinstance(widg, QLabel):
            new_widget = QWidget()
            new_layout = QVBoxLayout()

            new_layout.setAlignment(QtCore.Qt.AlignTop)

            new_widget.setLayout(new_layout)
            self.search_scroll_area.setWidget(new_widget)
        widg = self.search_scroll_area.widget()
        widg.layout().addWidget(QLabel(show_name))


app = QApplication(sys.argv)
ex = MyWindow()
ex.show()
app.exec_()
