"""
Ponto de entrada principal do sistema de anotação
"""
from src.utils import DateValidator
from src.ui import DisplayManager, TerminalUI
from src.core import DatasetLoader, ImageProcessor, AnnotationManager
from src.config import Config
import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Função principal"""
    # Configuração
    config = Config(
        dataset_path="rf_export",
        output_path="annotations_output"
    )

    # Inicializa componentes
    loader = DatasetLoader(config.paths.dataset_path)
    processor = ImageProcessor(config.annotation)
    manager = AnnotationManager(config.paths)
    terminal = TerminalUI()
    display = DisplayManager(config.display, config.zoom)

    # Carrega dados
    image_paths = loader.get_all_images()

    if not image_paths:
        print("❌ Nenhuma imagem encontrada")
        return

    # Informações iniciais
    terminal.clear()
    terminal.print_header(
        total_images=len(image_paths),
        already_annotated=len(manager.annotations),
        start_from=0,
        class_names=loader.class_names
    )

    # Inicia interface visual
    display.start()

    try:
        # Loop principal de anotação
        annotation_history = []  # Lista de (idx, img_info, box_idx, box)

        idx = 0
        while idx < len(image_paths):
            img_info = image_paths[idx]
            image_path = img_info['path']
            subset = img_info['subset']
            label_path = img_info['label_path']

            # Carrega imagem
            import cv2
            image = cv2.imread(str(image_path))
            if image is None:
                print(f"⚠️  Erro ao carregar: {image_path.name}")
                idx += 1
                continue

            img_height, img_width = image.shape[:2]

            # Lê anotações
            boxes = loader.read_yolo_label(label_path)
            if not boxes:
                idx += 1
                continue

            # Processa cada box
            box_idx = 0
            went_back = False  # Flag para saber se voltou

            while box_idx < len(boxes):
                box = boxes[box_idx]
                crop_id = f"{subset}_{image_path.stem}_box{box_idx}"

                if manager.is_annotated(crop_id):
                    box_idx += 1
                    continue

                # Prepara visualização
                terminal.clear()
                terminal.print_instructions()

                img_display = processor.draw_annotation(
                    image, box, box_idx, len(boxes)
                )

                # Auto zoom
                display_size = display.get_display_size(img_width, img_height)
                auto_zoom, auto_pan_x, auto_pan_y = processor.calculate_auto_zoom(
                    box, img_width, img_height,
                    display_size[0], display_size[1],
                    config.display.auto_zoom_coverage
                )

                display.set_zoom_pan(auto_zoom, auto_pan_x, auto_pan_y)
                display.update_image(img_display)

                # Salva crop
                crop_path = config.paths.crops_path / f"{crop_id}.jpg"
                cv2.imwrite(str(crop_path), img_display)

                # Mostra informações
                terminal.print_image_info(
                    idx, len(image_paths), subset,
                    image_path.name, box_idx, len(boxes),
                    box['class_name'], box['type'],
                    auto_zoom, crop_path.name
                )

                # Loop de entrada
                should_continue = True
                while should_continue:
                    date_input = input("📅 Data de validade: ").strip()

                    if date_input.lower() == 'quit':
                        manager.save()
                        display.stop()
                        manager.export_summary()
                        return

                    if date_input.lower() == 'back':
                        if annotation_history:
                            # Remove a última anotação
                            prev_idx, prev_img_info, prev_box_idx, prev_box = annotation_history.pop()
                            prev_crop_id = f"{prev_img_info['subset']}_{prev_img_info['path'].stem}_box{prev_box_idx}"

                            manager.remove_annotation(prev_crop_id)
                            print(f"↩️  Voltando para: {prev_crop_id}")

                            # Volta para a imagem/box anterior
                            idx = prev_idx
                            box_idx = prev_box_idx
                            went_back = True
                            should_continue = False
                            break
                        else:
                            print("⚠️  Não há anotações anteriores para voltar")
                            continue

                    if date_input.lower() == 'skip':
                        print("⏭️  Pulando...")
                        box_idx += 1
                        should_continue = False
                        break

                    if date_input.lower() == 'ilegivel':
                        manager.add_illegible(
                            crop_id, image_path.name, subset,
                            box_idx, box
                        )
                        annotation_history.append(
                            (idx, img_info, box_idx, box))
                        print("✓ Marcado como ilegível")
                        box_idx += 1
                        should_continue = False
                        break

                    # Valida e normaliza data
                    if date_input:
                        validator = DateValidator()
                        normalized, is_valid = validator.normalize(date_input)

                        if is_valid:
                            manager.add_annotation(
                                crop_id, image_path.name, subset,
                                box_idx, box, normalized, date_input
                            )
                            annotation_history.append(
                                (idx, img_info, box_idx, box))
                            print(f"✓ Salvo como: {normalized}")
                            box_idx += 1
                            should_continue = False
                            break
                        else:
                            print(
                                "❌ Formato inválido! Use: DD/MM/YYYY, DDMMYYYY ou DDMMYY")
                    else:
                        print("❌ Digite uma data ou comando válido")

                # Se deu back, sai do loop de boxes e recarrega a imagem
                if went_back:
                    break

            # Se deu back, não avança idx (recarrega mesma imagem)
            # Se não deu back, avança para próxima imagem
            if not went_back:
                idx += 1

    finally:
        display.stop()
        manager.save()
        print(f"\n🎉 Concluído! Total: {len(manager.annotations)} anotações")


if __name__ == "__main__":
    main()
