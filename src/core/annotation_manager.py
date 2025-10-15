"""
Gerenciamento de anotações com suporte a múltiplos usuários
"""
import json
import shutil
from pathlib import Path
import time
from typing import Dict, Any
from datetime import datetime
from ..models import Annotation, AnnotationStatus
from ..config import PathConfig
from ..utils import FileLock


class AnnotationManager:
    """Gerencia anotações de datas de validade com segurança para múltiplos usuários"""

    def __init__(self, paths: PathConfig):
        self.paths = paths
        self.annotations: Dict[str, Annotation] = {}
        self.lock_file = paths.output_path / ".annotations.lock"
        self.backup_dir = paths.output_path / "backups"
        self.backup_dir.mkdir(exist_ok=True)

    def _load_existing(self):
        """Carrega anotações existentes do JSON"""
        self.annotations.clear()  # Limpa antes de carregar
        if self.paths.annotations_file.exists():
            with open(self.paths.annotations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for crop_id, ann_data in data.items():
                    self.annotations[crop_id] = Annotation.from_dict(
                        crop_id, ann_data)

    def is_annotated(self, crop_id: str) -> bool:
        """Verifica se crop já foi anotado (consulta JSON se necessário)"""
        # Se não está em memória, carrega do JSON
        if not self.annotations and self.paths.annotations_file.exists():
            self._load_existing()
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

    def _create_backup(self):
        """Cria backup do arquivo JSON antes de salvar"""
        if self.paths.annotations_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"expiry_dates_{timestamp}.json"
            shutil.copy2(self.paths.annotations_file, backup_file)

            # Mantém apenas últimos 10 backups
            backups = sorted(self.backup_dir.glob("expiry_dates_*.json"))
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    old_backup.unlink()

    def save(self, max_retries: int = 3):
        """
        Salva todas as anotações com lock de arquivo

        Args:
            max_retries: Número máximo de tentativas
        """
        for attempt in range(max_retries):
            try:
                # Tenta adquirir lock
                with FileLock(self.lock_file, timeout=10):
                    # Cria backup antes de salvar
                    self._create_backup()

                    # Carrega dados existentes
                    existing_annotations = {}
                    if self.paths.annotations_file.exists():
                        try:
                            with open(self.paths.annotations_file, 'r', encoding='utf-8') as f:
                                existing_data = json.load(f)
                                for crop_id, ann_data in existing_data.items():
                                    existing_annotations[crop_id] = ann_data
                        except (json.JSONDecodeError, IOError) as e:
                            print(f"⚠️  Erro ao ler JSON existente: {e}")

                    # Mescla com anotações em memória
                    for crop_id, ann in self.annotations.items():
                        existing_annotations[crop_id] = ann.to_dict()

                    # Salva atomicamente (escreve em temp, depois move)
                    temp_file = self.paths.annotations_file.with_suffix('.tmp')
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(existing_annotations, f,
                                  indent=2, ensure_ascii=False)

                    # Move atomicamente
                    temp_file.replace(self.paths.annotations_file)

                    print(
                        f"\n✓ Anotações salvas: {self.paths.annotations_file}")
                    return

            except TimeoutError:
                if attempt < max_retries - 1:
                    print(
                        f"⏳ Aguardando outros usuários... (tentativa {attempt + 1}/{max_retries})")
                    time.sleep(1)
                else:
                    print(
                        "❌ Não foi possível salvar - outro usuário está usando o arquivo")
                    print(
                        "💡 Suas anotações estão em memória. Tente novamente em instantes.")
            except Exception as e:
                print(f"❌ Erro ao salvar: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)

    def validate_json_integrity(self) -> bool:
        """Valida integridade do arquivo JSON"""
        if not self.paths.annotations_file.exists():
            return True

        try:
            with open(self.paths.annotations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Valida estrutura básica
                if not isinstance(data, dict):
                    return False

                # Valida cada anotação
                for crop_id, ann_data in data.items():
                    required_fields = [
                        'image', 'subset', 'class_name', 'status']
                    if not all(field in ann_data for field in required_fields):
                        return False

                return True
        except Exception as e:
            print(f"⚠️  Erro na validação: {e}")
            return False

    def restore_from_backup(self):
        """Restaura do backup mais recente"""
        backups = sorted(self.backup_dir.glob(
            "expiry_dates_*.json"), reverse=True)

        if backups:
            latest_backup = backups[0]
            print(f"🔄 Restaurando do backup: {latest_backup.name}")
            shutil.copy2(latest_backup, self.paths.annotations_file)
            self._load_existing()
            return True

        return False

    def get_annotation_count(self) -> int:
        """Retorna contagem de anotações do JSON (sempre atualizado)"""
        # Recarrega do JSON para garantir contagem correta
        if self.paths.annotations_file.exists():
            try:
                with open(self.paths.annotations_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return len(data)
            except (json.JSONDecodeError, IOError):
                pass
        return 0

    def export_summary(self, force_rebuild: bool = False):
        """
        Exporta resumo estatístico

        Args:
            force_rebuild: Se True, reconstrói sumário do zero baseado no JSON
        """
        if force_rebuild:
            # Recarrega anotações do JSON para garantir dados atualizados
            self._load_existing()

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

        print(f"\n📊 Resumo reconstruído: {summary_file}")
        print(
            f"📈 Total: {total} | Legíveis: {annotated} | Ilegíveis: {illegible}")
