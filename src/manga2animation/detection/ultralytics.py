"""Kết nối với model Ultralytics; tách thư viện model khỏi phần xử lý bố cục."""
from ..layout.geometry import area, pad_bbox


class UltralyticsDetector:
    def __init__(self, model, confidence=.25, device='cpu', panel_class=0, text_class=1,
                 text_confidence=None, text_padding=.1):
        from ultralytics import YOLO
        self.model = YOLO(model)
        self.confidence = confidence
        self.device = device
        self.panel_class = panel_class
        self.text_class = text_class
        self.text_confidence = confidence if text_confidence is None else text_confidence
        self.text_padding = text_padding

    def detect(self, image):
        # Lấy vùng chữ ở ngưỡng thấp hơn, sau đó lọc riêng theo từng loại vùng.
        prediction = self.model.predict(image, conf=min(self.confidence, self.text_confidence),
                                        device=self.device, verbose=False)[0]
        panels, texts = [], []
        for box in prediction.boxes:
            cls = int(box.cls.item())
            bbox = [round(v) for v in box.xyxy[0].tolist()]
            bbox = [max(0, min(v, image.width if i % 2 == 0 else image.height))
                    for i, v in enumerate(bbox)]
            if not area(bbox):
                continue
            item = {'bbox': bbox, 'confidence': float(box.conf.item())}
            if cls == self.panel_class and item['confidence'] >= self.confidence:
                panels.append(item)
            elif cls == self.text_class and item['confidence'] >= self.text_confidence:
                # Giữ vùng detect gốc để đối chiếu; vùng nới rộng được dùng khi crop và OCR.
                item['bbox_detected'] = bbox[:]
                item['bbox'] = pad_bbox(bbox, image.size, self.text_padding)
                texts.append(item)
        return panels, texts
