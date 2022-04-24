from PyQt5.QtWidgets import QMenu
from PyQt5 import QtCore


class QMyMenu(QMenu):
    def __init__(self):
        super(QMyMenu, self).__init__()
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in [QtCore.QEvent.MouseButtonRelease]:
            if isinstance(obj, QMenu):
                if obj.activeAction():
                    if not obj.activeAction().menu():  # if the selected action does not have a submenu
                        # eat the event, but trigger the function
                        obj.activeAction().trigger()
                        return True
        return super(QMyMenu, self).eventFilter(obj, event)

