"""
Entrada principal do sistema de anotação (refatorado)
"""
import sys
from pathlib import Path
import time
from typing import List, Dict, Any, Optional, Tuple

import cv2
from src.utils import DateValidator
from src.ui import DisplayManager, TerminalUI
from src.core import DatasetLoader, ImageProcessor, AnnotationManager
from src.config import Config

# Adiciona src ao path (somente se necessário)
sys.path.insert(0, str(Path(__file__).parent))


def init_components(dataset_path: str, output_path: str):
    """Inicializa configurações e componentes centrais do sistema."""
    config = Config(dataset_path=dataset_path, output_path=output_path)
    loader = DatasetLoader(config.paths.dataset_path)
    processor = ImageProcessor(config.annotation)
    manager = AnnotationManager(config.paths)
    terminal = TerminalUI()
    display = DisplayManager(config.display, config.zoom)
    return config, loader, processor, manager, terminal, display


def load_image(image_path: Path) -> Optional[Any]:
    """Carrega imagem com OpenCV (retorna None em erro)."""
    image = cv2.imread(str(image_path))
    if image is None:
        return None
    return image


def maybe_resize_image(image, max_source_w: int, max_source_h: int) -> Tuple[Any, float]:
    """
    Redimensiona a imagem se for maior que os limites e retorna (image, scale).
    scale é 1.0 se não redimensionou.
    """
    h, w = image.shape[:2]
    scale = 1.0
    if w > max_source_w or h > max_source_h:
        scale = min(max_source_w / w, max_source_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        resized = cv2.resize(image, (new_w, new_h),
                             interpolation=cv2.INTER_AREA)
        return resized, scale
    return image, scale


def convert_autozoom_to_display_space(
    auto_zoom_display: float,
    auto_pan_display_x: int,
    auto_pan_display_y: int,
    img_w: int,
    img_h: int,
    display: DisplayManager
) -> Tuple[float, int, int]:
    """
    Converte valores retornados por ImageProcessor.calculate_auto_zoom (espaço reduzido/display)
    para o espaço que DisplayManager espera (pixels relativos à imagem original com zoom aplicado).
    """
    # display_w/h = tamanho reduzido calculado por display.get_display_size(img_w, img_h)
    display_w, display_h = display.get_display_size(img_w, img_h)

    # scale: quanto a imagem original foi reduzida para o display reduzido
    scale = display_w / float(img_w) if img_w > 0 else 1.0

    # zoom que devemos aplicar à imagem original para obter o mesmo efeito visual
    zoom_for_display = auto_zoom_display * scale

    # pan retornado está em pixels do display reduzido. Precisamos mapear para o espaço do "zoomed original".
    # Compensar diferença entre centro do display reduzido e centro da janela real:
    pan_for_display_x = int(
        round(auto_pan_display_x + (display_w - display.window_width) / 2.0))
    pan_for_display_y = int(
        round(auto_pan_display_y + (display_h - display.window_height) / 2.0))

    # Clamp sensato
    pan_for_display_x = max(0, pan_for_display_x)
    pan_for_display_y = max(0, pan_for_display_y)

    # Proteções de zoom (não permitir <= 0)
    zoom_for_display = max(display.MIN_ZOOM_FOR_SAFETY if hasattr(
        display, "MIN_ZOOM_FOR_SAFETY") else 0.01, float(zoom_for_display))
    if hasattr(display, "zoom_config") and getattr(display.zoom_config, "max_zoom", None):
        zoom_for_display = min(zoom_for_display, display.zoom_config.max_zoom)

    return zoom_for_display, pan_for_display_x, pan_for_display_y


def prompt_and_handle_input(
    terminal: TerminalUI,
    manager: AnnotationManager,
    annotation_history: List[Tuple[int, Dict[str, Any], int, Dict[str, Any]]],
    crop_id: str,
    img_info: Dict[str, Any],
    box_idx: int,
    box: Dict[str, Any],
    display: DisplayManager,
    current_idx: int,
    image_paths_len: int,
    config: Config
) -> Tuple[bool, Optional[int], Optional[int], bool]:
    """
    Prompt loop para o usuário inserir a data/comando.
    Retorna (should_continue_main_loop, new_idx, new_box_idx, went_back)
    - should_continue_main_loop: False se devemos sair do processamento atual da imagem (quando avançar/skip/back etc.)
    - new_idx/new_box_idx: valores para sobrescrever idx e box_idx quando 'back' for usado
    - went_back: True se houve back (necessário para abandonar loops superiores)
    """
    while True:
        date_input = input("📅 Data de validade: ").strip()

        if date_input.lower() == 'quit':
            print("\n💾 Salvando e reconstruindo sumário...")
            manager.save()
            display.stop()
            manager.export_summary(force_rebuild=True)
            exit(0)

        if date_input.lower() == 'back':
            if annotation_history:
                prev_idx, prev_img_info, prev_box_idx, prev_box = annotation_history.pop()
                prev_crop_id = f"{prev_img_info['subset']}_{prev_img_info['path'].stem}_box{prev_box_idx}"
                manager.remove_annotation(prev_crop_id)
                print(f"↩️  Voltando para: {prev_crop_id}")
                return False, prev_idx, prev_box_idx, True
            else:
                print("⚠️  Não há anotações anteriores para voltar")
                continue

        if date_input.lower() == 'skip':
            print("⏭️  Pulando...")
            return False, None, None, False  # avança o box_idx pelo chamador

        if date_input.lower() == 'ilegivel':
            manager.add_illegible(
                crop_id, img_info['path'].name, img_info['subset'], box_idx, box)
            annotation_history.append((current_idx, img_info, box_idx, box))
            print("✓ Marcado como ilegível")
            return False, None, None, False

        if date_input:
            validator = DateValidator()
            normalized, is_valid = validator.normalize(date_input)
            if is_valid:
                manager.add_annotation(
                    crop_id, img_info['path'].name, img_info['subset'], box_idx, box, normalized, date_input)
                annotation_history.append(
                    (current_idx, img_info, box_idx, box))
                print(f"✓ Salvo como: {normalized}")
                time.sleep(config.display.delay)
                return False, None, None, False
            else:
                print("❌ Formato inválido! Use: DD/MM/YYYY, DDMMYYYY ou DDMMYY")
        else:
            print("❌ Digite uma data ou comando válido")


def run_annotation_loop(config: Config, loader: DatasetLoader, processor: ImageProcessor,
                        manager: AnnotationManager, terminal: TerminalUI, display: DisplayManager):
    """
    Loop principal (refatorado). Mantém a lógica de iteração por imagens/boxes e interação com o usuário.
    """
    # Carrega lista de imagens
    image_paths = loader.get_all_images()
    if not image_paths:
        print("❌ Nenhuma imagem encontrada")
        return

    # Carrega anotações existentes
    manager._load_existing()

    # Valida integridade do JSON
    if not manager.validate_json_integrity():
        print("⚠️  JSON corrompido detectado!")
        response = input("Deseja restaurar do backup? (s/n): ")
        if response.lower() == 's':
            if manager.restore_from_backup():
                print("✅ Backup restaurado com sucesso!")
            else:
                print("❌ Nenhum backup disponível")
                return

    # Header
    terminal.clear()
    annotation_count = manager.get_annotation_count()
    terminal.print_header(
        total_images=len(image_paths),
        already_annotated=annotation_count,
        start_from=0,
        class_names=loader.class_names
    )

    # Start display thread
    display.start()

    annotation_history: List[Tuple[int,
                                   Dict[str, Any], int, Dict[str, Any]]] = []

    try:
        idx = 0
        while idx < len(image_paths):
            img_info = image_paths[idx]
            image_path = img_info['path']
            subset = img_info['subset']
            label_path = img_info['label_path']

            image = load_image(image_path)
            if image is None:
                print(f"⚠️  Erro ao carregar: {image_path.name}")
                idx += 1
                continue

            # possivelmente redimensiona a fonte para economizar memória
            image, _scale = maybe_resize_image(
                image, config.display.max_source_width, config.display.max_source_height)
            img_h, img_w = image.shape[:2]

            # Lê anotações
            boxes = loader.read_yolo_label(label_path)
            if not boxes:
                idx += 1
                continue

            box_idx = 0
            went_back = False

            while box_idx < len(boxes):
                box = boxes[box_idx]
                crop_id = f"{subset}_{image_path.stem}_box{box_idx}"

                if manager.is_annotated(crop_id):
                    box_idx += 1
                    continue

                # preparação visual
                terminal.clear()
                terminal.print_instructions()

                img_display = processor.draw_annotation(
                    image, box, box_idx, len(boxes))

                display_w, display_h = display.get_display_size(img_w, img_h)
                # chama a nova função passando também o tamanho real da janela do DisplayManager
                zoom_for_display, pan_for_display_x, pan_for_display_y = processor.calculate_auto_zoom(
                    box, img_w, img_h, display_w, display_h,
                    display.window_width, display.window_height,
                    target_coverage=config.display.auto_zoom_coverage,
                    min_zoom=0.1, max_zoom=config.zoom.max_zoom
                )

                # aplica direto no DisplayManager (agora NÃO precisa converter mais)
                display.set_zoom_pan(
                    zoom_for_display, pan_for_display_x, pan_for_display_y)
                # informe que não quer que update_image re-centre automatic (se estiver usando applyAutoCenter flag)
                display.update_image(img_display, applyAutoCenter=False)

                # salva o crop de visualização (opcional)
                crop_path = config.paths.crops_path / f"{crop_id}.jpg"
                cv2.imwrite(str(crop_path), img_display)

                # mostra info no terminal
                terminal.print_image_info(
                    idx, len(image_paths), subset,
                    image_path.name, box_idx, len(boxes),
                    box.get('class_name', 'N/A'), box.get('type', 'bbox'),
                    zoom_for_display, crop_path.name
                )

                # loop de input do usuário
                should_continue, new_idx, new_box_idx, went_back = prompt_and_handle_input(
                    terminal, manager, annotation_history, crop_id, img_info, box_idx, box,
                    display, idx, len(image_paths), config
                )

                if went_back:
                    # saltar para a imagem/box anterior
                    idx = new_idx if new_idx is not None else idx
                    box_idx = new_box_idx if new_box_idx is not None else 0
                    break

                if should_continue:
                    # caso especial (não usado atualmente) — mantém compatibilidade
                    pass

                # Se não deu back e não houve comandos especiais, avança o box_idx quando necessário:
                # - 'skip' e salvamentos incrementam box_idx pelo chamador (prompt retorna False sem new indices)
                # Aqui detectamos se a última ação salvou/ilegivel/skip pelo tamanho do history
                # Simples e robusto: se a última entrada do histórico é a atual, consideramos salvo/ilegível.
                if annotation_history and annotation_history[-1][0] == idx and annotation_history[-1][2] == box_idx:
                    # já salvo/ilegível, avança
                    box_idx += 1
                else:
                    # Se não foi salvo (skip ou erro), avançar para o próximo box por padrão
                    # (a prompt já tratou 'skip' retornando sem alterar history)
                    # Se o user escolheu 'skip', o prompt devolve sem alteração de history -> avançamos
                    box_idx += 1

            # fim do loop de boxes
            if not went_back:
                idx += 1

    finally:
        display.stop()
        manager.save()
        print("\n📊 Reconstruindo sumário final...")
        manager.export_summary(force_rebuild=True)


def main():
    config, loader, processor, manager, terminal, display = init_components(
        dataset_path="rf_export",
        output_path="annotations_output",
    )
    run_annotation_loop(config, loader, processor, manager, terminal, display)


if __name__ == "__main__":
    main()
