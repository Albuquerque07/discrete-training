import pandas as pd
from neo4j import GraphDatabase


import pandas as pd
from neo4j import GraphDatabase

class ProcessadorDadosTreino:
    """
    Lida com o processamento e limpeza dos dados vindos do EXCEL.
    """
    def __init__(self, filepath):
        try:
            self.df = pd.read_excel(filepath)
            print("Arquivo Excel carregado com sucesso.")
        except Exception as e:
            print(f"Erro ao ler o arquivo {filepath}: {e}")
            raise
        
        self.dados_longos = None
        self.musculos_unicos = None
        self.exercicios_unicos = None

    def _limpar_e_transformar(self):


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
        self.dados_longos = self._limpar_e_transformar()
        
        self.musculos_unicos = self.dados_longos[
            ['Múculo Principal', 'Músculo Secundário']
        ].drop_duplicates()
        
        self.exercicios_unicos = self.dados_longos['Exercicio'].drop_duplicates().tolist()
        
        return self


class Neo4jDatabase:
    """Controla as operações para a database do Neo4j"""

    def __init__(self, uri, auth):
        """Inicializa as variáveis a serem usadas"""
        self.uri = uri
        self.auth = auth
        self.driver = None

    def connect(self):
        """Conecta ao banco de dados do Neo4j via núvem"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=self.auth)
            self.driver.verify_connectivity()
            print("Conexão com Neo4j Aura estabelecida com sucesso.")
        except Exception as e:
            print(f"Falha ao conectar no Neo4j: {e}")
            raise

    def close(self):
        """Fecha a conexão com o banco"""
        if self.driver:
            self.driver.close()
            print("Conexão com Neo4j fechada.")

    def __enter__(self):
        """Conecta com o banco de dados ao acessar a classe"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Fecha a conexão com o banco ao terminar as operações com o banco"""
        self.close()

    def _run_query(self, query, **params):
        """Roda o código CYPHER na query do banco de dados"""

        if not self.driver:
            raise Exception("Driver não está conectado.")
        
        with self.driver.session(database="neo4j") as session:
            try:
                result = session.run(query, **params)
                return [record for record in result]
            except Exception as e:
                print(f"Erro query: {e}")
                return None

    def limpar_banco(self):
        """Limpa as informações antigas do banco"""
        print("Limpando o banco de dados...")

        # String que irá se comunicar com o banco de dados pela linguagem CYPHER
        query = "MATCH (n) DETACH DELETE n"
        self._run_query(query)
        print("Banco de dados limpo.")

    def popular_grupos_e_musculos(self, musculos_df):
        """Transforma o df de músculos em um dicionário e o insere no banco de dados de uma vez só"""
        print(f"Enviando lote de {len(musculos_df)} músculos para a nuvem...")
        
        # Converte o DataFrame para uma lista de dicionários, evitando várias chamadas ao banco de dados
        batch_data = musculos_df.rename(columns={
            'Múculo Principal': 'grupo', 
            'Músculo Secundário': 'subgrupo'
        }).to_dict('records')

        # String que irá se comunicar com o banco de dados pela linguagem CYPHER
        query = """
        UNWIND $batch AS row
        MERGE (g:GrupoMuscular {nome: row.grupo})
        MERGE (m:Musculo {nome: row.subgrupo})
        MERGE (g)-[:POSSUI]->(m)
        """
        self._run_query(query, batch=batch_data)
        print("Vértices de Músculos e Grupos criados.")

    def popular_exercicios(self, exercicios_lista):
        """Insere a lista de exercícios recebida no banco do Neo4j Aura"""

        print(f"Enviando lote de {len(exercicios_lista)} exercícios...")
        
        # String que irá se comunicar com o banco de dados pela linguagem CYPHER
        query = """
        UNWIND $nomes AS nome_exercicio
        MERGE (e:Exercicio {nome: nome_exercicio})
        """
        self._run_query(query, nomes=exercicios_lista)
        print("Nós de Exercícios criados.")

    def criar_relacionamentos_ativacao(self, dados_longos_df):
        """Cria arestas de relacionamento entre os vértices de musculo e exercícios"""

        print(f"Enviando lote de {len(dados_longos_df)} relacionamentos...")
        
        batch_data = dados_longos_df.rename(columns={
            'Exercicio': 'exercicio',
            'Músculo Secundário': 'musculo',
            'Peso': 'peso'
        }).to_dict('records')

        # String que irá se comunicar com o banco de dados pela linguagem CYPHER
        query = """
        UNWIND $batch AS row
        MATCH (e:Exercicio {nome: row.exercicio})
        MATCH (m:Musculo {nome: row.musculo})
        MERGE (m)-[r:É_ATIVADO]->(e)
        SET r.peso = row.peso
        """
        self._run_query(query, batch=batch_data)
        print("Relacionamentos de ativação criados com sucesso.")



# Driver Code

URI = "neo4j+s://87ac44c9.databases.neo4j.io"
AUTH = ("neo4j", "qP5nlLhuF1ELaAXiEL2hv0wTAqTuz436Hvqs9TNVkRQ")
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