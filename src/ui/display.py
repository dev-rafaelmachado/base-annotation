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

        # Zoom inicial neutro (1.0 = 100%)
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0

        # Não há mínimo forçado; permitir zoom livre.
        # Se quiser um limite baixo seguro, ajuste aqui (e/ou em zoom_config.min_zoom).
        self.MIN_ZOOM_FOR_SAFETY = 0.01

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

        # Tamanho fixo da janela
        self.window_width = 640
        self.window_height = 640

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

    def update_image(self, image: np.ndarray, applyAutoCenter: bool = True):
        """Atualiza imagem sendo exibida.

        - Se applyAutoCenter for True (padrão), centraliza o bbox na janela
          usando o zoom atual (não altera self.zoom_level).
        - Se False, apenas atualiza a imagem e respeita zoom/pan já definidos
          (usado quando você chama set_zoom_pan antes de update_image).
        """
        self.current_image = image
        self.should_update = True

        if not applyAutoCenter:
            return

        # Detecta bbox
        bbox = self._detect_content_bbox_robust(image)
        img_h, img_w = image.shape[:2]

        center_x = self.window_width / 2.0
        center_y = self.window_height / 2.0

        if bbox is not None:
            x1, y1, x2, y2 = bbox

            # Centro do bbox NA IMAGEM ORIGINAL (sem zoom)
            bbox_center_x = (x1 + x2) / 2.0
            bbox_center_y = (y1 + y2) / 2.0

            # Posição do centro do bbox após aplicar o zoom atual
            zoomed_bbox_center_x = bbox_center_x * self.zoom_level
            zoomed_bbox_center_y = bbox_center_y * self.zoom_level

            # Para centralizar esse ponto na janela (usando coordenadas do zoomed image)
            pan_x = int(round(zoomed_bbox_center_x - center_x))
            pan_y = int(round(zoomed_bbox_center_y - center_y))

            # Garante que pan não seja negativo
            pan_x = max(0, pan_x)
            pan_y = max(0, pan_y)

            # Limita pan para não ultrapassar os limites da imagem com zoom
            zoomed_img_w = int(img_w * self.zoom_level)
            zoomed_img_h = int(img_h * self.zoom_level)

            max_pan_x = max(0, zoomed_img_w - self.window_width)
            max_pan_y = max(0, zoomed_img_h - self.window_height)

            self.pan_x = min(pan_x, max_pan_x)
            self.pan_y = min(pan_y, max_pan_y)
        else:
            # Sem bbox: centraliza a imagem inteira mantendo o zoom atual
            zoomed_img_w = int(img_w * self.zoom_level)
            zoomed_img_h = int(img_h * self.zoom_level)

            self.pan_x = max(0, (zoomed_img_w - self.window_width) // 2)
            self.pan_y = max(0, (zoomed_img_h - self.window_height) // 2)

    def _detect_content_bbox_robust(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detecção robusta de bounding box com múltiplas estratégias
        SEMPRE retorna um bbox válido se houver qualquer conteúdo
        """
        h, w = image.shape[:2]

        # Estratégia 1: Detecção por threshold baixo (conteúdo escuro)
        bbox = self._detect_bbox_threshold(image, threshold=15)
        if bbox and self._is_valid_bbox(bbox, w, h):
            return bbox

        # Estratégia 2: Threshold mais alto (conteúdo claro)
        bbox = self._detect_bbox_threshold(image, threshold=30)
        if bbox and self._is_valid_bbox(bbox, w, h):
            return bbox

        # Estratégia 3: Detecção por bordas (Canny)
        bbox = self._detect_bbox_edges(image)
        if bbox and self._is_valid_bbox(bbox, w, h):
            return bbox

        # Estratégia 4: Análise de variância (detecta regiões com conteúdo)
        bbox = self._detect_bbox_variance(image)
        if bbox and self._is_valid_bbox(bbox, w, h):
            return bbox

        # Se nada funcionar, retorna None (usará imagem completa)
        return None

    def _detect_bbox_threshold(self, image: np.ndarray, threshold: int) -> Optional[Tuple[int, int, int, int]]:
        """Detecta bbox usando threshold simples"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)

        # Encontra pixels não-zero
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return None

        # Bounding box dos pixels não-zero
        x, y, bw, bh = cv2.boundingRect(coords)

        # Adiciona margem de 2%
        h, w = image.shape[:2]
        margin_x = max(5, int(bw * 0.02))
        margin_y = max(5, int(bh * 0.02))

        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w, x + bw + margin_x)
        y2 = min(h, y + bh + margin_y)

        return (x1, y1, x2, y2)

    def _detect_bbox_edges(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detecta bbox usando detecção de bordas"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Canny edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Dilata para conectar bordas próximas
        kernel = np.ones((5, 5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)

        coords = cv2.findNonZero(edges)
        if coords is None:
            return None

        x, y, bw, bh = cv2.boundingRect(coords)

        h, w = image.shape[:2]
        margin_x = max(10, int(bw * 0.03))
        margin_y = max(10, int(bh * 0.03))

        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w, x + bw + margin_x)
        y2 = min(h, y + bh + margin_y)

        return (x1, y1, x2, y2)

    def _detect_bbox_variance(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detecta bbox analisando variância local (áreas com conteúdo têm alta variância)"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        h, w = gray.shape

        # Calcula variância local usando filtro
        mean = cv2.blur(gray, (15, 15))
        sqr_mean = cv2.blur(gray ** 2, (15, 15))
        variance = sqr_mean - mean ** 2

        # Threshold na variância
        _, var_thresh = cv2.threshold(variance.astype(
            np.uint8), 10, 255, cv2.THRESH_BINARY)

        coords = cv2.findNonZero(var_thresh)
        if coords is None:
            return None

        x, y, bw, bh = cv2.boundingRect(coords)

        margin_x = max(10, int(bw * 0.02))
        margin_y = max(10, int(bh * 0.02))

        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w, x + bw + margin_x)
        y2 = min(h, y + bh + margin_y)

        return (x1, y1, x2, y2)

    def _is_valid_bbox(self, bbox: Tuple[int, int, int, int], img_w: int, img_h: int) -> bool:
        """Valida se bbox é útil (não é a imagem inteira e não é muito pequeno)"""
        x1, y1, x2, y2 = bbox
        bbox_w = x2 - x1
        bbox_h = y2 - y1
        bbox_area = bbox_w * bbox_h
        image_area = img_w * img_h

        # Rejeita se for mais de 95% da imagem (não há bordas significativas)
        if bbox_area > image_area * 0.95:
            return False

        # Rejeita se for menos de 1% da imagem (muito pequeno, provavelmente ruído)
        if bbox_area < image_area * 0.01:
            return False

        # Rejeita se bbox for muito pequeno em pixels absolutos
        if bbox_w < 50 or bbox_h < 50:
            return False

        return True

    def _detect_content_bbox(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Método legado - agora usa detecção robusta"""
        return self._detect_content_bbox_robust(image)

    def set_zoom_pan(self, zoom: float, pan_x: int, pan_y: int):
        """Define zoom e pan (permite qualquer zoom)"""
        # segurança: evitar zoom <= 0
        zoom = max(self.MIN_ZOOM_FOR_SAFETY, float(zoom))
        # respeitar limite superior se houver
        if hasattr(self.zoom_config, "max_zoom") and self.zoom_config.max_zoom:
            zoom = min(zoom, self.zoom_config.max_zoom)
        self.zoom_level = zoom
        self.pan_x = int(max(0, pan_x))
        self.pan_y = int(max(0, pan_y))

        # reset minimal de ajustes visuais para estado padrão
        self.brightness = self.display_config.default_brightness
        self.contrast = self.display_config.default_contrast
        self.rotation = self.display_config.default_rotation
        self.should_update = True

    def get_display_size(self, img_width: int, img_height: int) -> Tuple[int, int]:
        """
        Calcula tamanho de display para uma imagem mantendo qualidade original
        Adapta-se a qualquer tamanho sem preencher a tela inteira
        """
        if img_width < self.display_config.min_width or img_height < self.display_config.min_height:
            scale = max(
                self.display_config.min_width / img_width,
                self.display_config.min_height / img_height
            )
            display_width = int(img_width * scale)
            display_height = int(img_height * scale)
        else:
            scale = min(
                self.display_config.max_width / img_width,
                self.display_config.max_height / img_height,
                1.0
            )
            display_width = int(img_width * scale)
            display_height = int(img_height * scale)

        return display_width, display_height

    def _display_loop(self):
        """Loop principal de visualização"""
        while not self.stop_flag:
            if self.should_update and self.current_image is not None:
                self._render()

            key = cv2.waitKey(50) & 0xFF
            if (key != 255):
                self._handle_key(key)

            time.sleep(0.01)

    def _render(self):
        """Renderiza imagem com zoom e pan em janela fixa com letterbox"""
        base_image = self._apply_rotation(self.current_image)
        base_image = self._apply_brightness_contrast(base_image)
        display_image = self._apply_zoom_pan(base_image)

        canvas = np.zeros(
            (self.window_height, self.window_width, 3), dtype=np.uint8)

        img_h, img_w = display_image.shape[:2]

        if img_w > self.window_width or img_h > self.window_height:
            scale = min(self.window_width / img_w, self.window_height / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            fitted_image = cv2.resize(
                display_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            fitted_image = display_image
            new_w = img_w
            new_h = img_h

        y_offset = (self.window_height - new_h) // 2
        x_offset = (self.window_width - new_w) // 2
        canvas[y_offset:y_offset + new_h,
               x_offset:x_offset + new_w] = fitted_image

        self._draw_instructions(canvas)

        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.window_width,
                         self.window_height)
        cv2.imshow(self.window_name, canvas)

    def _apply_zoom_pan(self, image: np.ndarray) -> np.ndarray:
        """Aplica zoom e pan - extrai região da imagem com zoom"""
        h, w = image.shape[:2]

        # Aplica zoom (resize)
        new_w = max(1, int(w * self.zoom_level))
        new_h = max(1, int(h * self.zoom_level))
        zoomed = cv2.resize(image, (new_w, new_h),
                            interpolation=cv2.INTER_LINEAR)

        zh, zw = zoomed.shape[:2]

        # Calcula região a extrair (clamp pan dentro dos limites válidos)
        x1 = int(max(0, min(self.pan_x, max(0, zw - self.window_width))))
        y1 = int(max(0, min(self.pan_y, max(0, zh - self.window_height))))
        x2 = min(zw, x1 + self.window_width)
        y2 = min(zh, y1 + self.window_height)

        crop = zoomed[y1:y2, x1:x2]

        crop_h, crop_w = crop.shape[:2]

        # Se o crop for menor que a janela (ex: imagem menor que window ou pan nos limites),
        # pad à direita/embaixo para garantir que retornemos exatamente window_size.
        if crop_w != self.window_width or crop_h != self.window_height:
            pad_right = max(0, self.window_width - crop_w)
            pad_bottom = max(0, self.window_height - crop_h)
            # top, bottom, left, right
            crop = cv2.copyMakeBorder(
                crop,
                0, pad_bottom,
                0, pad_right,
                borderType=cv2.BORDER_CONSTANT,
                value=(0, 0, 0)
            )

        # Retorna imagem com tamanho exatamente (window_height, window_width, 3)
        return crop

    def _apply_brightness_contrast(self, image: np.ndarray) -> np.ndarray:
        """Aplica ajustes de brilho e contraste"""
        if self.brightness == 0 and self.contrast == 1.0:
            return image

        adjusted = cv2.convertScaleAbs(
            image, alpha=self.contrast, beta=self.brightness)
        return adjusted

    def _apply_rotation(self, image: np.ndarray) -> np.ndarray:
        """Aplica rotação na imagem"""
        if self.rotation == 0:
            return image

        h, w = image.shape[:2]
        center = (w // 2, h // 2)

        matrix = cv2.getRotationMatrix2D(center, self.rotation, 1.0)

        cos = abs(matrix[0, 0])
        sin = abs(matrix[0, 1])

        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        matrix[0, 2] += (new_w / 2) - center[0]
        matrix[1, 2] += (new_h / 2) - center[1]

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
            f"Zoom: {self.zoom_level:.2f}x"
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

        # Zoom in
        if key in [ord('q'), ord('Q')]:
            old_zoom = self.zoom_level
            self.zoom_level = min(
                self.zoom_level + self.zoom_config.zoom_step, getattr(self.zoom_config, "max_zoom", self.zoom_level + self.zoom_config.zoom_step))

            if self.current_image is not None:
                img_h, img_w = self.current_image.shape[:2]
                zoom_ratio = self.zoom_level / \
                    max(old_zoom, self.MIN_ZOOM_FOR_SAFETY)

                center_x = self.pan_x + (self.window_width // 2)
                center_y = self.pan_y + (self.window_height // 2)

                new_center_x = center_x * zoom_ratio
                new_center_y = center_y * zoom_ratio

                self.pan_x = int(new_center_x - (self.window_width // 2))
                self.pan_y = int(new_center_y - (self.window_height // 2))

                max_pan_x = max(
                    0, int(img_w * self.zoom_level - self.window_width))
                max_pan_y = max(
                    0, int(img_h * self.zoom_level - self.window_height))
                self.pan_x = max(0, min(self.pan_x, max_pan_x))
                self.pan_y = max(0, min(self.pan_y, max_pan_y))

            changed = True

        # Zoom out
        elif key in [ord('e'), ord('E')]:
            old_zoom = self.zoom_level
            # Permitir zoom livre para baixo (sem forçar um limite rígido), mas proteger de zero
            self.zoom_level = max(
                self.MIN_ZOOM_FOR_SAFETY, self.zoom_level - self.zoom_config.zoom_step)

            if self.current_image is not None:
                img_h, img_w = self.current_image.shape[:2]
                zoom_ratio = self.zoom_level / \
                    max(old_zoom, self.MIN_ZOOM_FOR_SAFETY)

                center_x = self.pan_x + (self.window_width // 2)
                center_y = self.pan_y + (self.window_height // 2)

                new_center_x = center_x * zoom_ratio
                new_center_y = center_y * zoom_ratio

                self.pan_x = int(new_center_x - (self.window_width // 2))
                self.pan_y = int(new_center_y - (self.window_height // 2))

                max_pan_x = max(
                    0, int(img_w * self.zoom_level - self.window_width))
                max_pan_y = max(
                    0, int(img_h * self.zoom_level - self.window_height))
                self.pan_x = max(0, min(self.pan_x, max_pan_x))
                self.pan_y = max(0, min(self.pan_y, max_pan_y))

            changed = True

        # Reset: centraliza no bbox mantendo zoom atual
        elif key in [ord('r'), ord('R')]:
            bbox = None
            if self.current_image is not None:
                bbox = self._detect_content_bbox_robust(self.current_image)

            if bbox is not None:
                x1, y1, x2, y2 = bbox
                bbox_center_x = (x1 + x2) / 2.0
                bbox_center_y = (y1 + y2) / 2.0

                zoomed_bbox_center_x = bbox_center_x * self.zoom_level
                zoomed_bbox_center_y = bbox_center_y * self.zoom_level

                self.pan_x = int(zoomed_bbox_center_x -
                                 (self.window_width // 2))
                self.pan_y = int(zoomed_bbox_center_y -
                                 (self.window_height // 2))

                self.pan_x = max(0, self.pan_x)
                self.pan_y = max(0, self.pan_y)

                img_h, img_w = self.current_image.shape[:2]
                zoomed_img_w = int(img_w * self.zoom_level)
                zoomed_img_h = int(img_h * self.zoom_level)

                max_pan_x = max(0, zoomed_img_w - self.window_width)
                max_pan_y = max(0, zoomed_img_h - self.window_height)

                self.pan_x = min(self.pan_x, max_pan_x)
                self.pan_y = min(self.pan_y, max_pan_y)
            else:
                # centraliza imagem inteira
                if self.current_image is not None:
                    img_h, img_w = self.current_image.shape[:2]
                    zoomed_img_w = int(img_w * self.zoom_level)
                    zoomed_img_h = int(img_h * self.zoom_level)

                    self.pan_x = max(
                        0, (zoomed_img_w - self.window_width) // 2)
                    self.pan_y = max(
                        0, (zoomed_img_h - self.window_height) // 2)

            self.brightness = self.display_config.default_brightness
            self.contrast = self.display_config.default_contrast
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
        elif key in [ord('n'), ord('N')]:
            self.rotation = (
                self.rotation + self.display_config.rotation_step) % 360
            changed = True
        elif key in [ord('m'), ord('M')]:
            self.rotation = (
                self.rotation - self.display_config.rotation_step) % 360
            changed = True
        elif key in [ord('t'), ord('T')]:
            self.rotation = self.display_config.default_rotation
            changed = True

        if changed:
            self.should_update = True
