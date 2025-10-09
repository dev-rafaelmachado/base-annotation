"""
Modelos de dados para anotações
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AnnotationType(Enum):
    """Tipo de anotação"""
    BBOX = "bbox"
    POLYGON = "polygon"


class AnnotationStatus(Enum):
    """Status da anotação"""
    ANNOTATED = "anotado"
    ILLEGIBLE = "ilegivel"
    PENDING = "pendente"


@dataclass
class BoundingBox:
    """Bounding box retangular"""
    x_center: float
    y_center: float
    width: float
    height: float

    def to_absolute(self, img_width: int, img_height: int) -> tuple:
        """Converte para coordenadas absolutas"""
        x_center_abs = self.x_center * img_width
        y_center_abs = self.y_center * img_height
        width_abs = self.width * img_width
        height_abs = self.height * img_height

        x1 = int(x_center_abs - width_abs / 2)
        y1 = int(y_center_abs - height_abs / 2)
        x2 = int(x_center_abs + width_abs / 2)
        y2 = int(y_center_abs + height_abs / 2)

        return x1, y1, x2, y2

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'type': AnnotationType.BBOX.value,
            **asdict(self)
        }


@dataclass
class Polygon:
    """Polígono com múltiplos pontos"""
    coords: List[float]

    def to_points(self, img_width: int, img_height: int):
        """Converte para array de pontos absolutos"""
        import numpy as np
        points = []
        for i in range(0, len(self.coords), 2):
            x = int(self.coords[i] * img_width)
            y = int(self.coords[i + 1] * img_height)
            points.append([x, y])
        return np.array(points, dtype=np.int32)

    def get_bounding_box(self, img_width: int, img_height: int) -> tuple:
        """Retorna bounding box do polígono"""
        points = self.to_points(img_width, img_height)
        x_coords = points[:, 0]
        y_coords = points[:, 1]
        return (
            x_coords.min(), y_coords.min(),
            x_coords.max(), y_coords.max()
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'type': AnnotationType.POLYGON.value,
            'coords': self.coords
        }


@dataclass
class Annotation:
    """Anotação completa de data de validade"""
    crop_id: str
    image_name: str
    subset: str
    box_index: int
    class_id: int
    class_name: str
    geometry: Dict[str, Any]  # BoundingBox ou Polygon serializado
    expiry_date: Optional[str] = None
    expiry_date_raw: Optional[str] = None
    status: AnnotationStatus = AnnotationStatus.PENDING
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para JSON"""
        return {
            'image': self.image_name,
            'subset': self.subset,
            'box_index': self.box_index,
            'class_id': self.class_id,
            'class_name': self.class_name,
            'annotation': self.geometry,
            'expiry_date': self.expiry_date,
            'expiry_date_raw': self.expiry_date_raw,
            'status': self.status.value,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, crop_id: str, data: Dict[str, Any]) -> 'Annotation':
        """Cria anotação a partir de dicionário"""
        return cls(
            crop_id=crop_id,
            image_name=data['image'],
            subset=data['subset'],
            box_index=data['box_index'],
            class_id=data['class_id'],
            class_name=data['class_name'],
            geometry=data['annotation'],
            expiry_date=data.get('expiry_date'),
            expiry_date_raw=data.get('expiry_date_raw'),
            status=AnnotationStatus(data['status']),
            timestamp=data['timestamp']
        )
