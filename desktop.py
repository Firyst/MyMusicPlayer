from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QTextEdit, QLayout, \
    QAbstractScrollArea, QVBoxLayout, QTextBrowser, QHBoxLayout
from PyQt5.QtGui import QIcon, QPixmap, QFontMetrics, QFont, QTextCursor
import sys
from main import get_scrappers, duration_to_string
from threading import Thread

test_data = []
# i know this is bad...
result_queue = dict()  # scrapper_name: [[result_list], is_finished]
result_count = 0


def run_scrapper(req, source_name, scrapper_func, update):
    print('running search with ', scrapper_func)
    global result_queue
    result_queue[source_name] = [[], False]
    for r in scrapper_func(req):
        result_queue[source_name][0].append(r)
        update.click()
    result_queue[source_name][1] = True
    update.click()


class ResultWidget:
    def __init__(self, track, source=None):
        style = '''
        QWidget#Result-background:hover
        {
            background-color: rgb(50, 100, 200);
        }
        '''
        label_widget = QWidget()
        label_widget.setObjectName("Result-background")
        label_layout = QGridLayout()

        self.author_label = QLabel(track.get_param('author'))
        self.author_label.setWordWrap(False)
        label_layout.addWidget(self.author_label, 0, 0, 1, 2)

        self.name_label = QLabel(track.get_param('name'))
        self.name_label.setWordWrap(False)
        label_layout.addWidget(self.name_label, 0, 2, 1, 2)

        self.duration_label = QLabel(duration_to_string(track.get_param('duration')))
        self.duration_label.setWordWrap(False)
        label_layout.addWidget(self.duration_label, 0, 4, 1, 1)


        label_widget.setLayout(label_layout)
        label_widget.setAutoFillBackground(True)
        label_widget.setStyleSheet(style)
        self.button = QPushButton("Download")
        label_layout.addWidget(self.button, 0, 5, 1, 1)

        self.widget = label_widget
        self.track = track

    def on_enter(self, event):
        print('enter', event)

    def get_widget(self):
        return self.widget

    def truncate(self, metrics, max_width):
        # resizes labels for the given proportions
        props = [0.25, 0.25, 0.2]
        labels = [self.author_label, self.name_label, self.duration_label]
        texts = [self.track['author'], self.track['name'], duration_to_string(self.track['duration'])]
        metrics = QFontMetrics(self.name_label.font())
        for i in range(len(props)):
            size = int(props[i] * max_width)
            text = texts[i]
            if metrics.width(text) > size:
                while metrics.width(text + '...') > size:
                    text = text[:-1]
                labels[i].setText(text + '...')
            else:
                labels[i].setText(text)
            # labels[i].resize(size, labels[i].height())
        # self.button.resize(int((1 - sum(props)) * max_width), self.button.height())


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('desktop.ui', self)
        self.search_button.clicked.connect(self.start_search)
        self.current_results = []

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

    def debug(self, *args, **kwargs):
        print('debug')

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        # truncate text while resizing
        for result in self.current_results:
            result.truncate(None, self.search_scroll_area.width())

    def upd(self):
        global result_count
        finished = True
        for scr_name in result_queue:
            scrapper_res = result_queue[scr_name]
            while len(scrapper_res[0]):
                t = scrapper_res[0].pop(0)
                self.add_search_result(t)
                result_count += 1
            if not scrapper_res[1]:
                finished = False
        if result_count == 0 and finished:
            self.set_search_label('Nothing found.\nCheck search keywords or your connection.')


    def start_search(self):
        self.set_search_label('Searching...')
        self.current_results = []
        search_text = self.search_request.text()
        if search_text:
            scr = get_scrappers()
            for scrapper in scr:
                Thread(target=run_scrapper, args=(search_text, scrapper, scr[scrapper], self.cos)).start()

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
                    background-color: rgb(75, 100, 200);
                }
                '''
        add_widget = ResultWidget(track)
        self.current_results.append(add_widget)
        widg.layout().addWidget(add_widget.get_widget())



app = QApplication(sys.argv)
ex = MyWindow()
ex.show()
app.exec_()
