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

        # Controles de brilho e contraste
        self.brightness = display_config.default_brightness
        self.contrast = display_config.default_contrast

        # Controle de rotação
        self.rotation = display_config.default_rotation

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
        # Reseta brilho, contraste e rotação ao mudar de imagem
        self.brightness = self.display_config.default_brightness
        self.contrast = self.display_config.default_contrast
        self.rotation = self.display_config.default_rotation
        self.should_update = True

    def get_display_size(self, img_width: int, img_height: int) -> Tuple[int, int]:
        """
        Calcula tamanho de display para uma imagem com redimensionamento inteligente
        Suporta imagens de qualquer tamanho incluindo 4K/8K
        """
        # Primeiro redimensiona imagens muito grandes para tamanho gerenciável
        if img_width > self.display_config.max_source_width or img_height > self.display_config.max_source_height:
            source_scale = min(
                self.display_config.max_source_width / img_width,
                self.display_config.max_source_height / img_height
            )
            img_width = int(img_width * source_scale)
            img_height = int(img_height * source_scale)

        # Agora calcula escala para caber na tela
        scale = min(
            self.display_config.max_width / img_width,
            self.display_config.max_height / img_height
        )

        # Garante que sempre redimensiona imagens grandes
        if scale > 1.0:
            scale = 1.0

        # Para imagens muito pequenas, aumenta
        if img_width < self.display_config.min_width or img_height < self.display_config.min_height:
            scale = max(
                self.display_config.min_width / img_width,
                self.display_config.min_height / img_height
            )

        final_width = int(img_width * scale)
        final_height = int(img_height * scale)

        # Garante que não ultrapassa limites da tela
        final_width = min(final_width, self.display_config.max_width)
        final_height = min(final_height, self.display_config.max_height)

        return final_width, final_height

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

        # Redimensiona para display com interpolação apropriada
        display_w, display_h = self.get_display_size(w, h)

        # Escolhe interpolação baseado na escala
        scale = display_w / w
        if scale > 1.0:
            # Aumentando - usa CUBIC para suavizar
            interpolation = cv2.INTER_CUBIC
        elif scale > 0.5:
            # Reduzindo até 50% - usa AREA para melhor qualidade
            interpolation = cv2.INTER_AREA
        else:
            # Reduzindo mais de 50% - usa LINEAR para performance
            interpolation = cv2.INTER_LINEAR

        base_image = cv2.resize(
            self.current_image, (display_w, display_h),
            interpolation=interpolation
        )

        # Aplica rotação
        base_image = self._apply_rotation(base_image)

        # Aplica brilho e contraste
        base_image = self._apply_brightness_contrast(base_image)

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

    def _apply_brightness_contrast(self, image: np.ndarray) -> np.ndarray:
        """Aplica ajustes de brilho e contraste"""
        if self.brightness == 0 and self.contrast == 1.0:
            return image

        # Aplica transformação: output = contrast * input + brightness
        adjusted = cv2.convertScaleAbs(
            image, alpha=self.contrast, beta=self.brightness)
        return adjusted

    def _apply_rotation(self, image: np.ndarray) -> np.ndarray:
        """Aplica rotação na imagem"""
        if self.rotation == 0:
            return image

        h, w = image.shape[:2]
        center = (w // 2, h // 2)

        # Matriz de rotação
        matrix = cv2.getRotationMatrix2D(center, self.rotation, 1.0)

        # Calcula novos limites da imagem rotacionada
        cos = abs(matrix[0, 0])
        sin = abs(matrix[0, 1])

        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        # Ajusta a matriz de translação
        matrix[0, 2] += (new_w / 2) - center[0]
        matrix[1, 2] += (new_h / 2) - center[1]

        # Aplica rotação
        rotated = cv2.warpAffine(
            image, matrix, (new_w, new_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )

        return rotated

    def _draw_instructions(self, image: np.ndarray):
        """Desenha instruções na imagem"""
        instructions = [
            "ZOOM: [ Q ] + | [ E ] - | [ R ] reset",
            "MOVE: [ W ] [ S ] [ A ] [ D ]",
            f"BRILHO: [ B ] + | [ V ] - | Atual: {self.brightness:+.0f}",
            f"CONTRASTE: [ C ] + | [ X ] - | Atual: {self.contrast:.2f}",
            f"ROTACAO: [ N ] ← | [ M ] → | [ T ] reset | Atual: {self.rotation:.0f}°",
            f"Zoom: {self.zoom_level:.1f}x"
        ]

        h = image.shape[0]
        for i, text in enumerate(instructions):
            y_pos = h - 120 + i * 20
            cv2.putText(
                image, text, (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA
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
            self.brightness = self.display_config.default_brightness
            self.contrast = self.display_config.default_contrast
            # Não reseta rotação aqui - tem tecla T específica
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

        # Brilho
        elif key in [ord('b'), ord('B')]:
            self.brightness = min(
                self.brightness + self.display_config.brightness_step, 100)
            changed = True
        elif key in [ord('v'), ord('V')]:
            self.brightness = max(
                self.brightness - self.display_config.brightness_step, -100)
            changed = True

        # Contraste
        elif key in [ord('c'), ord('C')]:
            self.contrast = min(
                self.contrast + self.display_config.contrast_step, 3.0)
            changed = True
        elif key in [ord('x'), ord('X')]:
            self.contrast = max(
                self.contrast - self.display_config.contrast_step, 0.1)
            changed = True

        # Rotação
        elif key in [ord('n'), ord('N')]:  # Rotaciona para esquerda (sentido anti-horário)
            self.rotation = (
                self.rotation + self.display_config.rotation_step) % 360
            changed = True
        elif key in [ord('m'), ord('M')]:  # Rotaciona para direita (sentido horário)
            self.rotation = (
                self.rotation - self.display_config.rotation_step) % 360
            changed = True
        elif key in [ord('t'), ord('T')]:  # Reset rotação
            self.rotation = self.display_config.default_rotation
            changed = True

        if changed:
            self.should_update = True
