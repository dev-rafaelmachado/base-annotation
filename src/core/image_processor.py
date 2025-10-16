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
        window_w: int,
        window_h: int,
        target_coverage: float = 0.6,
        min_zoom: float = 0.1,
        max_zoom: float = 5.0
    ) -> Tuple[float, int, int]:
        """
        Calcula zoom e pan prontos para o DisplayManager (espaço da imagem original).
        Retorna: (zoom_for_display, pan_x, pan_y)
          - zoom_for_display: fator de zoom a aplicar na imagem original (1.0 = 100%)
          - pan_x/pan_y: topo-esquerdo do crop em pixels no "zoomed original" (para posicionar a janela)
        Parâmetros:
          - display_w/display_h: tamanho *reduzido* de display (retornado por display.get_display_size)
          - window_w/window_h: tamanho real da janela onde é mostrado (DisplayManager.window_width/height)
        """
        # --- obtém bbox absoluto na imagem original ---
        if box['type'] == 'polygon':
            polygon = Polygon(box['coords'])
            x1, y1, x2, y2 = polygon.get_bounding_box(img_width, img_height)
        else:
            bbox = BoundingBox(
                box['x_center'], box['y_center'], box['width'], box['height'])
            x1, y1, x2, y2 = bbox.to_absolute(img_width, img_height)

        bbox_w = max(1.0, float(x2 - x1))
        bbox_h = max(1.0, float(y2 - y1))
        bbox_cx = (x1 + x2) / 2.0
        bbox_cy = (y1 + y2) / 2.0

        # --- escala entre original e display reduzido ---
        # (display_w = img_width * scale)
        scale = float(display_w) / float(img_width) if img_width > 0 else 1.0

        # bbox no espaço reduzido
        scaled_bbox_w = bbox_w * scale
        scaled_bbox_h = bbox_h * scale

        # --- calcula zoom desejado no espaço reduzido ---
        # quanto precisamos aumentar para que bbox ocupe target_coverage do display reduzido
        # proteções contra divisão por zero já garantidas pelos max(1.0, ...)
        zoom_needed_w = (display_w * target_coverage) / scaled_bbox_w
        zoom_needed_h = (display_h * target_coverage) / scaled_bbox_h
        auto_zoom_display = min(zoom_needed_w, zoom_needed_h)

        # --- converte para zoom sobre a imagem original ---
        # se display reduzido foi obtido com scale = display_w/img_w,
        # então o zoom a aplicar na imagem original é:
        zoom_for_display = float(auto_zoom_display) * scale

        # clamp do zoom no espaço DO DISPLAY (aplicado na imagem original)
        zoom_for_display = max(min_zoom, min(max_zoom, zoom_for_display))

        # --- calcula o centro do bbox após aplicar o zoom_for_display (espaço zoomed original) ---
        zoomed_center_x = bbox_cx * zoom_for_display
        zoomed_center_y = bbox_cy * zoom_for_display

        # queremos que esse centro fique no centro da janela final (window_w/2, window_h/2)
        pan_x = int(round(zoomed_center_x - (window_w / 2.0)))
        pan_y = int(round(zoomed_center_y - (window_h / 2.0)))

        # --- limita pan para não extrapolar os limites do "zoomed" da imagem ---
        zoomed_img_w = int(max(1, round(img_width * zoom_for_display)))
        zoomed_img_h = int(max(1, round(img_height * zoom_for_display)))

        max_pan_x = max(0, zoomed_img_w - window_w)
        max_pan_y = max(0, zoomed_img_h - window_h)

        pan_x = max(0, min(pan_x, max_pan_x))
        pan_y = max(0, min(pan_y, max_pan_y))

        return zoom_for_display, pan_x, pan_y
