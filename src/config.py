"""
Configurações globais do sistema de anotação
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple


@dataclass
class PathConfig:
    """Configurações de caminhos"""
    dataset_path: Path
    output_path: Path
    crops_path: Path
    annotations_file: Path

    def __post_init__(self):
        """Cria diretórios necessários"""
        self.output_path.mkdir(exist_ok=True)
        self.crops_path.mkdir(exist_ok=True)


@dataclass
class DisplayConfig:
    """Configurações de visualização"""
    max_width: int = 1200
    max_height: int = 800
    min_width: int = 400
    min_height: int = 300
    auto_zoom_coverage: float = 0.6  # Região ocupa 60% da tela


@dataclass
class ZoomConfig:
    """Configurações de zoom"""
    min_zoom: float = 0.5
    max_zoom: float = 5.0
    zoom_step: float = 0.2
    pan_step: int = 50


@dataclass
class AnnotationConfig:
    """Configurações de anotação"""
    save_interval: int = 5  # Salva a cada N anotações
    polygon_alpha: float = 0.15  # Transparência do preenchimento
    border_color: Tuple[int, int, int] = (0, 255, 0)  # Verde BGR
    fill_color: Tuple[int, int, int] = (0, 255, 255)  # Amarelo BGR
    border_thickness: int = 2


class Config:
    """Configuração central do sistema"""

    def __init__(self, dataset_path: str, output_path: str = "annotations_output"):
        dataset_path = Path(dataset_path)
        output_path = Path(output_path)

        self.paths = PathConfig(
            dataset_path=dataset_path,
            output_path=output_path,
            crops_path=output_path / "crops",
            annotations_file=output_path / "expiry_dates_all.json"
        )

        self.display = DisplayConfig()
        self.zoom = ZoomConfig()
        self.annotation = AnnotationConfig()
