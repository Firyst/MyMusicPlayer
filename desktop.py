from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QTextEdit, QLayout, \
    QAbstractScrollArea, QVBoxLayout, QTextBrowser, QHBoxLayout, QSizePolicy, QPlainTextEdit, QToolButton
from PyQt5.QtGui import QIcon, QPixmap, QFontMetrics, QFont, QTextCursor
from main import get_scrappers, duration_to_string
from threading import Thread
import sys
import os

test_data = []
# i know this is bad...
result_queue = dict()  # scrapper_name: [[result_list], is_finished]
result_count = 0
TRACK_PROPERTIES = {'title': "Title", 'artist': "Artist", 'album': "Album", 'composer': 'Composer',
                    'date': 'Release date', 'discnumber': 'Disc number', 'tracknumber': 'Track number',
                    'genre': 'Genre', 'duration': "Duration", 'bitrate': "Bitrate", 'data': "Custom data",
                    'added': "Added to collection"}


def run_scrapper(req, source_name, scrapper_func, update):
    print('running search with ', scrapper_func)
    global result_queue
    result_queue[source_name] = [[], False]
    for r in scrapper_func(req):
        result_queue[source_name][0].append(r)
        update.click()
    result_queue[source_name][1] = True
    update.click()


class StyleManager:
    def __init__(self, folder):
        self.dir = folder
        self.icons = dict()

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


class ResultWidget:
    def __init__(self, track, styles, hover_func=None):
        self.hover_func = hover_func  # function to call when hovered
        style = '''
        QWidget#Result-background:hover
        {
            background-color: rgb(36, 36, 36);
        }
        QToolButton { /* all types of tool button */
        border: 1px solid rgb(0, 0, 0, 0);
        border-radius: 16px;
        }
        QToolButton:hover {
        border: 1px solid rgb(0, 0, 0, 0);
        border-radius: 13px;
        background-color: rgb(36, 36, 36);
        }
        QToolButton:pressed {
        border: 1px solid rgb(0, 0, 0, 0);
        border-radius: 13px;
        background-color: rgb(36, 36, 70);
        }
        '''

        my_widget = QWidget()
        my_widget.setObjectName("Result-background")
        label_layout = QGridLayout()

        self.author_label = QLabel(track.get_param('author'))
        self.author_label.setWordWrap(False)
        label_layout.addWidget(self.author_label, 0, 0, 1, 3)

        self.name_label = QLabel(track.get_param('name'))
        self.name_label.setWordWrap(False)
        label_layout.addWidget(self.name_label, 0, 3, 1, 4)

        self.duration_label = QLabel(duration_to_string(track.get_param('duration')))
        self.duration_label.setWordWrap(False)
        label_layout.addWidget(self.duration_label, 0, 7, 1, 1)

        my_widget.setLayout(label_layout)
        my_widget.setAutoFillBackground(True)
        my_widget.setStyleSheet(style)
        my_widget.setAttribute(QtCore.Qt.WA_Hover)

        self.button = QToolButton()
        self.button.setIcon(styles.get_icon('more'))
        self.button.setIconSize(QtCore.QSize(24, 24))
        self.button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        label_layout.addWidget(self.button, 0, 9, 1, 1)
        self.my_widget = my_widget

        self.track = track
        self.my_widget.setMouseTracking(True)
        self.my_widget.enterEvent = self.enter
        self.my_widget.leaveEvent = self.leave
        self.button.clicked.connect(self.view_track_data)

    def view_track_data(self):
        self.hover_func(self.track)

    def enter(self, event, **kwargs):
        # self.hover_func(self.track)
        pass

    def leave(self, event, **kwargs):
        pass

    def get_widget(self):
        return self.my_widget

    def truncate(self, max_width, metrics=None):
        # resize labels for the given proportions
        props = [0.2, 0.3, 0.2]
        labels = [self.author_label, self.name_label, self.duration_label]
        texts = [self.track['artist'], self.track['title'], duration_to_string(self.track['duration'])]
        if metrics is None:
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


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('desktop.ui', self)
        self.search_button.clicked.connect(self.start_search)
        self.current_results = []

        self.set_search_label('Nothing here yet...')
        self.cos = QPushButton('1')
        self.cos.clicked.connect(self.upd)
        self.properties_button.clicked.connect(self.hide_search_properties)
        # QVBoxLayout.addStretch()

        st = '''
        QWidget
        { 
            background-color: yellow; 
        }
        QWidget:hover {
            background-color: red; 
        }
        '''
        # self.test_widget.setStyleSheet(st)
        # self.widget2.setStyleSheet(st)
        # self.statusbar.showMessage("Loaded.")
        self.styles = StyleManager("styles/default/")

    def debug(self, *args, **kwargs):
        print('debug')

    def hide_search_properties(self):
        self.search_properties.hide()

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        """
        Truncate text while resizing
        """
        if self.current_results:
            metrics = QFontMetrics(self.current_results[0].name_label.font())
            for result in self.current_results:
                result.truncate(self.search_scroll_area.width(), metrics)

    def show_track_data(self, track):
        """
        Show track data in right-side menu
        """
        # print(track)
        self.search_properties.show()
        data_layout = QVBoxLayout()
        for track_kw in TRACK_PROPERTIES:
            if track.get_param(track_kw):
                title = QLabel(TRACK_PROPERTIES[track_kw] + ":")
                font = title.font()
                font.setBold(True)
                title.setFont(font)
                data_layout.addWidget(title)

                if track_kw == "duration":
                    text = QLabel(duration_to_string(track.get_param(track_kw)))
                else:
                    text = QLabel(str(track.get_param(track_kw)))
                text.setWordWrap(True)
                data_layout.addWidget(text)
        properties_widget = QWidget()
        data_layout.addStretch(0)
        properties_widget.setLayout(data_layout)
        self.properties_area.setWidget(properties_widget)

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
        self.current_results = []
        search_text = self.search_request.text()
        if search_text:
            self.set_search_label('Searching...')
            scr = get_scrappers()
            for scrapper in scr:
                Thread(target=run_scrapper, args=(search_text, scrapper, scr[scrapper], self.cos)).start()

    def set_search_label(self, label_text):
        """
        Set a label in results field
        """
        lbl = QLabel(label_text)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.search_scroll_area.setWidget(lbl)

    def add_search_result(self, track):
        widg = self.search_scroll_area.widget()

        if isinstance(widg, QLabel):
            # if layout inside scroll widget
            new_widget = QWidget()
            new_widget.setAutoFillBackground(True)
            new_layout = QVBoxLayout()
            new_layout.setAlignment(QtCore.Qt.AlignTop)
            new_widget.setLayout(new_layout)

            self.search_scroll_area.setWidget(new_widget)
        widget = self.search_scroll_area.widget()
        add_widget = ResultWidget(track, self.styles, self.show_track_data)

        self.current_results.append(add_widget)
        widget.layout().addWidget(add_widget.get_widget())
        add_widget.truncate(self.search_scroll_area.width())


app = QApplication(sys.argv)
app.setStyle("WhiteSur-dark-yellow")
ex = MyWindow()
ex.show()
app.exec_()
