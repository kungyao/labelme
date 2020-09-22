import re

from qtpy import QT_VERSION
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

from PyQt5.QtCore import Qt
from qtpy.QtCore import QPointF
from qtpy.QtWidgets import QSlider, QLabel, QPushButton

from labelme.logger import logger
import labelme.utils

QT5 = QT_VERSION[0] == "5"


# TODO(unknown):
# - Calculate optimal position so as not to go out of screen area.

class SubWindow(QtWidgets.QMainWindow):
    def __init__(self, labelDialog=None):
        super(SubWindow, self).__init__(labelDialog)
        self.pixmap = QtGui.QPixmap()
        self.labelDialog = labelDialog
        
        # let sub window on the top of main window
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Dialog)
        
        # disable default button
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowMinimizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint, False)
        
        self._painter = QtGui.QPainter()
        
        self.position = QtCore.QPoint(0, 0)
        self.size = QtCore.QSize(100, 100)
        self.box = None
        
    def initialize(self, pixmap, pos, rect):
        self.pixmap = pixmap
        self.box = {
            'xmin' : min(rect[0].x(), rect[1].x()),
            'ymin' : min(rect[0].y(), rect[1].y()),
            'xmax' : max(rect[0].x(), rect[1].x()),
            'ymax' : max(rect[0].y(), rect[1].y()),
        }
        self.size = QtCore.QSize(
            self.box['xmax'] - self.box['xmin'], 
            self.box['ymax'] - self.box['ymin']
        )
        # set sub window size
        # self.resize(self.size)
        self.setFixedSize(self.size)
        self.position = QtCore.QPoint(
            max(0, pos.x() - self.width()), 
            pos.y()
        )
        self.move(self.position)
    
    def paintEvent(self, event):
        if not self.pixmap:
            return super(SubWindow, self).paintEvent(event)
            
        p = self._painter
        p.begin(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        
        p.drawPixmap(0, 0, self.pixmap, self.box['xmin'], self.box['ymin'], self.size.width(), self.size.height())
        
        p.end()
        
    def closeEvent(self, event):
        if not self.labelDialog.inEdit:
            event.accept() # let the window close
        else:
            event.ignore() 

class LabelQLineEdit(QtWidgets.QLineEdit):
    def setListWidget(self, list_widget):
        self.list_widget = list_widget

    def keyPressEvent(self, e):
        if e.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down]:
            self.list_widget.keyPressEvent(e)
        else:
            super(LabelQLineEdit, self).keyPressEvent(e)


