# detector.py

import cv2

class PersonDetector:
    """
    Handles person detection using a pre-trained MobileNet SSD model.
    """

    def __init__(self, prototxt_path, model_path):
        self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        self.class_id_person = 15  # Class ID for 'person' in MobileNet SSD

    def detect(self, frame):
        """
        Detects persons in the frame.
        Returns a list of bounding boxes for detected persons.
        """
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
                                     0.007843, (300, 300), 127.5)
        self.net.setInput(blob)
        detections = self.net.forward()
        boxes = []

        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                class_id = int(detections[0, 0, i, 1])
                if class_id == self.class_id_person:
                    box = detections[0, 0, i, 3:7] * [w, h, w, h]
                    boxes.append(box.astype(int))
        return boxes
