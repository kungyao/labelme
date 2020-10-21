import os
import cv2
import numpy as np

from ..shape import Shape
from qtpy.QtCore import QPointF

here = os.path.dirname(os.path.abspath(__file__))
# np_image  : input threshold image according to tool mode
# rectangle : QPointF list
# QPointF.x() / QPointF.y()
# return (p1, p2, area)
def connected_component_from_rectangle_region(np_image, rectangle):
    # cv2.imshow(
        # 'abs',
        # np_image[
            # int(rectangle[0].y()) : int(rectangle[1].y()),
            # int(rectangle[0].x()) : int(rectangle[1].x())
        # ]
    # )
    # print(rectangle[0], rectangle[1])
    label = np.zeros(np_image.shape, np_image.dtype)
    # set range of numpy array data
    label[
        min(int(rectangle[0].y()), int(rectangle[1].y())) : max(int(rectangle[0].y()), int(rectangle[1].y())),
        min(int(rectangle[0].x()), int(rectangle[1].x())) : max(int(rectangle[0].x()), int(rectangle[1].x()))
    ] = 255
    
    # 在qimage_to_np_array做了
    # # to binary image
    # _, thresImage = cv2.threshold(np_image, 150, 255, cv2.THRESH_BINARY)
    label = cv2.bitwise_and(np_image, label)
    # # cc找白色區域，所以反白
    # label = cv2.bitwise_not(label)
    # # cv2.imshow('aaa', label)
    
    ccRegion = []
    GLabels, _, GStats, _ = cv2.connectedComponentsWithStats(label)
    for GLabel in range(1, GLabels, 1):
        area = GStats[GLabel, cv2.CC_STAT_AREA]
        # top left
        p1 = [GStats[GLabel, cv2.CC_STAT_LEFT], GStats[GLabel, cv2.CC_STAT_TOP]]
        GObjectW = GStats[GLabel, cv2.CC_STAT_WIDTH]
        GObjectH = GStats[GLabel, cv2.CC_STAT_HEIGHT]
        # right bottom
        p2 = p1.copy()
        p2[0] = p2[0] + GObjectW
        p2[1] = p2[1] + GObjectH
        # to shape
        shape = Shape()
        shape.shape_type = 'rectangle'
        shape.addPoint(QPointF(p1[0], p1[1]))
        shape.addPoint(QPointF(p2[0], p2[1]))
        shape.close()
        # container
        ccRegion.append((shape, area))
    # ccRegion = combine_overlap_rectangle(ccRegion)
    return ccRegion

import torch
from .TextDetection import get_predict_box
model = None
device = torch.device('cuda') if torch.cuda.is_available else torch.device('cpu')
def predict_text_inside_box(np_image, rectangle):
    global model
    global device
    if not model:
        modelPath = os.path.join(here, 'TextDetection/model/m1.pth')
        if not os.path.exists(modelPath):
            return []
        model = torch.load(modelPath, map_location=device)
    xmin = min(int(rectangle[0].x()), int(rectangle[1].x()))
    ymin = min(int(rectangle[0].y()), int(rectangle[1].y()))
    xmax = max(int(rectangle[0].x()), int(rectangle[1].x()))
    ymax = max(int(rectangle[0].y()), int(rectangle[1].y()))
    cropImg = np_image[ymin : ymax, xmin : xmax]
    # xmin, ymin, xmax, ymax, label
    boxes = get_predict_box(model, device, cropImg, threshold=0.95)
    def toShape(box, offset_x, offset_y):
        shape = Shape()
        shape.shape_type = 'rectangle'
        shape.label = box[4]
        shape.flags = None
        shape.group_id = None
        shape.addPoint(QPointF(box[0] + offset_x, box[1] + offset_y))
        shape.addPoint(QPointF(box[2] + offset_x, box[3] + offset_y))
        shape.close()
        return shape
    shapes = []
    for box in boxes:
        shapes.append(toShape(box, xmin, ymin))
    return shapes

    