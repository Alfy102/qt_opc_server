from PyQt6.QtWidgets import QDialog

from login_gui import Ui_Dialog as login_dialog
from export_logs_gui import Ui_Dialog as export_logs_dialog
from export_oee_gui import Ui_Dialog as export_oee_dialog
from msg_box_gui import Ui_Dialog as message_dialog

class MessageBox(QDialog, message_dialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)


class ExportLogsDialog(QDialog, export_logs_dialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)


class ExportOeeDialog(QDialog, export_oee_dialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)


class Dialog(QDialog, login_dialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)