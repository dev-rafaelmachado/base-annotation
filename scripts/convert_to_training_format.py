import json
import csv
from pathlib import Path


def convert_annotations_to_csv(annotations_file, output_csv):
    """
    Converte as anotações JSON para CSV para treino de OCR
    Formato: image_path,text
    """
    with open(annotations_file, 'r', encoding='utf-8') as f:
        annotations = json.load(f)

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['crop_id', 'subset', 'image_path',
                        'expiry_date', 'expiry_date_raw', 'class_name', 'status'])

        for crop_id, data in annotations.items():
            if data['status'] == 'anotado' and data['expiry_date']:
                writer.writerow([
                    crop_id,
                    data.get('subset', 'unknown'),
                    f"crops/{crop_id}.jpg",
                    data['expiry_date'],  # Formato ISO: YYYY-MM-DD
                    data.get('expiry_date_raw', ''),  # Texto original
                    data.get('class_name', 'unknown'),
                    data['status']
                ])

    print(f"✓ CSV criado: {output_csv}")
    print(f"  - Coluna 'expiry_date': formato ISO (YYYY-MM-DD)")
    print(f"  - Coluna 'expiry_date_raw': texto original digitado")


def merge_all_annotations(output_path="annotations_output"):
    """Mescla todas as anotações de diferentes subsets em um único arquivo"""
    output_path = Path(output_path)
    all_annotations = {}

    for json_file in output_path.glob("expiry_dates_*.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            annotations = json.load(f)
            all_annotations.update(annotations)
            print(
                f"✓ Carregadas {len(annotations)} anotações de {json_file.name}")

    merged_file = output_path / "expiry_dates_all.json"
    with open(merged_file, 'w', encoding='utf-8') as f:
        json.dump(all_annotations, f, indent=2, ensure_ascii=False)

    print(
        f"\n✓ Total de {len(all_annotations)} anotações mescladas em {merged_file}")
    return merged_file


if __name__ == "__main__":
    output_path = "annotations_output"

    # Converte para CSV
    annotations_file = Path(output_path) / "expiry_dates_all.json"
    output_csv = Path(output_path) / "training_data.csv"

    if annotations_file.exists():
        convert_annotations_to_csv(annotations_file, output_csv)
        print("\n✅ Conversão concluída!")
    else:
        print(f"❌ Arquivo não encontrado: {annotations_file}")
