import pandas as pd
from neo4j import GraphDatabase


class ProcessadorDadosTreino:
    """
        Lida com o processamento e limpeza dos dados vindos do EXCEL
    """
    def __init__(self, filepath):
        """
        Lê o arquivo excel e inicializa as variáveis a serem utilizadas

        Args:
            filepath (_type_): Caminho para acessar arquivo (.xlsx).
        """
        try:
            self.df = pd.read_excel(filepath)
            print("Arquivo Excel carregado com sucesso.")
        except Exception as e:
            print(f"Erro ao ler o arquivo {filepath}: Detalhe: {e}")
            raise
        
        self.dados_longos = None
        self.musculos_unicos = None
        self.exercicios_unicos = None

    def _limpar_e_transformar(self):
        """
            Trata os dados do EXCEL e os pivota com a função melt.
        """
        
        self.df['Múculo Principal'] = self.df['Múculo Principal'].ffill()
        
        df_long = self.df.melt(
            id_vars=['Múculo Principal', 'Músculo Secundário'],
            var_name='Exercicio',
            value_name='Peso'
        )
      
        df_long = df_long.dropna(subset=['Peso'])
        
        df_long = df_long[df_long['Peso'] > 0]
        
        df_long['Peso'] = pd.to_numeric(df_long['Peso'])
        
        print(f"Dados processados: {len(df_long)} relacionamentos encontrados.")
        return df_long

    def processar(self):
        """
            Processa os dados longos do df e retorna uma tupla dos valores preparados para serem inseridos na database
        """
        self.dados_longos = self._limpar_e_transformar()
        
        self.musculos_unicos = self.dados_longos[
            ['Múculo Principal', 'Músculo Secundário']
        ].drop_duplicates()
        
        self.exercicios_unicos = self.dados_longos['Exercicio'].drop_duplicates().tolist()
        
        return self


class Neo4jDatabase:

    """Controla as operações para a database  do Neo4j"""

    def __init__(self, uri, auth):
        """Inicializa as variáveis a serem utilizadas"""

        self.uri = uri
        self.auth = auth
        self.driver = None

    def connect(self):
        """Verifica a conexão com o banco"""

        try:
            self.driver = GraphDatabase.driver(self.uri, auth=self.auth)
            self.driver.verify_connectivity()
            print("Conexão com Neo4j estabelecida com sucesso.")
        except Exception as e:
            print(f"Falha ao conectar no Neo4j: {e}")
            raise

    def close(self):
        """Fecha a conexão com o banco de dados"""

        if self.driver:
            self.driver.close()
            print("Conexão com Neo4j fechada.")

    def __enter__(self):
        """Permite o uso do with statement para a classe Principal ao chamar o método "connect" ao entrar"""

        self.connect()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        """Permite o uso do with statement para classe Principalao chamar o método "close" ao sair"""

        self.close()


    def _run_query(self, query, **params):
        """Roda o código CYPHER na database"""

        if not self.driver:
            raise Exception("Driver não está conectado. Chame connect() primeiro.")
        
        with self.driver.session(database="neo4j") as session:
            try:
                result = session.run(query, **params)
                return [record for record in result]
            except Exception as e:
                print(f"Erro ao executar query: {query} \nParams: {params} \nErro: {e}")
                return None
            
    
    def limpar_banco(self):
        """Deleta antigos dados da database"""

        print("Limpando o banco de dados...")
        query = "MATCH (n) DETACH DELETE n"
        self._run_query(query)
        print("Banco de dados limpo.")


    def popular_grupos_e_musculos(self, musculos_df):
        """Insere o  conjunto de dados passados em dataframe na database"""

        print(f"Populando {len(musculos_df)} músculos e grupos...")
        query = """
        MERGE (g:GrupoMuscular {nome: $grupo_primario})
        MERGE (m:Musculo {nome: $musculo_secundario})
        MERGE (g)-[:POSSUI]->(m)
        """
        for _, row in musculos_df.iterrows():
            self._run_query(
                query,
                grupo_primario=row['Múculo Principal'],
                musculo_secundario=row['Músculo Secundário']
            )
        print("Vértices de Músculos e Grupos criados.")


    def popular_exercicios(self, exercicios_lista):
        """Cria os nós (:Exercicio)."""
        print(f"Populando {len(exercicios_lista)} exercícios...")
        query = "MERGE (e:Exercicio {nome: $nome_exercicio})"
        for exercicio in exercicios_lista:
            self._run_query(query, nome_exercicio=exercicio)
        print("Nós de Exercícios criados.")

    def criar_relacionamentos_ativacao(self, dados_longos_df):
        """
        """
        print(f"Criando {len(dados_longos_df)} relacionamentos de ativação...")
        query = """
        MATCH (e:Exercicio {nome: $nome_exercicio})
        MATCH (m:Musculo {nome: $musculo_secundario})
        MERGE (m)-[r:É_ATIVADO]->(e)
        SET r.peso = $peso
        """
        count = 0
        for _, row in dados_longos_df.iterrows():
            self._run_query(
                query,
                nome_exercicio=row['Exercicio'],
                musculo_secundario=row['Músculo Secundário'],
                peso=row['Peso']
            )
            count += 1
            if count % 100 == 0:
                print(f"  ... {count} relacionamentos criados ...")
        
        print("Relacionamentos de ativação criados com sucesso.")





# Driver Code

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "DiscreteTraining")
ARQUIVO_DADOS = "Training_Data.xlsx" 

if __name__ == "__main__":
    print("Inicializando processo de geração de treino...")
    
    try:
        dados_processados = ProcessadorDadosTreino("Training_Data.xlsx").processar()
        
        with Neo4jDatabase(URI, AUTH) as db:
            
            db.limpar_banco()
            
            db.popular_grupos_e_musculos(dados_processados.musculos_unicos)
            db.popular_exercicios(dados_processados.exercicios_unicos)
            
            db.criar_relacionamentos_ativacao(dados_processados.dados_longos)
            
        print("Banco de dados foi carregado com sucesso.")

    except Exception as e:
        print(f"### Ocorreu um erro fatal: {e} ###")