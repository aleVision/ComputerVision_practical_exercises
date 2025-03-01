import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QToolBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QSizeF, QLineF
from PyQt6.QtGui import QMouseEvent, QTransform, QPainter, QPen, QColor, QAction, QPolygonF

class TransformableRectItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        # Enable selection, moving, and geometry change notifications.
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.handle_size = 8.0
        self.handles = []  # List of (handle_name, QRectF) tuples.
        self.handle_selected = None
        # Default transformation mode (can be updated by MainWindow).
        self.transform_mode = 'translation'
        # Save the original geometry for computing affine/perspective transforms.
        self.original_rect = rect
        self.original_corners = [rect.topLeft(), rect.topRight(),
                                 rect.bottomRight(), rect.bottomLeft()]

    def update_handles(self):
        s = self.handle_size
        rect = self.rect()
        self.handles = []
        # In scaling, affine, or perspective modes, show the four corner handles.
        if self.transform_mode in ['scaling', 'affine', 'perspective']:
            self.handles.extend([
                ('top_left', QRectF(rect.topLeft() - QPointF(s/2, s/2), QSizeF(s, s))),
                ('top_right', QRectF(rect.topRight() - QPointF(s/2, s/2), QSizeF(s, s))),
                ('bottom_left', QRectF(rect.bottomLeft() - QPointF(s/2, s/2), QSizeF(s, s))),
                ('bottom_right', QRectF(rect.bottomRight() - QPointF(s/2, s/2), QSizeF(s, s)))
            ])
        # In rotation mode, add a dedicated rotation handle above the rectangle.
        if self.transform_mode == 'rotation':
            center_top = QPointF((rect.topLeft().x() + rect.topRight().x())/2, rect.top() - 20)
            self.handles.append(('rotate', QRectF(center_top - QPointF(s/2, s/2), QSizeF(s, s))))

    def hoverMoveEvent(self, event):
        # Change the mouse cursor if over a handle.
        cursor = Qt.CursorShape.ArrowCursor
        if self.isSelected():
            pos = event.pos()
            for handle, rect in self.handles:
                if rect.contains(pos):
                    cursor = Qt.CursorShape.CrossCursor if handle == 'rotate' else Qt.CursorShape.SizeFDiagCursor
                    break
        self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self.isSelected():
            pos = event.pos()
            self.handle_selected = None
            for handle, rect in self.handles:
                if rect.contains(pos):
                    self.handle_selected = handle
                    break
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.handle_selected:
            if self.transform_mode == 'scaling':
                self.resize_item(event.pos())
            elif self.transform_mode == 'rotation':
                self.rotate_item(event.pos())
            elif self.transform_mode in ['affine', 'perspective']:
                self.affine_transform_item(event.pos())
            else:
                super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.handle_selected = None
        super().mouseReleaseEvent(event)
        # Update the original geometry after transformation.
        self.original_rect = self.rect()
        self.original_corners = [self.rect().topLeft(), self.rect().topRight(),
                                 self.rect().bottomRight(), self.rect().bottomLeft()]

    def resize_item(self, pos):
        # Update the rectangle's geometry when a corner is dragged.
        rect = self.rect()
        if self.handle_selected == 'top_left':
            rect.setTopLeft(pos)
        elif self.handle_selected == 'top_right':
            rect.setTopRight(pos)
        elif self.handle_selected == 'bottom_left':
            rect.setBottomLeft(pos)
        elif self.handle_selected == 'bottom_right':
            rect.setBottomRight(pos)
        self.setRect(rect)
        self.update_handles()

    def rotate_item(self, pos):
        # Compute the angle between the center and the current mouse position.
        center = self.rect().center()
        line = QLineF(center, pos)
        angle = line.angle()  # Angle in degrees relative to horizontal.
        # Set the rotation (the negative sign adjusts for coordinate differences).
        self.setRotation(-angle)

    def affine_transform_item(self, pos):
        # Compute a new transformation by moving one corner.
        index_map = {'top_left': 0, 'top_right': 1, 'bottom_right': 2, 'bottom_left': 3}
        if self.handle_selected in index_map:
            new_corners = list(self.original_corners)  # Copy the original corner positions.
            new_corners[index_map[self.handle_selected]] = pos
            src_poly = QPolygonF(self.original_corners)
            dst_poly = QPolygonF(new_corners)
            ok, t = QTransform.quadToQuad(src_poly, dst_poly)
            if ok:
                self.setTransform(t)
        # (The same code applies for both affine and perspective modes.)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            self.update_handles()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(Qt.GlobalColor.green, 1.0, Qt.PenStyle.DashLine))
            for _, rect in self.handles:
                painter.drawRect(rect)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2D Transform Editor")
        self.setGeometry(100, 100, 800, 600)
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene, self)
        self.setCentralWidget(self.view)
        self.current_rect = None
        self.drawing = False
        self.transform_mode = 'translation'
        self.init_ui()

    def init_ui(self):
        toolbar = QToolBar("Transformation Modes", self)
        self.addToolBar(toolbar)

        translation_action = QAction("Translation", self)
        translation_action.triggered.connect(lambda: self.set_transform_mode('translation'))
        toolbar.addAction(translation_action)

        rotation_action = QAction("Rotation", self)
        rotation_action.triggered.connect(lambda: self.set_transform_mode('rotation'))
        toolbar.addAction(rotation_action)

        scaling_action = QAction("Scaling", self)
        scaling_action.triggered.connect(lambda: self.set_transform_mode('scaling'))
        toolbar.addAction(scaling_action)

        affine_action = QAction("Affine", self)
        affine_action.triggered.connect(lambda: self.set_transform_mode('affine'))
        toolbar.addAction(affine_action)

        perspective_action = QAction("Perspective", self)
        perspective_action.triggered.connect(lambda: self.set_transform_mode('perspective'))
        toolbar.addAction(perspective_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_rectangles)
        toolbar.addAction(save_action)

        load_action = QAction("Load", self)
        load_action.triggered.connect(self.load_rectangles)
        toolbar.addAction(load_action)

    def set_transform_mode(self, mode):
        self.transform_mode = mode
        # Update transformation mode for all items in the scene.
        for item in self.scene.items():
            if isinstance(item, TransformableRectItem):
                item.transform_mode = mode
                item.update_handles()

    def item_at(self, event):
        # Helper: return the top-most item at the event position.
        pos = self.view.mapToScene(event.position().toPoint())
        items = self.scene.items(pos)
        return items[0] if items else None

    def mousePressEvent(self, event: QMouseEvent):
        # Create a new rectangle only if not clicking on an existing item.
        item = self.item_at(event)
        if not item and event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = self.view.mapToScene(event.position().toPoint())
            self.current_rect = TransformableRectItem(QRectF(self.start_pos, self.start_pos))
            self.current_rect.transform_mode = self.transform_mode
            self.scene.addItem(self.current_rect)
            self.drawing = True
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing and self.current_rect:
            current_pos = self.view.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_pos, current_pos).normalized()
            self.current_rect.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            if self.current_rect:
                self.current_rect.update_handles()
                self.current_rect.setSelected(True)
                # Update original geometry for future affine transformations.
                self.current_rect.original_rect = self.current_rect.rect()
                self.current_rect.original_corners = [self.current_rect.rect().topLeft(),
                                                      self.current_rect.rect().topRight(),
                                                      self.current_rect.rect().bottomRight(),
                                                      self.current_rect.rect().bottomLeft()]
                self.current_rect = None
        else:
            super().mouseReleaseEvent(event)

    def save_rectangles(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Rectangles", "", "JSON Files (*.json)")
        if filename:
            try:
                rects = []
                for item in self.scene.items():
                    if isinstance(item, TransformableRectItem):
                        rect = item.rect()
                        transform = item.transform()
                        rects.append({
                            'x': rect.x(),
                            'y': rect.y(),
                            'width': rect.width(),
                            'height': rect.height(),
                            'transform': {
                                'm11': transform.m11(),
                                'm12': transform.m12(),
                                'm13': transform.m13(),
                                'm21': transform.m21(),
                                'm22': transform.m22(),
                                'm23': transform.m23(),
                                'm31': transform.m31(),
                                'm32': transform.m32(),
                                'm33': transform.m33(),
                            }
                        })
                with open(filename, 'w') as file:
                    json.dump(rects, file, indent=4)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save rectangles: {e}")

    def load_rectangles(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Rectangles", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r') as file:
                    rects = json.load(file)
                    self.scene.clear()
                    for rect_data in rects:
                        rect = QRectF(rect_data['x'], rect_data['y'], rect_data['width'], rect_data['height'])
                        item = TransformableRectItem(rect)
                        transform_data = rect_data['transform']
                        transform = QTransform(
                            transform_data['m11'], transform_data['m12'], transform_data['m13'],
                            transform_data['m21'], transform_data['m22'], transform_data['m23'],
                            transform_data['m31'], transform_data['m32'], transform_data['m33']
                        )
                        item.setTransform(transform)
                        item.transform_mode = self.transform_mode
                        item.update_handles()
                        self.scene.addItem(item)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load rectangles: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
