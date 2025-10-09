"""
Gerenciamento de display visual
"""
import cv2
import numpy as np
import threading
import time
from typing import Optional, Tuple
from ..config import DisplayConfig, ZoomConfig


class DisplayManager:
    """Gerencia visualização com zoom e pan"""

    def __init__(self, display_config: DisplayConfig, zoom_config: ZoomConfig):
        self.display_config = display_config
        self.zoom_config = zoom_config

        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0

        self.current_image: Optional[np.ndarray] = None
        self.should_update = False
        self.stop_flag = False
        self.thread: Optional[threading.Thread] = None

        self.window_name = "Imagem Completa"

    def start(self):
        """Inicia thread de visualização"""
        self.stop_flag = False
        self.thread = threading.Thread(target=self._display_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Para thread de visualização"""
        self.stop_flag = True
        if self.thread:
            self.thread.join(timeout=1)
        cv2.destroyAllWindows()

    def update_image(self, image: np.ndarray):
        """Atualiza imagem sendo exibida"""
        self.current_image = image
        self.should_update = True

    def set_zoom_pan(self, zoom: float, pan_x: int, pan_y: int):
        """Define zoom e pan"""
        self.zoom_level = zoom
        self.pan_x = pan_x
        self.pan_y = pan_y
        self.should_update = True

    def get_display_size(self, img_width: int, img_height: int) -> Tuple[int, int]:
        """Calcula tamanho de display para uma imagem"""
        scale = min(
            self.display_config.max_width / img_width,
            self.display_config.max_height / img_height,
            1.0
        )

        if scale < 0.5:
            scale = 1.0
        if img_width < self.display_config.min_width or img_height < self.display_config.min_height:
            scale = max(
                self.display_config.min_width / img_width,
                self.display_config.min_height / img_height
            )

        return int(img_width * scale), int(img_height * scale)

    def _display_loop(self):
        """Loop principal de visualização"""
        while not self.stop_flag:
            if self.should_update and self.current_image is not None:
                self._render()

            # Processa teclas
            key = cv2.waitKey(50) & 0xFF
            if key != 255:
                self._handle_key(key)

            time.sleep(0.01)

    def _render(self):
        """Renderiza imagem com zoom e pan"""
        h, w = self.current_image.shape[:2]

        # Redimensiona para display
        display_w, display_h = self.get_display_size(w, h)
        base_image = cv2.resize(
            self.current_image, (display_w, display_h),
            interpolation=cv2.INTER_CUBIC if display_w > w else cv2.INTER_AREA
        )

        # Aplica zoom e pan
        display_image = self._apply_zoom_pan(base_image)

        # Adiciona instruções
        self._draw_instructions(display_image)

        cv2.imshow(self.window_name, display_image)

    def _apply_zoom_pan(self, image: np.ndarray) -> np.ndarray:
        """Aplica zoom e pan"""
        h, w = image.shape[:2]

        if self.zoom_level != 1.0:
            new_w = int(w * self.zoom_level)
            new_h = int(h * self.zoom_level)
            zoomed = cv2.resize(image, (new_w, new_h),
                                interpolation=cv2.INTER_LINEAR)
        else:
            zoomed = image

        zh, zw = zoomed.shape[:2]

        # Calcula região visível
        x1 = max(0, min(self.pan_x, zw - w))
        y1 = max(0, min(self.pan_y, zh - h))
        x2 = min(zw, x1 + w)
        y2 = min(zh, y1 + h)

        visible = zoomed[y1:y2, x1:x2]

        # Preenche se necessário
        if visible.shape[0] < h or visible.shape[1] < w:
            canvas = np.zeros((h, w, 3), dtype=np.uint8)
            canvas[:visible.shape[0], :visible.shape[1]] = visible
            return canvas

        return visible

    def _draw_instructions(self, image: np.ndarray):
        """Desenha instruções na imagem"""
        instructions = [
            "ZOOM: [ Q ] aumentar | [ E ] diminuir | [ R ] resetar",
            "MOVER: [ W ] cima | [ S ] baixo | [ A ] esq | [ D ] dir",
            f"Zoom: {self.zoom_level:.1f}x"
        ]

        h = image.shape[0]
        for i, text in enumerate(instructions):
            y_pos = h - 60 + i * 20
            cv2.putText(
                image, text, (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA
            )

    def _handle_key(self, key: int):
        """Processa teclas"""
        changed = False

        # Zoom
        if key in [ord('q'), ord('Q')]:
            self.zoom_level = min(
                self.zoom_level + self.zoom_config.zoom_step, self.zoom_config.max_zoom)
            changed = True
        elif key in [ord('e'), ord('E')]:
            self.zoom_level = max(
                self.zoom_level - self.zoom_config.zoom_step, self.zoom_config.min_zoom)
            changed = True
        elif key in [ord('r'), ord('R')]:
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0
            changed = True

        # Pan
        elif key in [ord('w'), ord('W')]:
            self.pan_y = max(0, self.pan_y - self.zoom_config.pan_step)
            changed = True
        elif key in [ord('s'), ord('S')]:
            self.pan_y += self.zoom_config.pan_step
            changed = True
        elif key in [ord('a'), ord('A')]:
            self.pan_x = max(0, self.pan_x - self.zoom_config.pan_step)
            changed = True
        elif key in [ord('d'), ord('D')]:
            self.pan_x += self.zoom_config.pan_step
            changed = True

        if changed:
            self.should_update = True
