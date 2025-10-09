"""
Processamento e manipulação de imagens
"""
import cv2
import numpy as np
from typing import Tuple, Dict, Any
from ..config import AnnotationConfig
from ..models import BoundingBox, Polygon


class ImageProcessor:
    """Processa imagens e desenha anotações"""

    def __init__(self, config: AnnotationConfig):
        self.config = config

    def draw_annotation(
        self,
        image: np.ndarray,
        box: Dict[str, Any],
        box_idx: int,
        total_boxes: int
    ) -> np.ndarray:
        """Desenha anotação na imagem"""
        img_display = image.copy()
        img_height, img_width = image.shape[:2]

        if box['type'] == 'polygon':
            self._draw_polygon(img_display, box, img_width, img_height)
        else:
            self._draw_bbox(img_display, box, img_width, img_height)

        # Adiciona informações
        self._draw_info_text(img_display, box, box_idx, total_boxes)

        return img_display

    def _draw_polygon(
        self,
        image: np.ndarray,
        box: Dict[str, Any],
        img_width: int,
        img_height: int
    ):
        """Desenha polígono"""
        polygon = Polygon(box['coords'])
        points = polygon.to_points(img_width, img_height)

        # Preenchimento transparente
        overlay = image.copy()
        cv2.fillPoly(overlay, [points], self.config.fill_color)
        cv2.addWeighted(
            overlay, self.config.polygon_alpha,
            image, 1 - self.config.polygon_alpha,
            0, image
        )

        # Bordas
        cv2.polylines(
            image, [points], True,
            self.config.border_color,
            self.config.border_thickness
        )

    def _draw_bbox(
        self,
        image: np.ndarray,
        box: Dict[str, Any],
        img_width: int,
        img_height: int
    ):
        """Desenha bounding box retangular"""
        bbox = BoundingBox(
            box['x_center'], box['y_center'],
            box['width'], box['height']
        )
        x1, y1, x2, y2 = bbox.to_absolute(img_width, img_height)

        cv2.rectangle(
            image, (x1, y1), (x2, y2),
            self.config.border_color,
            self.config.border_thickness
        )

    def _draw_info_text(
        self,
        image: np.ndarray,
        box: Dict[str, Any],
        box_idx: int,
        total_boxes: int
    ):
        """Desenha texto informativo"""
        info_text = f"Box {box_idx+1}/{total_boxes} - {box['class_name']}"

        # Fundo preto
        text_size = cv2.getTextSize(
            info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
        )[0]
        cv2.rectangle(
            image, (5, 5),
            (text_size[0] + 15, 35),
            (0, 0, 0), -1
        )

        # Texto verde
        cv2.putText(
            image, info_text, (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
            self.config.border_color, 2, cv2.LINE_AA
        )

    def calculate_auto_zoom(
        self,
        box: Dict[str, Any],
        img_width: int,
        img_height: int,
        display_w: int,
        display_h: int,
        target_coverage: float = 0.6
    ) -> Tuple[float, int, int]:
        """Calcula zoom e pan automáticos"""
        # Obtém bounding box da região
        if box['type'] == 'polygon':
            polygon = Polygon(box['coords'])
            bbox_x1, bbox_y1, bbox_x2, bbox_y2 = polygon.get_bounding_box(
                img_width, img_height
            )
        else:
            bbox = BoundingBox(
                box['x_center'], box['y_center'],
                box['width'], box['height']
            )
            bbox_x1, bbox_y1, bbox_x2, bbox_y2 = bbox.to_absolute(
                img_width, img_height
            )

        bbox_w = bbox_x2 - bbox_x1
        bbox_h = bbox_y2 - bbox_y1
        center_x = (bbox_x1 + bbox_x2) / 2
        center_y = (bbox_y1 + bbox_y2) / 2

        # Escala para display
        scale = min(display_w / img_width, display_h / img_height)
        scaled_bbox_w = bbox_w * scale
        scaled_bbox_h = bbox_h * scale
        scaled_center_x = center_x * scale
        scaled_center_y = center_y * scale

        # Calcula zoom ideal
        zoom_w = (display_w * target_coverage) / scaled_bbox_w
        zoom_h = (display_h * target_coverage) / scaled_bbox_h
        auto_zoom = min(zoom_w, zoom_h)
        auto_zoom = max(1.0, min(5.0, auto_zoom))

        # Calcula pan para CENTRALIZAR a região
        # Após aplicar zoom, a posição do centro da região muda
        zoomed_center_x = scaled_center_x * auto_zoom
        zoomed_center_y = scaled_center_y * auto_zoom

        # Pan necessário para colocar o centro da região no centro da tela
        auto_pan_x = int(zoomed_center_x - (display_w / 2))
        auto_pan_y = int(zoomed_center_y - (display_h / 2))

        # Garante que pan está dentro dos limites
        zoomed_w = int(display_w * auto_zoom)
        zoomed_h = int(display_h * auto_zoom)

        auto_pan_x = max(0, min(auto_pan_x, max(0, zoomed_w - display_w)))
        auto_pan_y = max(0, min(auto_pan_y, max(0, zoomed_h - display_h)))

        return auto_zoom, auto_pan_x, auto_pan_y
