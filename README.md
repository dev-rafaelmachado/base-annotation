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
- ✅ **N/M** - Rotacionar imagem 10° (N=anti-horário, M=horário)
- ✅ **T** - Resetar rotação

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
| **`N`** | **Rotacionar 10° anti-horário (←)** |
| **`M`** | **Rotacionar 10° horário (→)** |
| **`T`** | **Resetar rotação para 0°** |

### Comandos de Anotação (terminal)
| Comando | Ação |
|---------|------|
| `01/02/2025` | Data completa: DD/MM/YYYY |
| `01022025` | Data completa: DDMMYYYY |
| `010225` | Data completa: DDMMYY |
| `02/2025` | Sem dia: MM/YYYY (assume **último dia do mês**) |
| `022025` | Sem dia: MMYYYY (assume **último dia do mês**) |
| `0225` | Sem dia: MMYY (assume **último dia do mês**) |
| `ilegivel` | Marca como não legível |
| `skip` | Pula esta anotação |
| `back` | Desfaz a última anotação |
| `quit` | Salva e encerra |

## Formatos de Data

| Entrada | Interpretação | Salvo como |
|---------|---------------|------------|
| 01/02/2025 | 01 de fevereiro de 2025 | 2025-02-01 |
| 01022025 | 01 de fevereiro de 2025 | 2025-02-01 |
| 010225 | 01 de fevereiro de 2025 | 2025-02-01 |
| **02/2025** | **28 de fevereiro de 2025** | **2025-02-28** |
| **022025** | **28 de fevereiro de 2025** | **2025-02-28** |
| **0225** | **28 de fevereiro de 2025** | **2025-02-28** |
| **02/2024** | **29 de fevereiro de 2024** *(bissexto)* | **2024-02-29** |
| **01/2025** | **31 de janeiro de 2025** | **2025-01-31** |
| **04/2025** | **30 de abril de 2025** | **2025-04-30** |

### 📅 Regras de Último Dia do Mês

Quando o dia não é fornecido, o sistema calcula automaticamente o último dia:
- **Janeiro, Março, Maio, Julho, Agosto, Outubro, Dezembro**: dia 31
- **Abril, Junho, Setembro, Novembro**: dia 30
- **Fevereiro**: dia 28 (ou 29 em anos bissextos)

## Dicas

✅ **Zoom automático** - A região já aparece ampliada e centralizada  
✅ **Ajuste fino** - Use Q/E e WASD se precisar ver mais detalhes  
✅ **Ajuste de imagem** - Use B/V e C/X para melhorar visibilidade  
✅ **Rotação da imagem** - Use N/M para girar em incrementos de 10°  
✅ **R para resetar** - Volta ao zoom automático e configurações padrão  
✅ **T para rotação** - Volta a rotação para 0°  
✅ **Mais rápido** - Não precisa dar zoom manualmente em cada imagem  
✅ **Foco no que importa** - A data já está em destaque  

## Estrutura

## 🔒 Modo Multi-Usuário

### Sistema Seguro para Equipe

✅ **Lock de arquivo** - Evita escrita simultânea  
✅ **Backups automáticos** - A cada salvamento  
✅ **Retry automático** - Tenta novamente se arquivo ocupado  
✅ **Validação de integridade** - Detecta JSON corrompido  
✅ **Restauração de backup** - Recupera dados se necessário  

### Como Usar em Equipe

1. **Clone o repositório** - Todos os membros clonam
2. **Rodem simultaneamente** - Sem problemas!
3. **Sistema sincroniza** - Lock garante segurança
4. **Backups automáticos** - Pasta `backups/` mantém histórico
5. **Merge automático** - Anotações são mescladas

### Arquitetura Multi-Usuário

