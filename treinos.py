import pandas as pd
import numpy as np
from neo4j import GraphDatabase

try:
    from database import Neo4jDatabase, ProcessadorDadosTreino
except ImportError:
    print("Erro: O arquivo 'database.py' não foi encontrado.")
    exit()

class GeradorTreino:
    """Faz o gerenciamento de toda lógica de criação de treino"""

    def __init__(self, db_driver):
        """Inicializa as variáveis de cache a serem usadas ao longo da classe

        Args:
            db_driver (_type_): Instância de conexão com o banco de dados

        Raises:
            ValueError: É retornado caso a conexão com o banco de dados não exista
        """

        if not db_driver:
            raise ValueError("O driver do Neo4j é necessário.")
        self.driver = db_driver
        
        self.df_completo = None
        self.matriz_grupo_df = None 
        self.matriz_musculo_df = None
        self.grupo_para_musculos_map = None
        
        print("Gerador de Treino inicializado.")

    def _carregar_cache_dados(self):
        if self.df_completo is not None:
            return 

        print("Baixando dados do Neo4j Aura (download único)...")

        query = """
        MATCH (g:GrupoMuscular)-[:POSSUI]->(m:Musculo)-[r:É_ATIVADO]->(e:Exercicio)
        RETURN g.nome AS Grupo, m.nome AS Musculo, e.nome AS Exercicio, r.peso AS Peso
        """
        with self.driver.session(database="neo4j") as session:
            results = session.run(query)
            data = [record.data() for record in results]
        
        if not data:
            raise Exception("O banco de dados parece vazio. Popule-o primeiro.")
            
        self.df_completo = pd.DataFrame(data)
        
        self.df_completo['ID_Musculo'] = self.df_completo['Grupo'] + " > " + self.df_completo['Musculo']
        
        print(f"Dados carregados localmente: {len(self.df_completo)} registros.")

    def _get_matriz_grupo_exercicio(self):
        """Gera a matriz de custo Grupo x Exercicio"""

        self._carregar_cache_dados()
        
        if self.matriz_grupo_df is None:
            # Agrupa por Grupo e Exercicio e soma os pesos
            df_agrupado = self.df_completo.groupby(['Grupo', 'Exercicio'])['Peso'].sum().reset_index()
            
            self.matriz_grupo_df = df_agrupado.pivot(
                index='Grupo', columns='Exercicio', values='Peso'
            ).fillna(0)
            
        return self.matriz_grupo_df

    def _get_matriz_musculo_exercicio(self):
        self._carregar_cache_dados()
        
        if self.matriz_musculo_df is None:
            # Usamos o ID_Musculo para pivotar
            df_unique = self.df_completo[['ID_Musculo', 'Exercicio', 'Peso']].drop_duplicates()
            
            self.matriz_musculo_df = df_unique.pivot(
                index='ID_Musculo',
                columns='Exercicio', 
                values='Peso'
            ).fillna(0)
            
        return self.matriz_musculo_df

    def _get_mapa_grupo_musculo(self):
        self._carregar_cache_dados()
        
        if self.grupo_para_musculos_map is None:
            
            grouped = self.df_completo.groupby('Grupo')['ID_Musculo'].unique()
            self.grupo_para_musculos_map = grouped.to_dict()
            
            for k, v in self.grupo_para_musculos_map.items():
                self.grupo_para_musculos_map[k] = v.tolist()
                
        return self.grupo_para_musculos_map



    def _algoritmo_hungaro(self, matriz_custo):
        """
        Implementa o algoritmo Kuhn-Munkres (Húngaro) O(n^3).
        Resolve o problema de Matching Perfeito de Custo Mínimo em Grafo Bipartido.
        
        Args:
            matriz_custo (np.array): Matriz (nxm) onde queremos minimizar a soma.
            
        Returns:
            list: Lista de tuplas (indice_linha, indice_coluna) representando as arestas escolhidas.
        """

        num_linha, num_colunas = matriz_custo.shape
        
        u = np.zeros(num_linha + 1)
        v = np.zeros(num_colunas + 1)
        p = np.zeros(num_colunas + 1, dtype=int)
        way = np.zeros(num_colunas + 1, dtype=int)

        for i in range(1, num_linha + 1):
            p[0] = i
            j0 = 0
            
            minv = np.full(num_colunas + 1, float('inf'))
            used = np.zeros(num_colunas + 1, dtype=bool)
            
            while True:
                used[j0] = True
                i0 = p[j0]
                delta = float('inf')
                j1 = 0
                
                for j in range(1, num_colunas + 1):
                    if not used[j]:
                        custo_reduzido = matriz_custo[i0-1, j-1] - u[i0] - v[j]
                        
                        if custo_reduzido < minv[j]:
                            minv[j] = custo_reduzido
                            way[j] = j0
                        
                        if minv[j] < delta:
                            delta = minv[j]
                            j1 = j
                
                for j in range(num_colunas + 1):
                    if used[j]:
                        u[p[j]] += delta
                        v[j] -= delta
                    else:
                        minv[j] -= delta
                
                j0 = j1
                if p[j0] == 0:
                    break
            
            while True:
                j1 = way[j0]
                p[j0] = p[j1]
                j0 = j1
                if j0 == 0:
                    break
        
        resultado = []
        for j in range(1, num_colunas + 1):
            if p[j] != 0:
                resultado.append((p[j]-1, j-1))
                
        return resultado


    def gerar_treino_full_body(self, dias_por_semana: int, grupos_alvo=None):
        """Gera um treino Full-Body utilizando o algoritmo Húngaro"""
        matriz_completa = self._get_matriz_grupo_exercicio()

        if grupos_alvo is None:
            grupos_alvo = matriz_completa.index.tolist()

        matriz_focada_df = matriz_completa.loc[grupos_alvo]
        
        max_score = matriz_focada_df.max().max()
        matriz_numpy = matriz_focada_df.to_numpy()
        
        matriz_custo = max_score - matriz_numpy 
        
        treinos_gerados = {}
        exercicios_ja_usados_indices = []

        for dia in range(dias_por_semana):
            dia_label = chr(ord('A') + dia)
            
            matriz_iteracao = matriz_custo.copy()
            if exercicios_ja_usados_indices:
                matriz_iteracao[:, exercicios_ja_usados_indices] = 999999
            
            pares_escolhidos = self._algoritmo_hungaro(matriz_iteracao)

            treino_do_dia = []
            for linha_idx, col_idx in pares_escolhidos:
                grupo = matriz_focada_df.index[linha_idx]
                exercicio = matriz_focada_df.columns[col_idx]
                score_real = matriz_numpy[linha_idx, col_idx]
                
                if score_real > 0 and matriz_iteracao[linha_idx, col_idx] < 900000:
                    treino_do_dia.append({
                        "grupo_alvo": grupo,
                        "exercicio_escolhido": exercicio,
                        "score_mvic_total": round(score_real, 2)
                    })
                    exercicios_ja_usados_indices.append(col_idx)
            
            treinos_gerados[f"Treino {dia_label}"] = treino_do_dia

        return treinos_gerados

    
    def gerar_treino_hipertrofia(self, grupos_alvo: list, num_exercicios: int):
        """Gera treino de hipertrofia usando algoritmo Greedy (Top-K)."""
        
        matriz_detalhada = self._get_matriz_musculo_exercicio()
        mapa_grupos = self._get_mapa_grupo_musculo()
        
        musculos_alvo = set()
        for grupo in grupos_alvo:
            if grupo in mapa_grupos:
                musculos_alvo.update(mapa_grupos[grupo])
        
        if not musculos_alvo:
            print("Nenhum músculo encontrado para os grupos informados.")
            return []

        musculos_validos = [m for m in musculos_alvo if m in matriz_detalhada.index]
        matriz_focada = matriz_detalhada.loc[musculos_validos]
        
        score_total_por_exercicio = matriz_focada.sum(axis=0)
        exercicios_ordenados = score_total_por_exercicio.sort_values(ascending=False)
        
        top_k = exercicios_ordenados.head(num_exercicios)
        
        treino_gerado = []
        for exercicio, score in top_k.items():
            if score == 0: 
                continue
                
            detalhes = matriz_focada[exercicio][matriz_focada[exercicio] > 0]
            
            treino_gerado.append({
                "exercicio_escolhido": exercicio,
                "score_mvic_total": round(score, 2),
                "musculos_ativados": detalhes.to_dict()
            })
            
        return treino_gerado


