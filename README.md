# Gerador de treino de musculação com matemática discreta

## Fazendo fork no repositório

Na sua IDE de preferência, abra o terminal e digite o seguinte código:

```
git clone https://github.com/Albuquerque07/discrete-training.git
```

Ele criará uma pasta com os arquivos do portifólio. Entre nela e digite no terminal da pasta:

```
pip install pandas, neo4j, scipy
```

## Entendendo o código

Darei uma ideia inicial em como o algoritmo foi estruturado para que todo processo seja entendido de forma mais leve. Articularei os seguintes pontos:
- Objetivo central
- Estruturação dos dados
- Sobre o Neo4j
- Pré-processamento dos dados
- Gerando treino full-body
- Gerando treino de hipertrofia


### Objetivo central
A ideia é gerar um treino de musculação para o usuário utilizando lógicas centradas na teoria de grafos de matemática discreta. O projeto é tanto um trabalho universitário quanto um projeto pessoal e foi utilizado de organização em POO para melhor estruturação da lógica.

### Estruturação dos dados
Utilizaremos grafos tripartidos para organizar nossos dados da seguinte forma:
![Exemplo de um vértice do grafo tripartido (Vértice de Peitoal)](tripartido_exemplo.png)
* Vértices presentes: "GrupoMuscular" -> "Musculo" -> "Exercicio"

* Arestas: "POSSUI" e "É_ATIVADO"

* Pesos: Nas arestas de "É_ATIVADO" (Sendo de 0 a 1)

Os pesos representam o quanto um Músculo é ativado pelo Exercício a qual se relaciona.

### Sobre o Neo4j
Para garantir uma facilidadde na expansão, adicionamos uma database na nuvém com o Neo4j Aura, o que torna o programa mais escalável e de fácil acesso, além dessa database possuir lógica de grafos ao armazenar e organizar dados (Imagem de cima é da database). A linguagem de comunicação com a database é feita através do Cypher

Toda lógica de gerenciamento da database, no código, é feita pela classe "Neo4jDatabase" que recebe as credenciais de login do server e realiza a ação de verificar e fechar a conexão sempre que for chamada. Ela tem a capacidade de inserir código Cypher no banco, popular com vértices e relacionar os vértices através de arestas (relacionamentos)

### Pré-processamento dos dados

A pesquisa dos pesos em relação a músculos e exercícios foi feita inicialmente em um arquivo Excel. Tais dados foram tratados a partir da classe "ProcessadorDadosTreino" que recebe o local do arquivo. O método "_limpar_e_transformar" irá transformar os dados em um dataframe longo no seguinte formato:

>Múculo Principal   &nbsp;&nbsp;Músculo Secundário  &nbsp;&nbsp;Exercicio  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Peso  
Peitoral  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Peitoral superior  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Supino inclinado 30°  0.40

Daí o método "processar" irá separar os valores em um dataframe de músculos únicos e uma lista de exercícios únicos para melhor serem inseridos na database posteriormente.

### Gerando treino Full-Body

Vinda do método "processar" da classe "ProcessadorDadosTreino", criamos uma matriz de custo com as variáveis: Músculo e Exercício; onde os pesos são cada célula da matriz. Dessa forma, o algoritmo aplica a função linear_sum_assignment que resolve o minimum weight matching problem em grafos bipartidos. Como queremos MAXIMIZAR a relação Grupo x Exercício, passamos a matriz de custo negativada para a função. Com os índices de Grupos e Exercícios que a função retorna nós acessamos os valores na matriz original e criamos uma lista de dicionário com cada dia de treino que foi passado de parâmetro.

### Gerando treino de hipertrofia

Primeiramente, pegamos a matriz de Músculos x Exercícios e limitamos ela apenas aos músculos selecionados na função. Após isso, somamos os scores para cada linha de Músculos e colocamos em ordem decrescente para posteriormente filtrar apenas os k maiores scores de exercícios.

