import re
import functools

from qtpy import QT_VERSION
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

from PyQt5.QtCore import Qt
from qtpy.QtCore import QPointF
from qtpy.QtWidgets import QSlider, QLabel, QPushButton, QAction

from labelme.logger import logger
import labelme.utils
from labelme.shape import Shape

QT5 = QT_VERSION[0] == "5"


# TODO(unknown):
# - Calculate optimal position so as not to go out of screen area.

class MyCanvas(QtWidgets.QWidget):
    selectionChanged = QtCore.Signal(list)
    
    def __init__(self, parent=None):
        super(MyCanvas, self).__init__(parent)
        
        self.setMouseTracking(True)
        # self.setFocusPolicy(QtCore.Qt.WheelFocus)
        
        self.parent = parent
        self.pixmap = QtGui.QPixmap()
        self.np_image = None
        
        self._painter = QtGui.QPainter()

        self.scale = 1.0
        
        self.size = QtCore.QSize(100, 100)
        self.box = None
        
        self.col_lines = []
        self.row_lines = []
        
        self.hShape = None
        self.hType = None
        self.hShapeIndex = None
        
        self.prevhShape = None
        
        self.movingShape = False
        
        self.cols = 0
        self.rows = 0
        self.pt_size = 1
        
        
        self.defaultThres = 20
        self.thres = 10

    def initialize(self, pixmap, np_image, pos, rect):
        self.scale = 1.0
        self.pixmap = pixmap
        self.np_image = np_image
        self.box = {
            'xmin'  : min(rect[0].x(), rect[1].x()),
            'ymin'  : min(rect[0].y(), rect[1].y()),
            'width' : abs(rect[0].x() - rect[1].x()),
            'height': abs(rect[0].y() - rect[1].y()),
        }
        self.size = QtCore.QSize(
            self.box['width'] + 10, 
            self.box['height'] + 10
        )
        
        w, h = np_image.shape[:2]
        self.pt_scale = min(w / self.box['width'], h / self.box['height'])
        self.thres = self.defaultThres / self.pt_scale
        self.setMinimumSize(self.size)
        
        # set sub window size
        self.resize(self.size)
        # self.setFixedSize(self.size)
        # position = QtCore.QPoint(
            # max(0, pos.x() - self.width()), 
            # pos.y()
        # )
        
        self.cols = 0
        self.rows = 0
        
        self.col_lines = []
        self.row_lines = []
        self.hShape = self.hType = self.hShapeIndex = None
        self.prevhShape = None
    
    def generateGrid(self, cols, rows, reset=False):
        self.selectionChanged.emit([])
        
        if cols == 0 or rows == 0 or (self.cols == cols and self.rows == rows and not reset):
            self.col_lines = []
            self.row_lines = []
            return
        
        w = self.box['width']
        h = self.box['height']
        
        colStep = self.box['width'] / cols
        rowStep = self.box['height'] / rows
        # set default box size to (colStep - defaultColGap)
        defaultColGap = 5
        defaultBoxSize = colStep - defaultColGap
        
        def createLine(p0, p1, pt_scale, color=(0, 127, 0)):
            shape = Shape()
            shape.shape_type = "line"
            shape.addPoint(p0)
            shape.addPoint(p1)
            shape.setColor(color[0], color[1], color[2])
            shape.scale = pt_scale
            shape.close()
            return shape
        
        self.col_lines = []
        for i in range(cols):
            # main line
            x = colStep * i
            self.col_lines.append(createLine(
                QPointF(x, 0),
                QPointF(x, h),
                self.pt_scale,
                color=(0, 255, 0)
            ))
            # constrain line
            x = x + defaultBoxSize
            self.col_lines.append(createLine(
                QPointF(x, 0),
                QPointF(x, h),
                self.pt_scale,
                color=(255, 0, 0)
            ))
        
        self.row_lines = []
        # add bottom line to bound the text area
        for i in range(rows + 1):
            # main line
            y = defaultBoxSize * i
            self.row_lines.append(createLine(
                QPointF(0, y),
                QPointF(w, y),
                self.pt_scale,
                color=(0, 0, 255)
            ))
            # # constrain line
            # y = y + defaultBoxSize
            # self.row_lines.append(createLine(
                # QPointF(0, y),
                # QPointF(w, y),
                # self.pt_scale,
                # color=(0, 0, 255)
            # ))
                
        self.cols = cols
        self.rows = rows
        self.update()
    
    def offsetToCenter(self):
        s = self.scale
        area = super(MyCanvas, self).size()
        w, h = self.box['width'] * s, self.box['height'] * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QtCore.QPoint(x, y)
    
    def paintEvent(self, event):
        if not self.pixmap:
            return super(SubWindow, self).paintEvent(event)
            
        p = self._painter
        p.begin(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        
        p.scale(self.scale, self.scale)
        p.translate(self.offsetToCenter())
        
        p.drawPixmap(0, 0, self.pixmap, self.box['xmin'], self.box['ymin'], self.box['width'], self.box['height'])
        
        for line in self.col_lines:
            line.paint(p)
        for line in self.row_lines:
            line.paint(p)
            
        p.end()
    
    def mouseMoveEvent(self, event):
        try:
            if QT5:
                pos = self.transformPos(event.localPos())
            else:
                pos = self.transformPos(event.posF())
        except AttributeError:
            return
        
        if QtCore.Qt.LeftButton & event.buttons():
            if self.selectedLine():
                self.boundedMoveLine(pos)
                self.repaint()
                self.movingShape = True
            # elif self.hShape and self.prevPoint:
                # self.boundedMoveShapes(pos)
                # self.repaint()
                # self.movingShape = True
            self.prevPoint = pos
            return
        
        self.prevPoint = pos
        
        colLineSize = len(self.col_lines)
        # select main col line (green)
        for i in range(0, len(self.col_lines), 2):
            line = self.col_lines[i]
            dis = line.distance(pos, self.thres)
            if dis is not None:
                self.hShape = line
                self.hType = 'col'
                self.hShapeIndex = i
                # line.highlightClosest(line.MOVE_VERTEX)
                self.update()
                break
        else: # nothing found go through
            # select constrain col line (red)
            for i in range(1, len(self.col_lines), 2):
                line = self.col_lines[i]
                dis = line.distance(pos, self.thres)
                if dis is not None:
                    self.hShape = line
                    self.hType = 'col'
                    self.hShapeIndex = i
                    # line.highlightClosest(line.MOVE_VERTEX)
                    self.update()
                    break
            else: # nothing found go through
                # select offset line (blue)
                for i, line in enumerate(self.row_lines):
                    dis = line.distance(pos, self.thres)
                    if dis is not None:
                        self.hShape = line
                        self.hType = 'row'
                        self.hShapeIndex = i
                        # line.highlightClosest(line.MOVE_VERTEX)
                        self.update()
                        break
                else: # nothing found go through
                    if self.hShape:
                        self.update()
                    self.hShape = self.hType = self.hShapeIndex = None
        
    def mousePressEvent(self, event):
        try:
            if QT5:
                pos = self.transformPos(event.localPos())
            else:
                pos = self.transformPos(event.posF())
        except AttributeError:
            return
            
        if event.button() == QtCore.Qt.LeftButton:
            self.selectShapePoint(pos)
            # self.prevPoint = pos
            self.update()
    
    def mouseReleaseEvent(self, event):
        # if event.button() == QtCore.Qt.RightButton:
            # menu = self.menu
            # menu.exec_(self.mapToGlobal(event.pos()))
            # QtWidgets.QApplication.restoreOverrideCursor()
        if self.movingShape and self.hShape:
            self.movingShape = False
    
    def transformPos(self, point):
        """Convert from widget-logical coordinates to painter-logical ones."""
        return point / self.scale - self.offsetToCenter()

    def setKanaBoxOffset(self, move):
        for line in self.row_lines:
            line.moveAllVertexBy(move)

    def setKanaBoxSize(self, sizeDif):
        move = QPointF(sizeDif, 0)
        # take odd index of col line
        for i in range(1, len(self.col_lines), 2):
            self.col_lines[i].moveAllVertexBy(move)
        move = QPointF(0, sizeDif)
        # first of the row line is used to define the top of the bubble
        for i in range(1, len(self.row_lines)):
            self.row_lines[i].moveAllVertexBy(move * i)
    
    def boundedMoveLine(self, pos):
        shape, type, shapeIndex = self.hShape, self.hType, self.hShapeIndex
        point = shape.points[0]
        if shape.shape_type == "line":
            move = pos - point
            if type == 'col':
                move.setY(0.0)
                if shapeIndex%2 == 0:
                    shape.moveAllVertexBy(move)
                    self.col_lines[shapeIndex + 1].moveAllVertexBy(move)
                else:
                    self.setKanaBoxSize(move.x())
            elif type == 'row':
                move.setX(0.0)
                self.setKanaBoxOffset(move)
    
    # def boundedMoveShapes(self, pos):
        # self.hShape.moveAllVertexBy(pos - self.prevPoint)
    
    def outOfPixmap(self, p):    
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w - 1 and 0 <= p.y() <= h - 1)
        
    def selectShapePoint(self, point):
        if self.prevhShape:
            self.prevhShape.selected = False
            self.prevhShape = None
        # A vertex is marked for selection.
        if self.selectedLine():  
            self.prevhShape = self.hShape
            shape, type, shapeIndex = self.hShape, self.hType, self.hShapeIndex
            shape.selected = True
    
    def selectedLine(self):
        return self.hShape is not None
    
    def resizeEvent(self, event):
        ratio_w = event.size().width() / self.box['width']
        ratio_h = event.size().height() / self.box['height']
        self.scale = min(ratio_w, ratio_h)
        # self.thres = self.defaultThres / (self.pt_scale * self.scale)
        self.update()    
    

