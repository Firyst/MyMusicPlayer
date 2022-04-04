from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QTextEdit, QLayout, \
    QAbstractScrollArea, QVBoxLayout, QTextBrowser, QHBoxLayout
from PyQt5.QtGui import QIcon, QPixmap, QFontMetrics, QFont, QTextCursor
import sys
from main import get_scrappers, duration_to_string
from threading import Thread

test_data = []
result_cache = []


def run_scrapper(req, scrapper_func, button):
    print('running search with ', scrapper_func)
    global result_cache
    for r in scrapper_func(req):
        result_cache.append(r)
        button.click()


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('desktop.ui', self)
        self.search_button.clicked.connect(self.start_search)

        self.set_search_label('Nothing here yet...')
        self.cos.clicked.connect(self.upd)
        st = '''
        QWidget
        { 
            background-color: yellow; 
        }
        QWidget:hover {
            background-color: red; 
        }
        '''
        self.test_widget.setStyleSheet(st)
        self.widget2.setStyleSheet(st)

    def upd(self):
        while len(result_cache):
            t = result_cache.pop(0)
            # print(t)
            self.add_search_result(t)

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

    def add_search_result(self, track):
        widg = self.search_scroll_area.widget()

        if isinstance(widg, QLabel):

            new_widget = QWidget()
            new_widget.setAutoFillBackground(True)
            new_layout = QVBoxLayout()

            new_layout.setAlignment(QtCore.Qt.AlignTop)

            new_widget.setLayout(new_layout)

            self.search_scroll_area.setWidget(new_widget)
        widg = self.search_scroll_area.widget()

        style = '''
        QWidget:hover
        {
            background-color: rgb(100, 100, 200);
        }
        '''
        label_widget = QWidget()
        label_layout = QHBoxLayout()


        lbl = QLabel(track.get_param('author'))
        lbl.setWordWrap(False)
        lbl.setTextFormat(QtCore.Qt.PlainText)
        label_layout.addWidget(lbl)
        lbl = QLabel(track.get_param('name'))
        lbl.setWordWrap(False)
        lbl.setTextFormat(QtCore.Qt.PlainText)
        label_layout.addWidget(lbl)
        lbl = QLabel(duration_to_string(track.get_param('duration')))
        lbl.setWordWrap(False)
        lbl.setTextFormat(QtCore.Qt.PlainText)
        label_layout.addWidget(lbl)


        label_widget.setLayout(label_layout)
        label_widget.setAutoFillBackground(True)
        label_widget.setStyleSheet(style)
        widg.layout().addWidget(label_widget)


app = QApplication(sys.argv)
ex = MyWindow()
ex.show()
app.exec_()
