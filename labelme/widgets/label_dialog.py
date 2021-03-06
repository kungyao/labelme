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
        self.pixmap = None
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
        self.thres = 20

        self.leftBoundary = self.rightBoundary = self.topBoundary = self.bottomBoundary = False

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
        self.prevhShape = self.prevhShapeIndex = None
        self.update()
    
    def clean(self):
        self.pixmap = self.np_image = None
        self.box = None
        
        self.col_lines = []
        self.row_lines = []
        
        self.hShape = self.hType = self.hShapeIndex = None
        self.prevhShape = self.prevhShapeIndex = None
        self.movingShape = False
        
        self.cols = self.rows = 0
        self.pt_size = 1
        
        self.defaultThres = self.thres = 20
        self.update()
    
    def generateGrid(self, cols, rows, reset=False):
        self.selectionChanged.emit([])
        
        if cols == 0 or rows == 0:
            self.col_lines = []
            self.row_lines = []
            return
        if self.cols == cols and self.rows == rows and not reset:
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
        
        # set row
        defaultColGap = 2
        defaultBoxSize = rowStep - defaultColGap
        self.row_lines = []
        # for i in range(rows + 1):
        #     # main line
        #     y = defaultBoxSize * i
        #     self.row_lines.append(createLine(
        #         QPointF(0, y),
        #         QPointF(w, y),
        #         self.pt_scale,
        #         color=(0, 0, 255)
        #     ))
            
        for i in range(rows):
            # main line
            y = defaultBoxSize * i
            self.row_lines.append(createLine(
                QPointF(0, y),
                QPointF(w, y),
                self.pt_scale,
                color=(0, 0, 255)
            ))
            # # constrain line
            y = y + defaultBoxSize
            self.row_lines.append(createLine(
                QPointF(0, y),
                QPointF(w, y),
                self.pt_scale,
                color=(0, 255, 255)
            ))
                
        self.cols = cols
        self.rows = rows
        self.update()
    
    def toShape(self, ifClean=True):
        shapes = []
        if len(self.col_lines) != 0 and len(self.row_lines) != 0:

            def createRectangle(p0, p1):
                shape = Shape()
                shape.shape_type = "rectangle"
                shape.addPoint(p0)
                shape.addPoint(p1)
                shape.close()
                return shape

            offset_x = self.box['xmin']
            offset_y = self.box['ymin']

            # for i in range(0, len(self.row_lines), 2):
            for i in range(0, len(self.row_lines), 2):
                for j in range(0, len(self.col_lines), 2):
                    topLeft = QPointF(
                        self.col_lines[j].points[0].x() + offset_x, 
                        self.row_lines[i].points[0].y() + offset_y
                    )
                    bottomRight = QPointF(
                        self.col_lines[j + 1].points[0].x() + offset_x, 
                        self.row_lines[i + 1].points[0].y() + offset_y
                    )
                    shape = createRectangle(
                        topLeft,
                        bottomRight,
                    )
                    if not shape.isWhiteRect(self.np_image):
                        shapes.append(shape)

        if ifClean:
            self.clean()
        return shapes
    
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
        self.hShape = self.hType = self.hShapeIndex = None
        # select main col line (green)
        if self.leftBoundary:
            for i in range(0, len(self.col_lines), 2):
                line = self.col_lines[i]
                dis = line.distance(pos, self.thres)
                if dis is not None:
                    self.hShape = line
                    self.hType = 'col'
                    self.hShapeIndex = i
                    break
        # select constrain col line (red)
        elif self.rightBoundary:
            for i in range(1, len(self.col_lines), 2):
                line = self.col_lines[i]
                dis = line.distance(pos, self.thres)
                if dis is not None:
                    self.hShape = line
                    self.hType = 'col'
                    self.hShapeIndex = i
                    break
        # select offset line (blue)
        elif self.topBoundary:
            for i in range(0, len(self.row_lines), 2):
                line = self.row_lines[i]
                dis = line.distance(pos, self.thres)
                if dis is not None:
                    self.hShape = line
                    self.hType = 'row'
                    self.hShapeIndex = i
                    break
        # select constrain line (blue)
        elif self.bottomBoundary:
            for i in range(1, len(self.row_lines), 2):
                line = self.row_lines[i]
                dis = line.distance(pos, self.thres)
                if dis is not None:
                    self.hShape = line
                    self.hType = 'row'
                    self.hShapeIndex = i
                    break

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
        if event.button() == QtCore.Qt.RightButton:
            menu = self.menu
            menu.exec_(self.mapToGlobal(event.pos()))
            QtWidgets.QApplication.restoreOverrideCursor()
        if self.movingShape and self.hShape:
            self.movingShape = False
    
    def transformPos(self, point):
        """Convert from widget-logical coordinates to painter-logical ones."""
        return point / self.scale - self.offsetToCenter()

    # move blue line vertically
    def moveRowLine(self, move, shape, index):
        if index%2 == 1:
            shape.moveAllVertexBy(move)
        else:
            shape.moveAllVertexBy(move)
            self.row_lines[index + 1].moveAllVertexBy(move)
        
    def moveColLine(self, move, shape, index):
        if index%2 == 1:
            shape.moveAllVertexBy(move)
        else:
            shape.moveAllVertexBy(move)
            self.col_lines[index + 1].moveAllVertexBy(move)

    def boundedMoveLine(self, pos):
        shape, type, shapeIndex = self.hShape, self.hType, self.hShapeIndex
        point = shape.points[0]
        if shape.shape_type == "line":
            move = pos - point
            if type == 'col':
                move.setY(0.0)
                self.moveColLine(move, shape, shapeIndex)
            elif type == 'row':
                move.setX(0.0)
                self.moveRowLine(move, shape, shapeIndex)

    def selectShapePoint(self, point):
        self.deselectShape()
        # A vertex is marked for selection.
        if self.selectedLine():
            self.prevhShape, self.prevhShapeIndex = self.hShape, self.hShapeIndex
            shape, type, shapeIndex = self.hShape, self.hType, self.hShapeIndex
            shape.selected = True
            if self.leftBoundary:
                self.col_lines[shapeIndex + 1].selected = True
            elif self.rightBoundary:
                self.col_lines[shapeIndex - 1].selected = True
            elif self.topBoundary:
                self.row_lines[shapeIndex + 1].selected = True
            elif self.bottomBoundary:
                self.row_lines[shapeIndex - 1].selected = True
    
    def deselectShape(self):
        if self.prevhShape:
            self.prevhShape.selected = False
            if self.leftBoundary:
                self.col_lines[self.prevhShapeIndex + 1].selected = False
            elif self.rightBoundary:
                self.col_lines[self.prevhShapeIndex - 1].selected = False
            elif self.topBoundary:
                self.row_lines[self.prevhShapeIndex + 1].selected = False
            elif self.bottomBoundary:
                self.row_lines[self.prevhShapeIndex - 1].selected = False
            self.prevhShape = self.prevhShapeIndex = None

    def selectedLine(self):
        return self.hShape is not None
    
    def resizeEvent(self, event):
        ratio_w = event.size().width() / self.box['width']
        ratio_h = event.size().height() / self.box['height']
        self.scale = min(ratio_w, ratio_h)
        # self.thres = self.defaultThres / (self.pt_scale * self.scale)
        self.update()

    def setEditMode(self, left, right, top, bottom):
        self.deselectShape()
        self.leftBoundary = left
        self.rightBoundary = right
        self.topBoundary = top
        self.bottomBoundary = bottom
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
        
        action = functools.partial(labelme.utils.newAction, self)
        # right click menu
        self.menu = QtWidgets.QMenu()
        
        self.leftBoundary = action(
            self.tr('Left Boundary'), 
            lambda: self.toggleEditMode(mode='left'),
            None,
            "objects",
            enabled=False,
        )
        self.rightBoundary = action(
            self.tr('Right Boundary'), 
            lambda: self.toggleEditMode(mode='right'),
            None,
            "objects",
            enabled=False,
        )
        self.topBoundary = action(
            self.tr('Top Boundary'), 
            lambda: self.toggleEditMode(mode='top'),
            None,
            "objects",
            enabled=False,
        )
        self.bottomBoundary = action(
            self.tr('Bottom Boundary'), 
            lambda: self.toggleEditMode(mode='bottom'),
            None,
            "objects",
            enabled=False,
        )
        self.menu.addAction(self.leftBoundary)
        self.menu.addAction(self.rightBoundary)
        self.menu.addAction(self.topBoundary)
        self.menu.addAction(self.bottomBoundary)

        self.setCentralWidget(self.canvas)
        self.canvas.menu = self.menu
        
        self.moveVal = QtCore.QPoint(0, 0)
        
    def initialize(self, pixmap, np_image, pos, rect):
        self.canvas.initialize(pixmap, np_image, pos, rect)
        area = super(SubWindow, self).size()
        aw, ah = area.width(), area.height()
        self.moveVal = pos - QtCore.QPoint(area.width(), 0)
        # self.move(self.moveVal)
        self.toggleEditMode(mode='left')
    def generateGrid(self, cols, rows, reset=False):
        self.canvas.generateGrid(cols, rows, reset)
    def toShape(self, ifClean=True):
        return self.canvas.toShape(ifClean=ifClean)
    def toggleEditMode(self, mode=None):
        left = right = top = bottom = False
        self.leftBoundary.setEnabled(True)
        self.rightBoundary.setEnabled(True)
        self.topBoundary.setEnabled(True)
        self.bottomBoundary.setEnabled(True)
        if mode == 'left':
            left = True
            self.leftBoundary.setEnabled(False)
        elif mode == 'right':
            right = True
            self.rightBoundary.setEnabled(False)
        elif mode == 'top':
            top = True
            self.topBoundary.setEnabled(False)
        elif mode == 'bottom':
            bottom = True
            self.bottomBoundary.setEnabled(False)
        else:
            raise ValueError(f"Unsupported createMode: {mode}")
        # set mode
        self.canvas.setEditMode(left, right, top, bottom)

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
        sub_labels=None,
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
        self.generateBoxbb.button(self.generateBoxbb.Reset).clicked.connect(self.resetTextBoxAttribute)
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
        # sub label list
        self.sub_labelList = QtWidgets.QListWidget()
        if self._fit_to_content["row"]:
            self.sub_labelList.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        if self._fit_to_content["column"]:
            self.sub_labelList.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        if labels:
            self.sub_labelList.addItems(sub_labels)
        self.sub_labelList.setDragDropMode(
            QtWidgets.QAbstractItemView.InternalMove
        )
        self.sub_labelList.currentItemChanged.connect(self.labelSelected)
        # make sure main label has content
        self.sub_labelList.itemDoubleClicked.connect(self.labelDoubleClicked)
        self.edit.setListWidget(self.sub_labelList)
        layout.addWidget(self.sub_labelList)
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
        self.completer = completer
        self.edit.setCompleter(completer)

        # sub completion
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
        completer.setModel(self.sub_labelList.model())
        self.sub_completer = completer
        
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

    def popUp(self, text=None, sub_text=None, move=True, flags=None, group_id=None, mode=None, shape=None, eidtType='Main'):
        f = mode == 'cc_rectangle' or mode == 'create_cc_region' or mode == 'cc_in_rectangle'
        for item in self.cc_threshold_ui:
            item.setVisible(f)
        f = mode == 'text_grid'
        for item in self.text_box_ui:
            item.setVisible(f)

        # if self._fit_to_content["row"]:
        #     self.labelList.setMinimumHeight(
        #         self.labelList.sizeHintForRow(0) * self.labelList.count() + 2
        #     )
        # if self._fit_to_content["column"]:
        #     self.labelList.setMinimumWidth(
        #         self.labelList.sizeHintForColumn(0) + 2
        #     )
        
        if eidtType=='Main':
            self.edit.setCompleter(self.completer)
            self.labelList.setVisible(True)
            self.sub_labelList.setVisible(False)
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
                # self.move(QtGui.QCursor.pos())
                self.move(QtWidgets.QApplication.desktop().screen().rect().center() - self.rect().center())
            # initialize sub window
            if mode == 'text_grid':
                self.sub_window.initialize(pixmap=self.app.canvas.pixmap, np_image=self.app.np_image_b, pos=self.pos(), rect=shape)
                self.sub_window.show()
                self.sub_window.move(self.sub_window.moveVal)
                self.sub_window.update()
        elif eidtType=='Sub':
            self.edit.setCompleter(self.sub_completer)
            self.labelList.setVisible(False)
            self.sub_labelList.setVisible(True)
            # self.sub_labelList.item(0).text()
            if sub_text is None:
                sub_text = ""
            self.edit.setText(sub_text)
            self.edit.setSelection(0, len(sub_text))
            items = self.sub_labelList.findItems(sub_text, QtCore.Qt.MatchFixedString)
            if items:
                if len(items) != 1:
                    logger.warning("Label list has duplicate '{}'".format(sub_text))
                self.sub_labelList.setCurrentItem(items[0])
                row = self.sub_labelList.row(items[0])
                self.edit.completer().setCurrentRow(row)

        result_text = None
        result_flag = None
        result_groupid = None
        
        if self.exec_():
            result_text = self.edit.text()
            result_flag = self.getFlags()
            result_groupid = self.getGroupId()
            
        if mode == 'text_grid':
            self.sub_window.close()
        
        # first is for main mode label
        # second is for sub mode label
        return result_text, result_flag, result_groupid, result_text
    
    def setTextBoxAttribute(self):
        self.sub_window.generateGrid(int("0" + self.text_cols.text()), int("0" + self.text_rows.text()))
    
    def resetTextBoxAttribute(self):
        self.sub_window.generateGrid(int("0" + self.text_cols.text()), int("0" + self.text_rows.text()), reset=True)
    
    def getShape(self):
        return self.sub_window.toShape()
    
    def sl_valuechange(self):
        self.app.canvas.setMinAreaValue(self.sl.value())
        self.slLabel.setText(str(self.sl.value()))
        # self.app.canvas.repaint()
        self.app.paintCanvas()
        # pass

