import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from neo4j import GraphDatabase

try:
    from database import Neo4jDatabase, ProcessadorDadosTreino
except ImportError:
    print("Certifique-se que o arquivo com as classes Neo4jDatabase e ProcessadorDadosTreino se chama 'database.py'")
    exit()

class GeradorTreino:
    """Organiza todos os treinos """

    def __init__(self, db_driver):
        """
        Inicializa o gerador com um driver do Neo4j já conectado.

        Args:
            db_driver (neo4j.Driver): O driver do Neo4j.
        """
        if not db_driver:
            raise ValueError("O driver do Neo4j é necessário.")
        self.driver = db_driver
        self.matriz_custo_df = None
        print("Gerador de Treino inicializado e conectado ao banco.")

    def _criar_matriz_com_pesos(self):
        """Cria uma matriz com os grupos principais, exercício e seus respectivos pesos somados"""
        
        query = """
        MATCH (g:GrupoMuscular)-[:POSSUI]->(m:Musculo)-[r:É_ATIVADO]->(e:Exercicio)
        RETURN g.nome AS Grupo, e.nome AS Exercicio, SUM(r.peso) AS ScoreTotal
        """
        with self.driver.session(database="neo4j") as session:
            results = session.run(query)
            data = [record.data() for record in results]
        
        if not data:
            raise Exception("Erro ao gerar a matriz. Verifique os valores da sua database")

        # Pivota os dados para criar a matriz Grupo x Exercício
        df = pd.DataFrame(data)
        self.matriz_custo_df = df.pivot(
            index='Grupo', 
            columns='Exercicio', 
            values='ScoreTotal'
        ).fillna(0)
        
        print(f"Matriz gerada com ({self.matriz_custo_df.shape[0]} grupos, {self.matriz_custo_df.shape[1]} exercícios)")


    def gerar_treino_full_body(self, dias_por_semana: int, grupos_alvo=None):
        """
        Gera treinos 'Full Body' para (N) dias, usando o Problema de Alocação
        para maximizar o score MVIC, garantindo variedade.

        Args:
            dias_por_semana (int): Quantos treinos (A, B, C...) gerar.
            grupos_alvo (list, optional): Lista de grupos a treinar. 
                                         Se None, usa os principais.
        """
        
        if self.matriz_custo_df is None:
            self._criar_matriz_com_pesos()

        if grupos_alvo is None:
            grupos_alvo = [
                'Peitoral', 'Ombro', 'Triceps', 'Biceps', 
                'Ante-braço', 'Costas', 'Abdômen', 'Quadríceps',
                'Posterior', 'Adutor', 'Panturrilha', 'Glúteo'
            ]
        
        matriz_focada = self.matriz_custo_df.loc[grupos_alvo]
        
        #Colocando o negativo pois a função do scipy minimiza, ao invés de maximizar
        matriz_custo_negativa = -(matriz_focada.copy())

        treinos_gerados = {}
        exercicios_ja_usados = []

        for dia in range(dias_por_semana):
            dia_label = chr(ord('A') + dia)
            
            if exercicios_ja_usados:
                matriz_custo_negativa[exercicios_ja_usados] = 999999 

            grupos_indices, exercicios_indices = linear_sum_assignment(matriz_custo_negativa)

            treino_do_dia = []
            for g_idx, e_idx in zip(grupos_indices, exercicios_indices):
                grupo = matriz_focada.index[g_idx]
                exercicio = matriz_focada.columns[e_idx]
                score = matriz_focada.iloc[g_idx, e_idx]
                
                treino_do_dia.append({
                    "grupo_alvo": grupo,
                    "exercicio_escolhido": exercicio,
                    "score_mvic_total": round(score, 2)
                })
                
                exercicios_ja_usados.append(exercicio)
            
            treinos_gerados[f"Treino {dia_label}"] = treino_do_dia

        return treinos_gerados

# Driver Code

URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "DiscreteTraining")
ARQUIVO_DADOS = "Training_Data.xlsx" 

if __name__ == "__main__":
    print("Inicializando processo de geração de treino...")
    
    try:
        # 2. Gerar o Treino
        print("\nFase 2: Gerando o treino...")
        
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            
            gerador = GeradorTreino(driver)
            
            DIAS_DE_TREINO = 3
            treinos = gerador.gerar_treino_full_body(dias_por_semana=DIAS_DE_TREINO)
            
            print("\n --- LISTA DE TREINOS GERADOS --- ")
            for dia, exercicios in treinos.items():
                print(f"\n========== {dia} ==========")
                for ex in exercicios:
                    print(f"  Grupo: {ex['grupo_alvo']:<12} | Exercício: {ex['exercicio_escolhido']:<25} | Score: {ex['score_mvic_total']}")

    except Exception as e:
        print(f"############### Ocorreu um erro fatal: {e} ##################")
        import traceback
        traceback.print_exc()