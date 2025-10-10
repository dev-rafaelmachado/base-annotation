"""
Interface de terminal
"""
import os
from typing import Dict


class TerminalUI:
    """Gerencia interface do terminal"""

    def clear(self):
        """Limpa terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(
        self,
        total_images: int,
        already_annotated: int,
        start_from: int,
        class_names: Dict[int, str]
    ):
        """Imprime cabeçalho inicial"""
        print(f"\n📊 Total de imagens: {total_images}")
        print(f"✅ Anotações existentes (JSON): {already_annotated}")
        print(f"🚀 Iniciando a partir da imagem {start_from}")
        print(f"📋 Classes: {class_names}")
        print("\n" + "="*60)
        print("🔒 MODO MULTI-USUÁRIO ATIVO")
        print("✅ Sistema de lock de arquivo ativado")
        print("✅ Backups automáticos habilitados")
        print("✅ Seguro para múltiplos usuários anotando simultaneamente")
        print("="*60)
        self.print_instructions()

    def print_instructions(self):
        """Imprime instruções"""
        print("\n" + "=" * 60)
        print("INSTRUÇÕES:")
        print("- ZOOM: [ Q ] aumentar | [ E ] diminuir | [ R ] resetar")
        print("- MOVER: [ W ] cima | [ S ] baixo | [ A ] esq | [ D ] dir")
        print("- BRILHO: [ B ] aumentar | [ V ] diminuir")
        print("- CONTRASTE: [ C ] aumentar | [ X ] diminuir")
        print("- Digite a data: 01/02/2025 ou 01022025 ou 010225")
        print("  (será salva como: 2025-02-01)")
        print("- 'skip' = pular | 'quit' = sair | 'ilegivel' = não consigo ler")
        print("- 'back' = desfazer última anotação")
        print("=" * 60 + "\n")

    def print_image_info(
        self,
        idx: int,
        total: int,
        subset: str,
        image_name: str,
        box_idx: int,
        total_boxes: int,
        class_name: str,
        box_type: str,
        zoom: float,
        crop_name: str
    ):
        """Imprime informações da imagem atual"""
        print(f"📸 [{idx+1}/{total}] {subset}/{image_name}")
        print(f"📦 Anotação {box_idx+1}/{total_boxes} - Classe: {class_name}")
        print(f"📐 Tipo: {box_type}")
        print(f"🔍 Zoom automático: {zoom:.1f}x")
        print(f"💾 Salvo: {crop_name}\n")
