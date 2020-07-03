import numpy as np
import cv2

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
    label = np.zeros(np_image.shape, np_image.dtype)
    # set range of numpy array data
    label[
        int(rectangle[0].y()) : int(rectangle[1].y()),
        int(rectangle[0].x()) : int(rectangle[1].x())
    ] = 255
    
    label = cv2.bitwise_and(np_image, label)
    # to binary image
    label = cv2.threshold(label, 150, 255, cv2.THRESH_BINARY)
    
    ccRegion = []
    GLabels, _, GStats, _ = cv2.connectedComponentsWithStats(labelX)
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
        # container
        ccRegion.append((p1, p2, area))
    
    return ccRegion