"""
Carregamento de datasets YOLOv8 do Roboflow
"""
from pathlib import Path
from typing import List, Dict, Any
import yaml


class DatasetLoader:
    """Carrega datasets YOLOv8 com estrutura Roboflow"""

    def __init__(self, dataset_path: Path):
        self.dataset_path = dataset_path
        self.class_names = self._load_class_names()

    def _load_class_names(self) -> Dict[int, str]:
        """Carrega nomes das classes do data.yaml"""
        yaml_path = self.dataset_path / "data.yaml"
        if not yaml_path.exists():
            return {}

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            names = data.get('names', {})

            # Converte lista para dicionário se necessário
            if isinstance(names, list):
                return {i: name for i, name in enumerate(names)}
            return names

    def get_all_images(self) -> List[Dict[str, Any]]:
        """Coleta todas as imagens de todos os subsets"""
        all_images = []
        subsets = ["train", "valid", "test"]

        print("\n🔄 Coletando todas as imagens...")

        for subset in subsets:
            subset_path = self.dataset_path / subset / "images"
            if not subset_path.exists():
                continue

            images = sorted(
                list(subset_path.glob("*.jpg")) +
                list(subset_path.glob("*.png")) +
                list(subset_path.glob("*.jpeg"))
            )

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

    def read_yolo_label(self, label_path: Path) -> List[Dict[str, Any]]:
        """Lê arquivo de label YOLO (bbox ou polígono)"""
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

                # Detecta tipo baseado no número de coordenadas
                if len(coords) > 4:
                    # Polígono
                    boxes.append({
                        'class_id': class_id,
                        'class_name': self.class_names.get(class_id, f"class_{class_id}"),
                        'type': 'polygon',
                        'coords': coords
                    })
                else:
                    # Bbox retangular
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
