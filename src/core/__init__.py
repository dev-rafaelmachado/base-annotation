"""
Núcleo do sistema de anotação
"""
from .dataset_loader import DatasetLoader
from .image_processor import ImageProcessor
from .annotation_manager import AnnotationManager

__all__ = ['DatasetLoader', 'ImageProcessor', 'AnnotationManager']