class LabelDialog(QtWidgets.QDialog):
    def __init__(
        self,
        text="Enter object label",
        parent=None,
        labels=None,
        sort_labels=True,
        show_text_field=True,
        completion="startswith",
        fit_to_content=None,
        flags=None,
        app=None
    ):
        if fit_to_content is None:
            fit_to_content = {"row": False, "column": True}
        self._fit_to_content = fit_to_content
        super(LabelDialog, self).__init__(parent)
        
        self.edit = LabelQLineEdit()
        self.edit.setPlaceholderText(text)
        self.edit.setValidator(labelme.utils.labelValidator())
        self.edit.editingFinished.connect(self.postProcess)
        if flags:
            self.edit.textChanged.connect(self.updateFlags)
        self.edit_group_id = QtWidgets.QLineEdit()
        self.edit_group_id.setPlaceholderText("Group ID")
        self.edit_group_id.setValidator(
            QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None)
        )
        
        layout = QtWidgets.QVBoxLayout()
        if show_text_field:
            layout_edit = QtWidgets.QHBoxLayout()
            layout_edit.addWidget(self.edit, 6)
            layout_edit.addWidget(self.edit_group_id, 2)
            layout.addLayout(layout_edit)
        
        ### cc region threshold
        ## slider
        defaultValue = 6
        self.sl = QSlider(Qt.Horizontal)
        self.sl.setMinimum(0)
        self.sl.setMaximum(100)
        self.sl.setValue(defaultValue)
        self.sl.valueChanged.connect(self.sl_valuechange)
        ## label show slider value
        self.slLabel = QLabel("")
        self.slLabel.setText(str(defaultValue))
        self.slLabel.setAlignment(Qt.AlignCenter)
        ## tie slider and label together
        slider_set = QtWidgets.QHBoxLayout()
        slider_set.addWidget(self.sl, 6)
        slider_set.addWidget(self.slLabel, 2)
        ## add to total layout
        layout.addLayout(slider_set)
        
        ### text box attribute
        text_box_set = QtWidgets.QVBoxLayout()
        ## column of text
        tmpHor = QtWidgets.QHBoxLayout()
        self.lines = QtWidgets.QLineEdit()
        self.lines.setPlaceholderText("")
        self.lines.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None))
        # label
        self.linesLabel = QLabel("Column of Text")
        self.linesLabel.setAlignment(Qt.AlignLeft)
        tmpHor.addWidget(self.linesLabel, 5)
        tmpHor.addWidget(self.lines, 5)
        text_box_set.addLayout(tmpHor)
        
        ## gep between each column
        tmpHor = QtWidgets.QHBoxLayout()
        self.colGap = QtWidgets.QLineEdit()
        self.colGap.setPlaceholderText("")
        self.colGap.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None))
        # label
        self.colGapLabel = QLabel("Gap Between Column")
        self.colGapLabel.setAlignment(Qt.AlignLeft)
        tmpHor.addWidget(self.colGapLabel, 5)
        tmpHor.addWidget(self.colGap, 5)
        text_box_set.addLayout(tmpHor)
        
        ## box size
        tmpHor = QtWidgets.QHBoxLayout()
        self.boxSize = QtWidgets.QLineEdit()
        self.boxSize.setPlaceholderText("")
        self.boxSize.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None))
        # label
        self.boxSizeLabel = QLabel("Box Size")
        self.boxSizeLabel.setAlignment(Qt.AlignLeft)
        tmpHor.addWidget(self.boxSizeLabel, 5)
        tmpHor.addWidget(self.boxSize, 5)
        text_box_set.addLayout(tmpHor)
        
        ## generate button
        self.generateBoxbb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Apply, QtCore.Qt.Horizontal, self)
        text_box_set.addWidget(self.generateBoxbb)
        ## add to total layout
        layout.addLayout(text_box_set)
        
        # buttons
        self.buttonBox = bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        bb.button(bb.Ok).setIcon(labelme.utils.newIcon("done"))
        bb.button(bb.Cancel).setIcon(labelme.utils.newIcon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)
        # label_list
        self.labelList = QtWidgets.QListWidget()
        if self._fit_to_content["row"]:
            self.labelList.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        if self._fit_to_content["column"]:
            self.labelList.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        self._sort_labels = sort_labels
        if labels:
            self.labelList.addItems(labels)
        if self._sort_labels:
            self.labelList.sortItems()
        else:
            self.labelList.setDragDropMode(
                QtWidgets.QAbstractItemView.InternalMove
            )
        self.labelList.currentItemChanged.connect(self.labelSelected)
        self.labelList.itemDoubleClicked.connect(self.labelDoubleClicked)
        self.edit.setListWidget(self.labelList)
        layout.addWidget(self.labelList)
        # label_flags
        if flags is None:
            flags = {}
        self._flags = flags
        self.flagsLayout = QtWidgets.QVBoxLayout()
        self.resetFlags()
        layout.addItem(self.flagsLayout)
        self.edit.textChanged.connect(self.updateFlags)
        self.setLayout(layout)
        # completion
        completer = QtWidgets.QCompleter()
        if not QT5 and completion != "startswith":
            logger.warn(
                "completion other than 'startswith' is only "
                "supported with Qt5. Using 'startswith'"
            )
            completion = "startswith"
        if completion == "startswith":
            completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            # Default settings.
            # completer.setFilterMode(QtCore.Qt.MatchStartsWith)
        elif completion == "contains":
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            completer.setFilterMode(QtCore.Qt.MatchContains)
        else:
            raise ValueError("Unsupported completion: {}".format(completion))
        completer.setModel(self.labelList.model())
        self.edit.setCompleter(completer)
        
        
        # mine
        self.inEdit = False
        self.app = app
        self.sub_window = SubWindow(self)
    
    def addLabelHistory(self, label):
        if self.labelList.findItems(label, QtCore.Qt.MatchExactly):
            return
        self.labelList.addItem(label)
        if self._sort_labels:
            self.labelList.sortItems()

    def labelSelected(self, item):
        self.edit.setText(item.text())

    def validate(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        if text:
            self.accept()

    def labelDoubleClicked(self, item):
        self.validate()

    def postProcess(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        self.edit.setText(text)

    def updateFlags(self, label_new):
        # keep state of shared flags
        flags_old = self.getFlags()

        flags_new = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label_new):
                for key in keys:
                    flags_new[key] = flags_old.get(key, False)
        self.setFlags(flags_new)

    def deleteFlags(self):
        for i in reversed(range(self.flagsLayout.count())):
            item = self.flagsLayout.itemAt(i).widget()
            self.flagsLayout.removeWidget(item)
            item.setParent(None)

    def resetFlags(self, label=""):
        flags = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label):
                for key in keys:
                    flags[key] = False
        self.setFlags(flags)

    def setFlags(self, flags):
        self.deleteFlags()
        for key in flags:
            item = QtWidgets.QCheckBox(key, self)
            item.setChecked(flags[key])
            self.flagsLayout.addWidget(item)
            item.show()

    def getFlags(self):
        flags = {}
        for i in range(self.flagsLayout.count()):
            item = self.flagsLayout.itemAt(i).widget()
            flags[item.text()] = item.isChecked()
        return flags

    def getGroupId(self):
        group_id = self.edit_group_id.text()
        if group_id:
            return int(group_id)
        return None

    def popUp(self, text=None, move=True, flags=None, group_id=None, mode=None):
        isCCMode = mode == 'cc_rectangle' or mode == 'create_cc_region'
        self.sl.setVisible(isCCMode)
        self.slLabel.setVisible(isCCMode)
        
        if self._fit_to_content["row"]:
            self.labelList.setMinimumHeight(
                self.labelList.sizeHintForRow(0) * self.labelList.count() + 2
            )
        if self._fit_to_content["column"]:
            self.labelList.setMinimumWidth(
                self.labelList.sizeHintForColumn(0) + 2
            )
        # if text is None, the previous label in self.edit is kept
        if text is None:
            text = self.edit.text()
        if flags:
            self.setFlags(flags)
        else:
            self.resetFlags(text)
        self.edit.setText(text)
        self.edit.setSelection(0, len(text))
        if group_id is None:
            self.edit_group_id.clear()
        else:
            self.edit_group_id.setText(str(group_id))
        items = self.labelList.findItems(text, QtCore.Qt.MatchFixedString)
        if items:
            if len(items) != 1:
                logger.warning("Label list has duplicate '{}'".format(text))
            self.labelList.setCurrentItem(items[0])
            row = self.labelList.row(items[0])
            self.edit.completer().setCurrentRow(row)
        self.edit.setFocus(QtCore.Qt.PopupFocusReason)
        if move:
            self.move(QtGui.QCursor.pos())
            
        self.setEditMode(True)
        # temp : pass last create shape to initialize
        self.sub_window.initialize(pixmap=self.app.canvas.pixmap, pos=self.pos(), rect=self.app.canvas.shapes[-1])
        if self.exec_():
            self.setEditMode(False)
            return self.edit.text(), self.getFlags(), self.getGroupId()
        else:
            self.setEditMode(False)
            return None, None, None

    def setEditMode(self, mode):
        self.inEdit = mode
        if mode:
            self.sub_window.show()
        else:
            self.sub_window.close()

    def sl_valuechange(self):
        self.app.canvas.setMinAreaValue(self.sl.value())
        self.slLabel.setText(str(self.sl.value()))
        # self.app.canvas.repaint()
        self.app.paintCanvas()
        # pass

