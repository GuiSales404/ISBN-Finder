import pandas as pd
import unicodedata
from tavily import TavilyClient
import re
import os

def normalizar_coluna(nome_coluna):
    nome = unicodedata.normalize('NFKD', str(nome_coluna)).encode('ASCII', 'ignore').decode('utf-8')
    nome = re.sub(r'\s+', ' ', nome)  # tira espaços duplos
    return nome.strip().lower()

def processar_arquivo_xlsx_para_csv(caminho_xlsx, caminho_csv_saida):
    # Lê o arquivo inteiro SEM dizer quem é header ainda
    df_raw = pd.read_excel(caminho_xlsx, header=None)

    # Mapeamento esperado
    colunas_esperadas = {
        'indicacao': 'INDICAÇÃO',
        'titulo': 'TÍTULO',
        'autor': 'AUTOR',
        'editora': 'EDITORA',
        'quant': 'QUANT',
        'valor unitario': 'VALOR UNITÁRIO',
        'valor total': 'VALOR TOTAL',
    }

    # Tentar encontrar a linha onde começam os cabeçalhos certos
    linha_cabecalho = None
    for i, row in df_raw.iterrows():
        colunas_normalizadas = [normalizar_coluna(cell) for cell in row if pd.notna(cell)]
        if colunas_normalizadas:
            matches = sum(
                any(esperado in col for esperado in colunas_esperadas.keys()) for col in colunas_normalizadas
            )
            if matches >= 4:  # Se bater pelo menos 4 colunas corretas, aceitamos
                linha_cabecalho = i
                break

    if linha_cabecalho is None:
        raise ValueError("❌ Não consegui encontrar os cabeçalhos corretos no arquivo.")

    # Ler de novo a partir do cabeçalho correto
    df = pd.read_excel(caminho_xlsx, skiprows=linha_cabecalho)

    # Agora normalizar as colunas
    df_renomeado = df.copy()
    df_renomeado.columns = [normalizar_coluna(col) for col in df.columns]

    # Mapeia as colunas certas
    colunas_mapeadas = {}
    for nome_normalizado, nome_original in zip(df_renomeado.columns, df.columns):
        for esperado in colunas_esperadas.keys():
            if esperado in nome_normalizado:
                colunas_mapeadas[colunas_esperadas[esperado]] = nome_original
                break

    # Verificar colunas faltando
    colunas_faltando = [col for col in colunas_esperadas.values() if col not in colunas_mapeadas]
    if colunas_faltando:
        raise ValueError(f"Colunas faltando no arquivo: {colunas_faltando}")

    # Selecionar e renomear
    df_final = df[list(colunas_mapeadas.values())]
    df_final.columns = list(colunas_mapeadas.keys())

    # Salvar como CSV
    df_final.to_csv(caminho_csv_saida, index=False, encoding='utf-8-sig')
    print(f"✅ Arquivo CSV salvo em: {caminho_csv_saida}")

def search(title:str, author:str, publisher:str) -> dict:
    client = TavilyClient(os.getenv('TAVILY'))
    response = client.search(
        query=f"Qual o ISBN-10 ou ISBN-13 desse livro de título: {title}, do autor: {author} e editora: {publisher}. Retorne a resposta sem texto adicional apenas ISBN-10 e ISBN-13",
        include_answer="basic"
    )
    return response

def extract_isbn(text):
    result = {}
    if not text:
        return result
    parts = text.split(',')
    for part in parts:
        part = part.strip()
        if ':' in part:
            key, value = part.split(':', 1)
            result[key.strip()] = value.strip()
    return result

def classificar_confiabilidade(score):
    score = round(score*100)
    if not isinstance(score, (int, float)):
        raise ValueError("O score deve ser um número.")
    if score < 0 or score > 100:
        raise ValueError("O score deve estar entre 0 e 100.")
    if score <= 25:
        return "Muito Baixa"
    elif score <= 50:
        return "Baixa"
    elif score <= 75:
        return "Alta"
    else:  
        return "Muito Alta"
    
def process_response(response:dict) -> dict:
    final_result = extract_isbn(response['answer'])
    reference = ''
    final_confiability = 0
    
    for result in response['results']:
        reference += f"{result['url']}: {classificar_confiabilidade(result['score'])} | "
        final_confiability += result['score']
    final_result['REFERÊNCIA'] = reference
    #divisao por zero aqui 
    if len(response['results']) != 0:
        total_confiability = final_confiability/len(response['results'])
        final_result['CONFIABILIDADE TOTAL'] = classificar_confiabilidade(total_confiability)
    else:
        final_result['CONFIABILIDADE TOTAL'] = ''
    return final_result

def start(df: pd.core.frame.DataFrame) -> pd.core.frame.DataFrame:
    df.loc[:, 'ISBN-13'] = None
    df.loc[:, 'ISBN-10'] = None
    df.loc[:, 'REFERÊNCIA'] = None
    df.loc[:, 'CONFIABILIDADE TOTAL'] = None

    for idx, row in df.iterrows():
        titulo = row['TÍTULO']
        autor = row['AUTOR']
        editora = row['EDITORA']
        
        # Buscar info
        response = search(titulo, autor, editora)
        finds = process_response(response)
        # Atualizar colunas novas
        df.at[idx, 'ISBN-13'] = finds.get('ISBN-13')
        df.at[idx, 'ISBN-10'] = finds.get('ISBN-10')
        df.at[idx, 'REFERÊNCIA'] = finds.get('REFERÊNCIA')
        df.at[idx, 'CONFIABILIDADE TOTAL'] = finds.get('CONFIABILIDADE TOTAL')
    
    return df