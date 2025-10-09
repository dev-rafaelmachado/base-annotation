import os
import cv2
import json
from pathlib import Path
import numpy as np
from datetime import datetime
import yaml
import shutil
import re
import threading
import time


class ExpiryDateAnnotator:
    def __init__(self, dataset_path, output_path="annotations_output"):
        """
        Inicializa o anotador de datas de validade

        Args:
            dataset_path: Caminho para a pasta do dataset Roboflow (contém train/, valid/, test/)
            output_path: Caminho para salvar as anotações
        """
        self.dataset_path = Path(dataset_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(exist_ok=True)

        # Lê data.yaml para obter informações das classes
        self.class_names = self.load_class_names()

        # Define os caminhos das imagens (todas de uma vez)
        self.image_paths = self.get_all_images()

        # Arquivo único para salvar todas as anotações
        self.annotations_file = self.output_path / "expiry_dates_all.json"
        self.annotations = self.load_existing_annotations()

        # Pasta para salvar crops das bounding boxes
        self.crops_path = self.output_path / "crops"
        self.crops_path.mkdir(exist_ok=True)

        # Controles de zoom
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0

        # Controle de thread de visualização
        self.should_update_display = False
        self.current_image = None
        self.display_thread = None
        self.stop_display = False

    def load_class_names(self):
        """Carrega os nomes das classes do data.yaml"""
        yaml_path = self.dataset_path / "data.yaml"
        if (yaml_path.exists()):
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
                names = data.get('names', {})

                # Se 'names' é uma lista, converte para dicionário
                if isinstance(names, list):
                    return {i: name for i, name in enumerate(names)}
                # Se já é dicionário, retorna como está
                elif isinstance(names, dict):
                    return names

        return {}

    def get_all_images(self):
        """Coleta todas as imagens de todos os subsets"""
        all_images = []
        subsets = ["train", "valid", "test"]

        print("\n🔄 Coletando todas as imagens...")

        for subset in subsets:
            subset_path = self.dataset_path / subset / "images"
            if not subset_path.exists():
                continue

            images = sorted(list(subset_path.glob("*.jpg")) +
                            list(subset_path.glob("*.png")) +
                            list(subset_path.glob("*.jpeg")))

            if images:
                print(f"📁 {subset}: {len(images)} imagens")

                for img_path in images:
                    all_images.append({
                        'path': img_path,
                        'subset': subset,
                        'label_path': img_path.parent.parent / "labels" / f"{img_path.stem}.txt"
                    })

        print(f"✅ Total: {len(all_images)} imagens\n")
        return all_images

    def load_existing_annotations(self):
        """Carrega anotações existentes se houver"""
        if self.annotations_file.exists():
            with open(self.annotations_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_annotations(self):
        """Salva as anotações em JSON"""
        with open(self.annotations_file, 'w', encoding='utf-8') as f:
            json.dump(self.annotations, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Anotações salvas em: {self.annotations_file}")

    def read_yolo_label(self, label_path):
        """
        Lê um arquivo de label YOLOv8 (suporta bbox retangular e polígono)
        Formato bbox: class_id x_center y_center width height
        Formato polígono: class_id x1 y1 x2 y2 x3 y3 x4 y4 ...
        """
        boxes = []
        if not label_path.exists():
            return boxes

        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue

                class_id = int(parts[0])
                coords = list(map(float, parts[1:]))

                # Detecta se é polígono (mais de 4 valores) ou bbox retangular
                if len(coords) > 4:
                    # É um polígono (coordenadas x,y normalizadas)
                    boxes.append({
                        'class_id': class_id,
                        'class_name': self.class_names.get(class_id, f"class_{class_id}"),
                        'type': 'polygon',
                        'coords': coords  # [x1, y1, x2, y2, x3, y3, ...]
                    })
                else:
                    # É uma bbox retangular
                    x_center, y_center, width, height = coords
                    boxes.append({
                        'class_id': class_id,
                        'class_name': self.class_names.get(class_id, f"class_{class_id}"),
                        'type': 'bbox',
                        'x_center': x_center,
                        'y_center': y_center,
                        'width': width,
                        'height': height
                    })
        return boxes

    def polygon_to_points(self, coords, img_width, img_height):
        """Converte coordenadas normalizadas do polígono para pontos absolutos"""
        points = []
        for i in range(0, len(coords), 2):
            x = int(coords[i] * img_width)
            y = int(coords[i + 1] * img_height)
            points.append([x, y])
        return np.array(points, dtype=np.int32)

    def yolo_to_bbox(self, box, img_width, img_height):
        """Converte coordenadas YOLO para bbox absoluto"""
        x_center = box['x_center'] * img_width
        y_center = box['y_center'] * img_height
        width = box['width'] * img_width
        height = box['height'] * img_height

        x1 = int(x_center - width / 2)
        y1 = int(y_center - height / 2)
        x2 = int(x_center + width / 2)
        y2 = int(y_center + height / 2)

        return x1, y1, x2, y2

    def draw_annotation_on_image(self, image, box, img_width, img_height, box_idx, total_boxes):
        """Desenha o polígono ou bbox na imagem completa"""
        img_display = image.copy()

        if box['type'] == 'polygon':
            # Desenha polígono na imagem original (SEM retificação)
            points = self.polygon_to_points(
                box['coords'], img_width, img_height)

            # Desenha o polígono preenchido com transparência leve
            overlay = img_display.copy()
            cv2.fillPoly(overlay, [points], (0, 255, 255))  # Amarelo
            cv2.addWeighted(overlay, 0.15, img_display, 0.85, 0, img_display)

            # Desenha as bordas do polígono
            cv2.polylines(img_display, [points], True, (0, 255, 0), 2)

        else:
            # Para bbox, desenha retângulo
            x1, y1, x2, y2 = self.yolo_to_bbox(box, img_width, img_height)
            cv2.rectangle(img_display, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Adiciona texto com informações
        info_text = f"Box {box_idx+1}/{total_boxes} - {box['class_name']}"

        # Fundo para o texto
        text_size = cv2.getTextSize(
            info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        cv2.rectangle(img_display, (5, 5),
                      (text_size[0] + 15, 35), (0, 0, 0), -1)

        # Texto
        cv2.putText(img_display, info_text, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

        return img_display

    def apply_zoom_and_pan(self, image):
        """Aplica zoom e pan na imagem"""
        h, w = image.shape[:2]

        # Calcula dimensões com zoom
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)

        # Redimensiona a imagem
        if self.zoom_level != 1.0:
            zoomed = cv2.resize(image, (new_w, new_h),
                                interpolation=cv2.INTER_LINEAR)
        else:
            zoomed = image

        # Aplica pan (deslocamento)
        zh, zw = zoomed.shape[:2]

        # Calcula região visível
        x1 = max(0, min(self.pan_x, zw - w))
        y1 = max(0, min(self.pan_y, zh - h))
        x2 = min(zw, x1 + w)
        y2 = min(zh, y1 + h)

        # Extrai região visível
        visible = zoomed[y1:y2, x1:x2]

        # Se a imagem visível for menor que o original, preenche com preto
        if visible.shape[0] < h or visible.shape[1] < w:
            canvas = np.zeros((h, w, 3), dtype=np.uint8)
            canvas[:visible.shape[0], :visible.shape[1]] = visible
            return canvas

        return visible

    def display_loop(self, window_name="Imagem Completa"):
        """Loop contínuo para atualizar a visualização"""
        while not self.stop_display:
            if self.should_update_display and self.current_image is not None:
                h, w = self.current_image.shape[:2]

                # Redimensiona para caber na tela inicialmente
                max_width = 1200
                max_height = 800

                scale = min(max_width / w, max_height / h, 1.0)

                # Se a imagem for muito pequena, aumenta
                if scale < 0.5:
                    scale = 1.0
                if w < 400 or h < 300:
                    scale = max(400 / w, 300 / h)

                display_w = int(w * scale)
                display_h = int(h * scale)

                # Redimensiona para display
                base_image = cv2.resize(self.current_image, (display_w, display_h),
                                        interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)

                # Aplica zoom e pan
                display_image = self.apply_zoom_and_pan(base_image)

                # Adiciona instruções de zoom na imagem
                instructions = [
                    "ZOOM: [ Q ] aumentar | [ E ] diminuir | [ R ] resetar",
                    "MOVER: [ W ] cima | [ S ] baixo | [ A ] esquerda | [ D ] direita",
                    f"Zoom: {self.zoom_level:.1f}x"
                ]

                for i, text in enumerate(instructions):
                    y_pos = display_image.shape[0] - 60 + i*20
                    cv2.putText(display_image, text, (10, y_pos),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

                cv2.imshow(window_name, display_image)

            # Processa eventos de teclado
            key = cv2.waitKey(50) & 0xFF
            if key != 255:  # Alguma tecla foi pressionada
                self.handle_zoom_keys(key)
                self.should_update_display = True

            time.sleep(0.01)

    def handle_zoom_keys(self, key):
        """Processa teclas de zoom e pan"""
        changed = False

        # Zoom com Q/E
        if key == ord('q') or key == ord('Q'):  # Aumentar zoom
            self.zoom_level = min(self.zoom_level + 0.2, 5.0)
            changed = True
        elif key == ord('e') or key == ord('E'):  # Diminuir zoom
            self.zoom_level = max(self.zoom_level - 0.2, 0.5)
            changed = True
        elif key == ord('r') or key == ord('R'):  # Resetar
            self.zoom_level = 1.0
            self.pan_x = 0
            self.pan_y = 0
            changed = True

        # Pan com WASD
        elif key == ord('w') or key == ord('W'):  # Cima
            self.pan_y = max(0, self.pan_y - 50)
            changed = True
        elif key == ord('s') or key == ord('S'):  # Baixo
            self.pan_y += 50
            changed = True
        elif key == ord('a') or key == ord('A'):  # Esquerda
            self.pan_x = max(0, self.pan_x - 50)
            changed = True
        elif key == ord('d') or key == ord('D'):  # Direita
            self.pan_x += 50
            changed = True

        if changed:
            self.should_update_display = True

    def start_display_thread(self):
        """Inicia a thread de visualização"""
        self.stop_display = False
        self.display_thread = threading.Thread(
            target=self.display_loop, daemon=True)
        self.display_thread.start()

    def stop_display_thread(self):
        """Para a thread de visualização"""
        self.stop_display = True
        if self.display_thread:
            self.display_thread.join(timeout=1)

    def update_display(self, image):
        """Atualiza a imagem sendo exibida"""
        self.current_image = image
        self.should_update_display = True

    def calculate_auto_zoom(self, box, img_width, img_height, display_w, display_h):
        """
        Calcula zoom e posição automáticos baseado no polígono/bbox
        para focar na região de interesse
        """
        if box['type'] == 'polygon':
            # Converte pontos do polígono
            points = self.polygon_to_points(
                box['coords'], img_width, img_height)

            # Calcula bounding box do polígono
            x_coords = points[:, 0]
            y_coords = points[:, 1]
            bbox_x1, bbox_y1 = x_coords.min(), y_coords.min()
            bbox_x2, bbox_y2 = x_coords.max(), y_coords.max()
            bbox_w = bbox_x2 - bbox_x1
            bbox_h = bbox_y2 - bbox_y1
            center_x = (bbox_x1 + bbox_x2) / 2
            center_y = (bbox_y1 + bbox_y2) / 2
        else:
            # Usa bbox retangular
            x1, y1, x2, y2 = self.yolo_to_bbox(box, img_width, img_height)
            bbox_w = x2 - x1
            bbox_h = y2 - y1
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

        # Escala a bbox para o tamanho de display
        scale = min(display_w / img_width, display_h / img_height)
        scaled_bbox_w = bbox_w * scale
        scaled_bbox_h = bbox_h * scale
        scaled_center_x = center_x * scale
        scaled_center_y = center_y * scale

        # Calcula zoom ideal (região deve ocupar ~60% da tela)
        target_screen_coverage = 0.6
        zoom_w = (display_w * target_screen_coverage) / scaled_bbox_w
        zoom_h = (display_h * target_screen_coverage) / scaled_bbox_h
        auto_zoom = min(zoom_w, zoom_h)

        # Limita o zoom entre 1.0 e 5.0
        auto_zoom = max(1.0, min(5.0, auto_zoom))

        # Calcula pan para centralizar a região
        # Após o zoom, precisamos ajustar o pan para centralizar
        zoomed_w = display_w * auto_zoom
        zoomed_h = display_h * auto_zoom

        # Posição do centro da região no espaço ampliado
        zoomed_center_x = scaled_center_x * auto_zoom
        zoomed_center_y = scaled_center_y * auto_zoom

        # Pan necessário para centralizar
        auto_pan_x = int(zoomed_center_x - display_w / 2)
        auto_pan_y = int(zoomed_center_y - display_h / 2)

        # Garante que pan não ultrapasse limites
        auto_pan_x = max(0, min(auto_pan_x, zoomed_w - display_w))
        auto_pan_y = max(0, min(auto_pan_y, zoomed_h - display_h))

        return auto_zoom, auto_pan_x, auto_pan_y

    def normalize_date(self, date_str):
        """
        Normaliza diferentes formatos de data para YYYY-MM-DD

        Aceita:
        - 01/02/2025 -> 2025-02-01
        - 01022025 -> 2025-02-01
        - 010225 -> 2025-02-01

        Returns:
            tuple: (normalized_date, is_valid)
        """
        date_str = date_str.strip()

        # Padrão 1: DD/MM/YYYY ou DD/MM/YY
        match = re.match(r'^(\d{2})/(\d{2})/(\d{2,4})$', date_str)
        if match:
            day, month, year = match.groups()
            # Se ano tem 2 dígitos, assume 20XX
            if len(year) == 2:
                year = f"20{year}"
            try:
                # Valida a data
                datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
                return f"{year}-{month}-{day}", True
            except ValueError:
                return None, False

        # Padrão 2: DDMMYYYY (8 dígitos)
        match = re.match(r'^(\d{2})(\d{2})(\d{4})$', date_str)
        if match:
            day, month, year = match.groups()
            try:
                datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
                return f"{year}-{month}-{day}", True
            except ValueError:
                return None, False

        # Padrão 3: DDMMYY (6 dígitos)
        match = re.match(r'^(\d{2})(\d{2})(\d{2})$', date_str)
        if match:
            day, month, year = match.groups()
            year = f"20{year}"
            try:
                datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
                return f"{year}-{month}-{day}", True
            except ValueError:
                return None, False

        # Não reconhecido
        return None, False

    def clear_terminal(self):
        """Limpa o terminal mantendo as instruções no topo"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_instructions(self):
        """Imprime as instruções no topo do terminal"""
        print("\n" + "="*60)
        print("INSTRUÇÕES:")
        print("- ZOOM: teclas [ Q ] aumentar | [ E ] diminuir | [ R ] resetar")
        print("- MOVER: [ W ] cima | [ S ] baixo | [ A ] esq | [ D ] dir")
        print("- Digite a data: 01/02/2025 ou 01022025 ou 010225")
        print("  (será salva como: 2025-02-01)")
        print("- 'skip' = pular | 'quit' = sair | 'ilegivel' = não consigo ler")
        print("- 'back' = desfazer última anotação")
        print("="*60 + "\n")

    def annotate(self, start_from=0):
        """Inicia o processo de anotação"""
        if not self.image_paths:
            print(f"❌ Nenhuma imagem encontrada")
            return

        total_images = len(self.image_paths)
        already_annotated = len(self.annotations)

        # Imprime header inicial
        self.clear_terminal()
        print(f"\n📊 Total de imagens: {total_images}")
        print(f"✅ Já anotadas: {already_annotated} bounding boxes")
        print(f"🚀 Iniciando a partir da imagem {start_from}")
        print(f"📋 Classes: {self.class_names}")
        self.print_instructions()

        # Inicia thread de visualização
        self.start_display_thread()

        annotation_history = []

        try:
            for idx, img_info in enumerate(self.image_paths[start_from:], start=start_from):
                image_path = img_info['path']
                subset = img_info['subset']
                label_path = img_info['label_path']

                # Carrega imagem
                image = cv2.imread(str(image_path))
                if image is None:
                    print(f"⚠️  Erro ao carregar: {image_path.name}")
                    continue

                img_height, img_width = image.shape[:2]

                # Lê as anotações (polígonos ou bboxes)
                boxes = self.read_yolo_label(label_path)

                if not boxes:
                    continue

                # Para cada anotação, solicita a data
                for box_idx, box in enumerate(boxes):
                    # ID único para esta anotação
                    crop_id = f"{subset}_{image_path.stem}_box{box_idx}"

                    # Se já foi anotado, pula
                    if crop_id in self.annotations:
                        continue

                    # Limpa terminal e mostra instruções
                    self.clear_terminal()
                    self.print_instructions()

                    # Desenha a anotação na imagem
                    img_display = self.draw_annotation_on_image(
                        image, box, img_width, img_height, box_idx, len(boxes))

                    # Calcula tamanho de display
                    h, w = img_display.shape[:2]
                    max_width = 1200
                    max_height = 800
                    scale = min(max_width / w, max_height / h, 1.0)

                    if scale < 0.5:
                        scale = 1.0
                    if w < 400 or h < 300:
                        scale = max(400 / w, 300 / h)

                    display_w = int(w * scale)
                    display_h = int(h * scale)

                    # Calcula zoom e pan automáticos
                    auto_zoom, auto_pan_x, auto_pan_y = self.calculate_auto_zoom(
                        box, img_width, img_height, display_w, display_h)

                    # Aplica zoom e pan automáticos
                    self.zoom_level = auto_zoom
                    self.pan_x = auto_pan_x
                    self.pan_y = auto_pan_y

                    # Salva uma versão com a anotação desenhada
                    crop_filename = self.crops_path / f"{crop_id}.jpg"
                    cv2.imwrite(str(crop_filename), img_display)

                    # Atualiza a visualização
                    self.update_display(img_display)
                    time.sleep(0.1)

                    # Informações da imagem atual
                    print(
                        f"📸 [{idx+1}/{total_images}] {subset}/{image_path.name}")
                    print(
                        f"📦 Anotação {box_idx+1}/{len(boxes)} - Classe: {box['class_name']}")
                    print(f"📐 Tipo: {box['type']}")
                    print(f"🔍 Zoom automático: {auto_zoom:.1f}x")
                    print(f"💾 Salvo: {crop_filename.name}\n")

                    while True:
                        expiry_date = input("📅 Data de validade: ").strip()

                        if expiry_date.lower() == 'quit':
                            print("\n💾 Salvando e encerrando...")
                            self.save_annotations()
                            self.stop_display_thread()
                            cv2.destroyAllWindows()
                            self.export_summary()
                            return

                        if expiry_date.lower() == 'back' and annotation_history:
                            last_crop_id = annotation_history.pop()
                            if last_crop_id in self.annotations:
                                del self.annotations[last_crop_id]
                                print(f"↩️  Removida: {last_crop_id}")
                            break

                        if expiry_date.lower() == 'skip':
                            print("⏭️  Pulando...")
                            break

                        if expiry_date.lower() == 'ilegivel':
                            if box['type'] == 'polygon':
                                coords_info = {'type': 'polygon',
                                               'coords': box['coords']}
                            else:
                                coords_info = {
                                    'type': 'bbox',
                                    'x_center': box['x_center'],
                                    'y_center': box['y_center'],
                                    'width': box['width'],
                                    'height': box['height']
                                }

                            self.annotations[crop_id] = {
                                'image': image_path.name,
                                'subset': subset,
                                'box_index': box_idx,
                                'class_id': box['class_id'],
                                'class_name': box['class_name'],
                                'annotation': coords_info,
                                'expiry_date': None,
                                'expiry_date_raw': None,
                                'status': 'ilegivel',
                                'timestamp': datetime.now().isoformat()
                            }
                            annotation_history.append(crop_id)
                            print("✓ Marcado como ilegível")
                            break

                        if expiry_date:
                            normalized_date, is_valid = self.normalize_date(
                                expiry_date)

                            if is_valid:
                                if box['type'] == 'polygon':
                                    coords_info = {
                                        'type': 'polygon', 'coords': box['coords']}
                                else:
                                    coords_info = {
                                        'type': 'bbox',
                                        'x_center': box['x_center'],
                                        'y_center': box['y_center'],
                                        'width': box['width'],
                                        'height': box['height']
                                    }

                                self.annotations[crop_id] = {
                                    'image': image_path.name,
                                    'subset': subset,
                                    'box_index': box_idx,
                                    'class_id': box['class_id'],
                                    'class_name': box['class_name'],
                                    'annotation': coords_info,
                                    'expiry_date': normalized_date,
                                    'expiry_date_raw': expiry_date,
                                    'status': 'anotado',
                                    'timestamp': datetime.now().isoformat()
                                }
                                annotation_history.append(crop_id)
                                print(f"✓ Salvo como: {normalized_date}")
                                break
                            else:
                                print(
                                    "❌ Formato inválido! Use: DD/MM/YYYY, DDMMYYYY ou DDMMYY")
                        else:
                            print("❌ Digite uma data ou comando válido")

                    # Salva a cada 5 anotações
                    if len(self.annotations) % 5 == 0 and self.annotations:
                        self.save_annotations()

        finally:
            self.stop_display_thread()
            cv2.destroyAllWindows()
            self.save_annotations()
            print(f"\n🎉 Concluído! Total: {len(self.annotations)} anotações")

    def export_summary(self):
        """Exporta um resumo das anotações"""
        summary_file = self.output_path / "summary.txt"

        total = len(self.annotations)
        anotados = sum(1 for a in self.annotations.values()
                       if a['status'] == 'anotado')
        ilegiveis = sum(1 for a in self.annotations.values()
                        if a['status'] == 'ilegivel')

        # Estatísticas
        by_class = {}
        by_subset = {}
        for annotation in self.annotations.values():
            class_name = annotation.get('class_name', 'unknown')
            by_class[class_name] = by_class.get(class_name, 0) + 1

            subset = annotation.get('subset', 'unknown')
            by_subset[subset] = by_subset.get(subset, 0) + 1

        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("RESUMO DAS ANOTAÇÕES DE DATAS\n")
            f.write("="*50 + "\n")
            f.write(f"Total de bboxes anotadas: {total}\n")
            f.write(f"Com data legível: {anotados}\n")
            f.write(f"Ilegíveis: {ilegiveis}\n\n")

            f.write("Por subset:\n")
            for subset, count in sorted(by_subset.items()):
                f.write(f"  - {subset}: {count}\n")

            f.write("\nPor classe:\n")
            for class_name, count in sorted(by_class.items()):
                f.write(f"  - {class_name}: {count}\n")

            f.write(f"\nArquivo JSON: {self.annotations_file}\n")
            f.write(f"Crops salvos em: {self.crops_path}\n")

        print(f"\n📊 Resumo: {summary_file}")


if __name__ == "__main__":
    # Configuração
    DATASET_PATH = "static"
    OUTPUT_PATH = "annotations_output"

    # Cria o anotador
    annotator = ExpiryDateAnnotator(DATASET_PATH, OUTPUT_PATH)

    # Inicia anotação
    annotator.annotate(start_from=0)

    # Exporta resumo
    annotator.export_summary()