# Driver Code

URI = "neo4j+ssc://87ac44c9.databases.neo4j.io"
AUTH = ("neo4j", "qP5nlLhuF1ELaAXiEL2hv0wTAqTuz436Hvqs9TNVkRQ")
ARQUIVO_DADOS = "Training_Data.xlsx" 

if __name__ == "__main__":
    print("Inicializando processo de geração de treino...")
    
    try:
        print("\nGerando os treinos...")
        
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            
            gerador = GeradorTreino(driver)
            DIAS_DE_TREINO = 3
            treinos_full_body = gerador.gerar_treino_full_body(dias_por_semana=DIAS_DE_TREINO)
            
            print("\n---- [RESULTADO] TREINOS FULL BODY (Matching) ----")
            for dia, exercicios in treinos_full_body.items():
                print(f"\n========== {dia} ==========")
                for ex in exercicios:
                    print(f"  Grupo: {ex['grupo_alvo']:<12} | Exercício: {ex['exercicio_escolhido']:<25} | Score: {ex['score_mvic_total']}")

            GRUPOS_HIPERTROFIA = ['Peitoral', 'Ombro', 'Triceps']
            NUM_EXERCICIOS = 6
            
            print(f"\n--- [RESULTADO] TREINO HIPERTROFIA (Greedy Top-K) para {GRUPOS_HIPERTROFIA} ---")
            treino_split = gerador.gerar_treino_hipertrofia(
                grupos_alvo=GRUPOS_HIPERTROFIA,
                num_exercicios=NUM_EXERCICIOS
            )
            
            for i, ex in enumerate(treino_split):
                print(f"\n {i+1}. Exercício: {ex['exercicio_escolhido']} (Score Total: {ex['score_mvic_total']})")
                for musculo, peso in ex['musculos_ativados'].items():
                    print(f"     - Ativa: {musculo:<25} (Peso: {peso})")


    except Exception as e:
        print(f"############### Ocorreu um erro fatal: {e} ##################")
        import traceback
        traceback.print_exc()