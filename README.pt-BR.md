# Métodos exatos para localização de hubs

[English](README.md) | Português (Brasil)

Autores: [@ValimD](https://github.com/ValimD), [@HenriUz](https://github.com/HenriUz), [@gebra04](https://github.com/gebra04)

Implementação do **Problema da p-Mediana de Hubs Capacitado com r-Alocação (CrApHMP)** para a disciplina de Métodos Exatos (XMAC02). A formulação e os objetivos experimentais seguem o [enunciado do trabalho](trabalho2.pdf).

## Problema

Dado um conjunto de nós que representam origens, destinos e locais candidatos à instalação de hubs, o problema seleciona exatamente **p hubs** e encaminha a demanda por eles para minimizar o custo total de transporte. Cada nó pode ser alocado a, no máximo, **r hubs**, e o fluxo total processado por cada hub deve respeitar sua capacidade.

| Parâmetro     | Significado                                                      |
| ------------- | ---------------------------------------------------------------- |
| n             | Número de nós                                                    |
| w[i,j]        | Demanda de fluxo do nó `i` para o nó `j`                         |
| d[i,j]        | Distância ou custo unitário de transporte de `i` para `j`        |
| p             | Número de hubs a abrir                                           |
| r             | Número máximo de alocações a hubs por nó, com `1 <= r <= p <= n` |
| B[k]          | Capacidade do hub candidato `k`                                  |
| alpha         | Fator de desconto no transporte entre hubs, com `0 < alpha <= 1` |
| lambda, delta | Coeficientes de custo de coleta e distribuição                   |

Uma rota segue o caminho `i -> k -> l -> j`, em que `k` e `l` são hubs. Seu custo unitário de transporte é:

$$
C_{ijkl} = \lambda d_{ik} + \alpha d_{kl} + \delta d_{lj}.
$$

Quando `k = l`, a rota utiliza um único hub. Definir `r = 1` resulta em alocação simples; definir `r = p` permite alocação múltipla a qualquer hub selecionado. Valores intermediários restringem o número de conexões, mantendo maior flexibilidade de roteamento.

### Conjuntos de dados

Os arquivos de entrada disponíveis neste repositório são:

| Conjunto | Arquivos                                 | Descrição                                                                                                               |
| -------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| CAB      | `datasets/CAB25.txt`                     | Fluxos de passageiros e distâncias entre 25 cidades dos EUA; atribuído no enunciado a O'Kelly (1987)                    |
| AP       | `datasets/AP40.txt`, `datasets/AP80.txt` | Instâncias com 40 e 80 nós derivadas de dados do serviço postal australiano; atribuídas a Ernst e Krishnamoorthy (1996) |
| Dummy    | `datasets/dummy/toy1.txt` a `toy8.txt`   | Instâncias pequenas para verificar o modelo e inspecionar a estrutura das soluções                                      |

Cada arquivo de texto contém, nesta ordem:

1. O número de nós `n` na primeira linha.
2. A matriz de demandas `w`, de dimensão `n x n`.
3. A matriz de distâncias `d`, de dimensão `n x n`.
4. Uma linha opcional com as capacidades dos `n` hubs candidatos.

Os valores são separados por espaços em branco. Linhas iniciadas por `#` são comentários.

As demandas de AP podem ser assimétricas (`w[i,j] != w[j,i]`) e apresentar valores positivos na diagonal (`w[i,i] > 0`). A implementação preserva esses valores.

Os arquivos CAB e AP não incluem capacidades. Informe um único valor com `--capacity`; ele será expandido para um vetor de tamanho `n`, atribuindo a mesma capacidade a todos os hubs candidatos. **Se o arquivo incluir uma linha de capacidades, ela terá prioridade sobre `--capacity`.**

## Método

O projeto implementa a formulação de programação linear inteira mista (MILP) do enunciado em **PuLP** e a resolve com o **CBC**.

As variáveis de decisão são:

- `z[i,k]`: variável binária que indica se o nó `i` está alocado ao hub `k`. Um valor diagonal `z[k,k] = 1` indica que o hub `k` está aberto.
- `x[i,j,k,l]`: variável contínua em `[0,1]` que representa a fração da demanda de `i` para `j` encaminhada pelos hubs `k` e `l`.

A função objetivo minimiza o custo total de transporte ponderado pela demanda:

$$
\min \sum_{i,j,k,l \in N} w_{ij} C_{ijkl} x_{ijkl}.
$$

As restrições garantem exatamente `p` hubs abertos, alocação apenas a hubs abertos, no máximo `r` alocações por nó, roteamento completo de cada fluxo entre origem e destino e consistência entre rotas e alocações. As capacidades consideram o fluxo processado pelo hub tanto na primeira quanto na segunda posição da rota; uma rota com `k = l` consome a capacidade desse hub apenas uma vez.

A implementação cria `n²` variáveis binárias de alocação e `n⁴` variáveis contínuas de roteamento. Por isso, a construção do modelo e o consumo de memória podem ser elevados em instâncias maiores.

A interface de experimentos utiliza `lambda = delta = 1`. Os status são apresentados diretamente conforme `pulp.LpStatus[prob.status]`.

## Arquitetura

O projeto separa a construção do modelo, a resolução, a coordenação dos experimentos e a visualização.

| Arquivo            | Responsabilidade                                                               |
| ------------------ | ------------------------------------------------------------------------------ |
| `src/build.py`     | Ler a instância e construir o modelo MILP                                      |
| `src/main.py`      | Construir e resolver um caso; extrair alocações e rotas; exportar DOT          |
| `experiments.sh`   | Percorrer sequencialmente os conjuntos de dados e as combinações de parâmetros |
| `src/visualize.py` | Gerar um relatório HTML a partir dos arquivos JSON dos experimentos            |

Para cada combinação de parâmetros, `experiments.sh` inicia `src/main.py --experiment`. A própria `main.py` executa o caso e grava suas saídas. A função `solve_problem` constrói o modelo por meio de `src/build.py` e executa o CBC usando `COIN_CMD`. O executável CBC deve estar instalado no sistema e disponível como `cbc` no PATH. Após os experimentos, `src/visualize.py` lê os arquivos JSON salvos para gerar o relatório HTML.

## Instalação

Utilize **Python 3.12 ou superior** e **Bash 4 ou superior**. Execute os comandos a seguir na raiz do repositório. Os exemplos de shell são destinados ao Linux ou a um ambiente compatível, como o WSL.

**Recomendado: uv**

Com o `uv` instalado, sincronize o ambiente usando o arquivo de versões fixadas (`uv.lock`) incluído no repositório:

```bash
uv sync --locked
```

Isso cria `.venv` e instala as dependências do projeto. Os comandos Python podem então ser executados com `uv run`.

**Alternativa: pip**

Crie e ative um ambiente virtual. Em seguida, instale as dependências dentro das faixas de versões declaradas em `pyproject.toml`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'numpy>=2.5.4' 'pulp[cbc]>=3.3,<4'
```

A alternativa com pip segue as faixas declaradas, mas não reproduz as versões exatas de `uv.lock`. Mantenha o limite superior de versão do PuLP: o código atual utiliza a API de solvers do PuLP 3.x.

## Uso

Execute os comandos na raiz do repositório. O script `experiments.sh` seleciona automaticamente o interpretador `.venv/bin/python` do projeto e, se ele não estiver disponível, utiliza `python3`. Você pode definir outro interpretador por meio da variável de ambiente `PYTHON`.

**Executar uma pequena combinação de parâmetros**

```bash
bash experiments.sh datasets/dummy/toy1.txt \
  --p 1 2 \
  --alpha 0.25 0.5 1.0
```

Sem `--r`, o script testa todos os inteiros de `1` até o valor atual de `p`. Para selecionar limites de alocação específicos, informe uma lista como `--r 1 2`.

| Opção                | Significado                                              | Padrão                                 |
| -------------------- | -------------------------------------------------------- | -------------------------------------- |
| `--p INTEGER...`     | Quantidades de hubs                                      | `1 2`                                  |
| `--r INTEGER...`     | Limites de alocação                                      | Todos os inteiros de `1` até cada `p`  |
| `--alpha NUMBER...`  | Fatores de desconto entre hubs                           | `0.25 0.5 1.0`                         |
| `--capacity NUMBER`  | Capacidade uniforme quando ausente no arquivo de entrada | Usar a linha de capacidades do arquivo |
| `--output DIRECTORY` | Diretório que receberá as sessões de experimentos        | `results`                              |

Coloque os caminhos das instâncias antes das opções. O script inicia um processo Python separado para cada instância e combinação válida de `(p, r, alpha)`, aguardando sua conclusão antes de iniciar o próximo. Combinações com `p > n` ou `r > p` são ignoradas.

**Executar CAB e AP com capacidades uniformes**

Por exemplo, os comandos abaixo atribuem capacidade `1000000` a cada hub candidato. Esse valor é ilustrativo e não constitui uma configuração experimental calibrada; escolha capacidades de acordo com a escala das demandas de cada conjunto de dados e com o grau desejado de restrição da capacidade.

```bash
bash experiments.sh datasets/CAB25.txt \
  --p 2 --r 1 2 --alpha 0.5 \
  --capacity 1000000

bash experiments.sh datasets/AP40.txt datasets/AP80.txt \
  --p 2 --r 1 2 --alpha 0.5 \
  --capacity 1000000
```

Para estudar o efeito de capacidades mais restritas, execute novamente o script com outros valores de `--capacity`. Para arquivos que contêm uma linha de capacidades, altere essa linha ou utilize uma cópia separada da instância, pois o valor informado na linha de comando não a substitui.

**Arquivos de saída**

Cada instância recebe um diretório de sessão cujo nome inclui o nome da instância e os parâmetros informados. Para o primeiro exemplo:

```text
results/toy1_p-1-2_r-auto_alpha-0.25-0.5-1.0_capacity-file/
```

Sessões repetidas recebem sufixos como `__run2`, preservando as saídas anteriores. Cada sessão contém:

- `summary.csv`: uma linha por caso, com parâmetros, capacidades efetivamente utilizadas, status, valor da função objetivo e tempos de execução.
- Um `.json` por caso: metadados, hubs, alocações, frações de roteamento e cargas dos hubs.
- Um `.cbc.log` por execução do solver: registro de execução do CBC.
- Um `.cbc.dot` por execução: alocações e fluxos agregados entre hubs.

O DOT representa o grafo da rede, enquanto o JSON mantém as frações detalhadas de roteamento utilizadas pelo relatório interativo. Os valores e grafos são exportados independentemente do status; consulte o status ao interpretar cada execução.

**Gerar o relatório HTML**

Com uv:

```bash
uv run python src/visualize.py results --output results/report.html
```

Com o ambiente do pip ativado:

```bash
python src/visualize.py results --output results/report.html
```

Abra `results/report.html` em um navegador. O relatório inclui uma tabela com todos os casos carregados e grafos interativos das soluções de instâncias armazenadas em um diretório `dummy`. Esses grafos permitem inspecionar alocações e rotas de um par origem-destino selecionado. Também é possível informar um único arquivo JSON ou o diretório de uma sessão específica no lugar de `results`.

**Executar um único caso diretamente**

Para gerar as mesmas saídas de experimento sem percorrer combinações de parâmetros:

```bash
uv run python src/main.py --experiment datasets/dummy/toy1.txt \
  --p 2 --r 1 --alpha 0.5 --session results/single-case
```

Com pip, substitua `uv run python` por `python` após ativar `.venv`.

## Resultados

Os resultados estão organizados por instância e parâmetro variado. `Objective` é o valor da função objetivo, `Time` é o tempo de resolução em segundos, `hubs` lista os nós selecionados e `flow` apresenta o fluxo processado por cada hub no formato `hub:fluxo`.

### CAB25

#### Variação de p e r

O primeiro teste utilizou `p = r = 1` e retornou um problema infactível. Em seguida, foram fixados `alpha = 0.5` e capacidade uniforme `B = 5693337`, variando `r` de `1` até `p` para `p = 3` e `p = 5`.

**Três hubs (`p = 3`)**

| Status | Objective | Time | p | r | hubs | flow |
| --- | --- | --- | --- | --- | --- | --- |
| Optimal | 8265432321.2787895 | 66.8389 | 3 | 1 | 3 11 17 | 3:5298722.0000 11:2280048.0000 17:5565268.0000 |
| Optimal | 7743535829.674574 | 42.0576 | 3 | 2 | 3 11 17 | 3:4184606.0000 11:2126618.0000 17:4964292.0000 |
| Optimal | 7742162357.846508 | 44.1111 | 3 | 3 | 3 11 17 | 3:4149854.0000 11:2126618.0000 17:4964292.0000 |

O aumento de `r` reduziu o custo, mantendo os hubs `3`, `11` e `17`. Os fluxos por hub diminuíram ou permaneceram iguais entre essas execuções, com a maior redução de custo na passagem de `r = 1` para `r = 2`.

**Cinco hubs (`p = 5`)**

| Status | Objective | Time | p | r | hubs | flow |
| --- | --- | --- | --- | --- | --- | --- |
| Optimal | 6764854460.072403 | 27.3185 | 5 | 1 | 3 6 11 13 16 | 3:4303060.0000 6:1489344.0000 11:2280048.0000 13:1221994.0000 16:4977634.0000 |
| Optimal | 6425607096.02948 | 136.5285 | 5 | 2 | 3 6 11 13 16 | 3:3473250.0000 6:1475238.0000 11:2066056.0000 13:1241966.0000 16:4787750.0000 |
| Optimal | 6365597976.784062 | 112.328 | 5 | 3 | 3 6 11 13 16 | 3:3402552.0000 6:1255944.0000 11:2066056.0000 13:1241966.0000 16:4787750.0000 |
| Optimal | 6346590993.705497 | 25.7976 | 5 | 4 | 3 6 11 13 16 | 3:3320122.0000 6:1320474.0000 11:2068704.0000 13:1221994.0000 16:4787750.0000 |
| Optimal | 6346590993.705497 | 19.2262 | 5 | 5 | 3 6 11 13 16 | 3:3320122.0000 6:1320474.0000 11:2068704.0000 13:1221994.0000 16:4787750.0000 |

Os hubs selecionados permaneceram os mesmos nas cinco execuções. O custo diminuiu até `r = 4`; passar para `r = 5` não alterou o objetivo nem os fluxos registrados. A redistribuição não reduz necessariamente o fluxo de cada hub: alguns recebem mais fluxo conforme `r` aumenta.

Nos casos apresentados, aumentar a quantidade de hubs e permitir mais alocações reduziu o custo de transporte, mas não produziu uma relação monotônica com o tempo de resolução. Para `p = 5`, por exemplo, o tempo subiu de `27.3185` para `136.5285` segundos entre `r = 1` e `r = 2`, e depois caiu nas execuções seguintes.

#### Variação de alpha

Foram fixados `p = r = 3` e capacidade uniforme `B = 5693337`, variando `alpha` de `0.1` a `0.7`.

| Status | Objective | Time | p | r | hubs | flow | alpha |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Optimal | 5930142707.276142 | 3420.243 | 3 | 3 | 3 11 16 | 3:5185556 11:2280048 16:5401480 | 0.1 |
| Optimal | 6429833196.403355 | 181.0848 | 3 | 3 | 11 16 20 | 11:2280048 16:5029756 20:4687522 | 0.2 |
| Optimal | 6902464548.067425 | 34.5468 | 3 | 3 | 3 11 16 | 3:4715754 11:2280048 16:4828986 | 0.3 |
| Optimal | 7341296104.181466 | 34.5253 | 3 | 3 | 3 11 16 | 3:4430308 11:2280048 16:4828986 | 0.4 |
| Optimal | 7742162357.846508 | 29.2235 | 3 | 3 | 3 11 17 | 3:4149854 11:2126618 17:4964292 | 0.5 |
| Optimal | 8106433107.063498 | 163.4828 | 3 | 3 | 3 11 16 | 3:4327404 11:2126618 16:4520486 | 0.6 |
| Optimal | 8424995470.809603 | 169.9717 | 3 | 3 | 3 11 16 | 3:4148906 11:2008080 16:4413484 | 0.7 |

O custo aumentou em todas as etapas conforme `alpha` cresceu. Isso corresponde ao aumento do coeficiente de transporte entre hubs: quanto maior `alpha`, menor o desconto nesse trecho. A alteração também mudou os hubs selecionados em algumas execuções. O tempo não acompanhou uma tendência monotônica; a execução com `alpha = 0.1` foi a mais demorada, com `3420.243` segundos.

#### Variação da capacidade B

Foram mantidos `p = r = 3` e `alpha = 0.5`, atribuindo a mesma capacidade `B` a todos os hubs candidatos.

| Status | Objective | Time | B | hubs | flow |
| --- | --- | --- | --- | --- | --- |
| Optimal | 9227986396.814335 | 476.6093 | 3000000 | 4 7 16 | 4:3000000 7:2991628 16:3000000 |
| Optimal | 7742162357.846508 | 29.2235 | 5693337 | 3 11 17 | 3:4149854 11:2126618 17:4964292 |
| Optimal | 7742162357.846508 | 30.9537 | 8000000 | 3 11 17 | 3:4149854 11:2126618 17:4964292 |

Os testes com `B = 1000000` e `B = 2000000` produziram problemas infactíveis. Com `B = 3000000`, a solução selecionou os hubs `4`, `7` e `16`, e os hubs `4` e `16` atingiram suas capacidades. Essa configuração apresentou custo maior que as duas configurações de capacidade mais alta.

Capacidades menores tornam as restrições mais severas e podem exigir outras localizações de hubs ou impedir a existência de uma solução viável. Já o aumento de `B = 5693337` para `B = 8000000` não alterou os hubs, os fluxos nem o objetivo registrados: a capacidade adicional não trouxe redução de custo nesses testes.

### Instâncias AP

As instâncias testadas foram **AP40 e AP80**. A intenção era repetir as variações realizadas para CAB25, mas ambas esgotaram a memória RAM nas máquinas utilizadas. Durante os testes, as máquinas travavam e encerravam o processo Python, impedindo a conclusão das execuções. Por isso, não são apresentados custos ou tempos de resolução para essas instâncias.
