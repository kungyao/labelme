import numpy as np
import cv2

from ..shape import Shape
from qtpy.QtCore import QPointF

# rectangle 1
# r1a top left
# r1b bottom right
# rectangle 2
# r2a top left
# r2b bottom right
def isRectangleOverlap(r1a, r1b, r2a, r2b):
    # if one rectangle is on left side of other 
    if (r1a[0] >= r2b[0] || r2a[0] >= r1b[0])
        return False; 
    # if one rectangle is above other 
    if (r1a[1] >= r2b[1] || r2a[1] >= r1b[1])
        return False; 
    return True; 

# def combine_overlap_rectangle(ccRegion):
    # newCCRegion = []
    # beOverlappedIndex = []
    
    # size = len(ccRegion)
    # for i in range(0, size):
        # if i in beOverlappedIndex:
            # continue
        # r1 = ccRegion[i]
        # for j in enumerate(i + 1, size):
            # if j in beOverlappedIndex:
                # continue
            # r2 = ccRegion[j]
            # if isRectangleOverlap(r1, r2)
                # newP1 = [min(r1[0][0], r2[0][0]), min(r1[0][1], r2[0][1])]
                # newP2 = [max(r1[1][0], r2[1][0]), max(r1[1][1], r2[1][1])]
                # newArea = (newP2[0] - newP1[0]) * (newP2[1] - newP1[1])
                # r1 = (
                    # newP1,
                    # newP2,
                    # newArea
                # )
                # beOverlappedItem.append(j)
        # newCCRegion.append(r1.copy())
    # return newCCRegion

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
        int(rectangle[0].y()) : int(rectangle[1].y()),
        int(rectangle[0].x()) : int(rectangle[1].x())
    ] = 255
    
    # 在qimage_to_np_array做了
    # # to binary image
    # _, thresImage = cv2.threshold(np_image, 150, 255, cv2.THRESH_BINARY)
    label = cv2.bitwise_and(np_image, label)
    # cc找白色區域，所以反白
    label = cv2.bitwise_not(label)
    # cv2.imshow('aaa', label)
    
    ccRegion = []
    GLabels, _, GStats, _ = cv2.connectedComponentsWithStats(label)
    # 從2開始，因為好像會找到最外框
    for GLabel in range(2, GLabels, 1):
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