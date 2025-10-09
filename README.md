# Anotador de Datas de Validade - YOLOv8 (Roboflow)

Script para anotar o **texto das datas de validade** em bounding boxes/polígonos já anotados no Roboflow.

## 🎯 Objetivo

As anotações (polígonos ou bboxes) já estão no Roboflow. Este script:
1. ✅ Lê as coordenadas das anotações (polígonos ou bboxes retangulares)
2. ✅ Mostra a imagem COMPLETA com polígono destacado
3. ✅ Zoom e navegação interativos
4. ✅ Você anota o texto da data
5. ✅ Normaliza e salva no formato ISO (YYYY-MM-DD)

## 🆕 Recursos

### 🎯 Zoom Automático Inteligente
- ✅ **Detecta a região** - Calcula automaticamente o tamanho do polígono/bbox
- ✅ **Zoom ideal** - Aplica zoom para que a região ocupe ~60% da tela
- ✅ **Centralização automática** - Posiciona a câmera no centro da região
- ✅ **Ajuste manual** - Você ainda pode usar Q/E/WASD para ajustar

### Visualização Aprimorada
- ✅ **Terminal limpo** - Limpa a cada nova imagem
- ✅ **Instruções fixas** - Sempre visíveis no topo
- ✅ **Polígonos destacados** - Preenchimento amarelo transparente
- ✅ **Bordas verdes** - Fácil identificação
- ✅ **Atualização em tempo real** - Thread separada

### Controles Estilo Gamer
- ✅ **Q/E** - Zoom in/out (ajuste fino após zoom automático)
- ✅ **WASD** - Movimento da câmera (W=cima, S=baixo, A=esquerda, D=direita)
- ✅ **R** - Reseta zoom, pan, brilho e contraste
- ✅ **B/V** - Aumentar/diminuir brilho
- ✅ **C/X** - Aumentar/diminuir contraste

### Suporte a Polígonos
- ✅ Detecta automaticamente polígonos e bboxes
- ✅ Desenha polígonos na imagem original
- ✅ Mantém contexto completo da imagem

## Workflow

1. **Imagem aparece** - Com zoom automático na região de interesse
2. **Região centralizada** - Foco automático no polígono
3. **Ajuste se necessário** - Use Q/E para zoom, WASD para mover
4. **Digite a data** - No terminal
5. **Próxima imagem** - Novo zoom automático

## Controles Durante Anotação

### Navegação na Imagem
| Tecla/Ação | Função |
|------------|--------|
| `Q` | Aumentar zoom (Zoom In) |
| `E` | Diminuir zoom (Zoom Out) |
| `R` | Resetar zoom, posição, brilho e contraste |
| `W` | Mover para cima |
| `S` | Mover para baixo |
| `A` | Mover para esquerda |
| `D` | Mover para direita |
| `B` | Aumentar brilho |
| `V` | Diminuir brilho |
| `C` | Aumentar contraste |
| `X` | Diminuir contraste |

## Dicas

✅ **Zoom automático** - A região já aparece ampliada e centralizada  
✅ **Ajuste fino** - Use Q/E e WASD se precisar ver mais detalhes  
✅ **Ajuste de imagem** - Use B/V e C/X para melhorar visibilidade  
✅ **R para resetar** - Volta ao zoom automático e configurações padrão  
✅ **Mais rápido** - Não precisa dar zoom manualmente em cada imagem  
✅ **Foco no que importa** - A data já está em destaque  

## Estrutura