class SubWindow(QtWidgets.QMainWindow):
    def __init__(self, labelDialog=None):
        super(SubWindow, self).__init__(labelDialog)
        self.labelDialog = labelDialog
        # let sub window on the top of main window
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Dialog)
        
        # disable default button
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowMinimizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint, False)

        self.canvas = MyCanvas(self)
        
        # right click menu
        self.menu = QtWidgets.QMenu()
        
        action = functools.partial(labelme.utils.newAction, self)
        # measureMode = action(
            # self.tr("Measure Box Size"),
            # self.ppppp,
            # None,
            # "objects",
            # self.tr("Measure Box Size"),
            # enabled=True,
        # )
        # self.menu.addAction(measureMode)
        
        # self.ifSelectLine = action(
            # self.tr('Select Sep Line'), 
            # self.setCanvasViewState,
            # None, 
            # checkable=True, 
            # checked=True)
        # self.ifSelectBox = action(
            # self.tr('Select Text Box'), 
            # self.setCanvasViewState,
            # None, 
            # checkable=True, 
            # checked=True)
        # self.ifShowLine = action(
            # self.tr('Show Sep Line'), 
            # self.setCanvasViewState,
            # None, 
            # checkable=True, 
            # checked=True)
        # self.ifShowBox = action(
            # self.tr('Show Text Box'), 
            # self.setCanvasViewState,
            # None, 
            # checkable=True, 
            # checked=True)
        
        # on the top of window
        # menuBar = self.menuBar()
        # tmpMenu = menuBar.addMenu('View')
        # tmpMenu.addAction(self.ifSelectLine)
        # tmpMenu.addAction(self.ifSelectBox)
        # tmpMenu.addAction(self.ifShowLine)
        # tmpMenu.addAction(self.ifShowBox)
        
        self.setCentralWidget(self.canvas)
        self.canvas.menu = self.menu
        
    def initialize(self, pixmap, np_image, pos, rect):
        self.canvas.initialize(pixmap, np_image, pos, rect)
        area = super(SubWindow, self).size()
        aw, ah = area.width(), area.height()
        self.move(pos - QtCore.QPoint(area.width(), 0))
    def generateGrid(self, cols, rows, reset=False):
        self.canvas.generateGrid(cols, rows, reset)
    # def setCanvasViewState(self):
        # self.canvas.ifSelectLine = self.ifSelectLine.isChecked()
        # self.canvas.ifSelectBox = self.ifSelectBox.isChecked()
        # self.canvas.ifShowLine = self.ifShowLine.isChecked()
        # self.canvas.ifShowBox = self.ifShowBox.isChecked()
        # self.canvas.update()
    
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
        
        # disable default button. Use default close button will have bug 
        # that sub window setting will be reset and can not modify again.
        # QtCore.Qt.Dialog setting will be reseted.
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        
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
        self.cc_threshold_ui = []
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
        self.cc_threshold_ui.append(self.sl)
        self.cc_threshold_ui.append(self.slLabel)
        layout.addLayout(slider_set)
        
        ### text box attribute
        self.text_box_ui = []
        text_box_set = QtWidgets.QVBoxLayout()
        ## column of text
        tmpHor = QtWidgets.QHBoxLayout()
        self.text_cols = QtWidgets.QLineEdit("4")
        self.text_cols.setPlaceholderText("")
        self.text_cols.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None))
        # label
        self.text_cols_label = QLabel("Columns of Text")
        self.text_cols_label.setAlignment(Qt.AlignLeft)
        tmpHor.addWidget(self.text_cols_label, 5)
        tmpHor.addWidget(self.text_cols, 5)
        # add to ui group
        self.text_box_ui.append(self.text_cols_label)
        self.text_box_ui.append(self.text_cols)
        text_box_set.addLayout(tmpHor)        
        
        ## rows of text
        tmpHor = QtWidgets.QHBoxLayout()
        self.text_rows = QtWidgets.QLineEdit("4")
        self.text_rows.setPlaceholderText("")
        self.text_rows.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None))
        # label
        self.text_rows_label = QLabel("Rows of Text")
        self.text_rows_label.setAlignment(Qt.AlignLeft)
        tmpHor.addWidget(self.text_rows_label, 5)
        tmpHor.addWidget(self.text_rows, 5)
        # add to ui group
        self.text_box_ui.append(self.text_rows_label)
        self.text_box_ui.append(self.text_rows)
        text_box_set.addLayout(tmpHor)
        
        ## generate button
        self.generateBoxbb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Apply | QtWidgets.QDialogButtonBox.Reset, 
            QtCore.Qt.Horizontal, 
            self
        )
        self.generateBoxbb.button(self.generateBoxbb.Apply).clicked.connect(self.setTextBoxAttribute)
        self.generateBoxbb.button(self.generateBoxbb.Reset).clicked.connect(self.setTextBoxAttribute)
        # add to ui group
        self.text_box_ui.append(self.generateBoxbb)
        text_box_set.addWidget(self.generateBoxbb, alignment=QtCore.Qt.AlignRight)
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
        # self.inEdit = False
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

    def popUp(self, text=None, move=True, flags=None, group_id=None, mode=None, shape=None):
        f = mode == 'cc_rectangle' or mode == 'create_cc_region'
        for item in self.cc_threshold_ui:
            item.setVisible(f)
        f = mode == 'tmp_mode'
        for item in self.text_box_ui:
            item.setVisible(f)
        
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
            
        # initialize sub window
        if mode == 'tmp_mode':
            self.sub_window.initialize(pixmap=self.app.canvas.pixmap, np_image=self.app.np_image, pos=self.pos(), rect=shape)
            self.sub_window.show()
        
        result_text = None
        result_flag = None
        result_groupid = None
        
        if self.exec_():
            result_text = self.edit.text()
            result_flag = self.getFlags()
            result_groupid = self.getGroupId()
            
        if mode == 'tmp_mode':
            self.sub_window.close()
        
        return result_text, result_flag, result_groupid, None
    
    def setTextBoxAttribute(self):
        self.sub_window.generateGrid(int("0" + self.text_cols.text()), int("0" + self.text_rows.text()))
    
    def resetTextBoxAttribute(self):
        self.sub_window.generateGrid(int("0" + self.text_cols.text()), int("0" + self.text_rows.text()), reset=True)
    
    def sl_valuechange(self):
        self.app.canvas.setMinAreaValue(self.sl.value())
        self.slLabel.setText(str(self.sl.value()))
        # self.app.canvas.repaint()
        self.app.paintCanvas()
        # pass

