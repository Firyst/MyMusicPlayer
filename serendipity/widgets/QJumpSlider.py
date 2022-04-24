from PyQt5.QtWidgets import QSlider, QStyle


class QJumpSlider(QSlider):
    def __init__(self, parent=None):
        super(QJumpSlider, self).__init__(parent)
        self.pressed = False
        self.release_func = None  # function that is called when mouse button is released
        self.set_value(33)

    def set_value(self, value):
        if not self.pressed:
            self.setValue(value)

    def mousePressEvent(self, event):
        # Jump to click position
        self.pressed = True
        self.setValue(QStyle.sliderValueFromPosition(self.minimum() - 5, self.maximum() + 5, event.x(), self.width()))

    def mouseMoveEvent(self, event):
        # Jump to pointer position while moving
        self.setValue(QStyle.sliderValueFromPosition(self.minimum() - 5, self.maximum() + 5, event.x(), self.width()))

    def mouseReleaseEvent(self, event):
        self.pressed = False
        if self.release_func:
            self.release_func(self)
