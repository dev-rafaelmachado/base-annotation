"""
Gerenciamento de anotações
"""
import json
from pathlib import Path
from typing import Dict, Any
from ..models import Annotation, AnnotationStatus
from ..config import PathConfig


class AnnotationManager:
    """Gerencia anotações de datas de validade"""

    def __init__(self, paths: PathConfig):
        self.paths = paths
        self.annotations: Dict[str, Annotation] = {}
        self._load_existing()

    def _load_existing(self):
        """Carrega anotações existentes"""
        if self.paths.annotations_file.exists():
            with open(self.paths.annotations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for crop_id, ann_data in data.items():
                    self.annotations[crop_id] = Annotation.from_dict(
                        crop_id, ann_data)

    def is_annotated(self, crop_id: str) -> bool:
        """Verifica se crop já foi anotado"""
        return crop_id in self.annotations

    def add_annotation(
        self,
        crop_id: str,
        image_name: str,
        subset: str,
        box_index: int,
        box: Dict[str, Any],
        expiry_date: str,
        expiry_date_raw: str
    ):
        """Adiciona nova anotação"""
        geometry = self._create_geometry(box)

        annotation = Annotation(
            crop_id=crop_id,
            image_name=image_name,
            subset=subset,
            box_index=box_index,
            class_id=box['class_id'],
            class_name=box['class_name'],
            geometry=geometry,
            expiry_date=expiry_date,
            expiry_date_raw=expiry_date_raw,
            status=AnnotationStatus.ANNOTATED
        )

        self.annotations[crop_id] = annotation
        self._auto_save()

    def add_illegible(
        self,
        crop_id: str,
        image_name: str,
        subset: str,
        box_index: int,
        box: Dict[str, Any]
    ):
        """Marca como ilegível"""
        geometry = self._create_geometry(box)

        annotation = Annotation(
            crop_id=crop_id,
            image_name=image_name,
            subset=subset,
            box_index=box_index,
            class_id=box['class_id'],
            class_name=box['class_name'],
            geometry=geometry,
            status=AnnotationStatus.ILLEGIBLE
        )

        self.annotations[crop_id] = annotation
        self._auto_save()

    def remove_annotation(self, crop_id: str):
        """Remove anotação"""
        if crop_id in self.annotations:
            del self.annotations[crop_id]

    def _create_geometry(self, box: Dict[str, Any]) -> Dict[str, Any]:
        """Cria geometria a partir de box"""
        if box['type'] == 'polygon':
            return {
                'type': 'polygon',
                'coords': box['coords']
            }
        else:
            return {
                'type': 'bbox',
                'x_center': box['x_center'],
                'y_center': box['y_center'],
                'width': box['width'],
                'height': box['height']
            }

    def _auto_save(self):
        """Salva automaticamente a cada N anotações"""
        if len(self.annotations) % 5 == 0:
            self.save()

    def save(self):
        """Salva todas as anotações"""
        data = {
            crop_id: ann.to_dict()
            for crop_id, ann in self.annotations.items()
        }

        with open(self.paths.annotations_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Anotações salvas: {self.paths.annotations_file}")

    def export_summary(self):
        """Exporta resumo estatístico"""
        summary_file = self.paths.output_path / "summary.txt"

        total = len(self.annotations)
        annotated = sum(
            1 for a in self.annotations.values()
            if a.status == AnnotationStatus.ANNOTATED
        )
        illegible = sum(
            1 for a in self.annotations.values()
            if a.status == AnnotationStatus.ILLEGIBLE
        )

        # Estatísticas por classe e subset
        by_class = {}
        by_subset = {}
        for ann in self.annotations.values():
            by_class[ann.class_name] = by_class.get(ann.class_name, 0) + 1
            by_subset[ann.subset] = by_subset.get(ann.subset, 0) + 1

        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("RESUMO DAS ANOTAÇÕES DE DATAS\n")
            f.write("=" * 50 + "\n")
            f.write(f"Total de anotações: {total}\n")
            f.write(f"Com data legível: {annotated}\n")
            f.write(f"Ilegíveis: {illegible}\n\n")

            f.write("Por subset:\n")
            for subset, count in sorted(by_subset.items()):
                f.write(f"  - {subset}: {count}\n")

            f.write("\nPor classe:\n")
            for class_name, count in sorted(by_class.items()):
                f.write(f"  - {class_name}: {count}\n")

            f.write(f"\nArquivo JSON: {self.paths.annotations_file}\n")
            f.write(f"Crops salvos em: {self.paths.crops_path}\n")

        print(f"\n📊 Resumo: {summary_file}")
