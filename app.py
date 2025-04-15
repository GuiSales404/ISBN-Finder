import gradio as gr
import pandas as pd
from functions import processar_arquivo_xlsx_para_csv, search, process_response
from datetime import datetime

def data_e_hora_atual():
    agora = datetime.now()
    return agora.strftime("%Y-%m-%d %H:%M:%S")


def processar_arquivo(uploaded_file, progress=gr.Progress(track_tqdm=True)):
    # Detecta tipo de arquivo
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file.name)
    elif uploaded_file.name.endswith('.xlsx'):
        path_csv_temporario = "temp_saida.csv"
        processar_arquivo_xlsx_para_csv(uploaded_file.name, path_csv_temporario)
        df = pd.read_csv(path_csv_temporario)
    else:
        raise ValueError("❌ Arquivo inválido. Apenas .csv ou .xlsx são aceitos.")

    # Inicializa colunas novas
    df.loc[:, 'ISBN-13'] = None
    df.loc[:, 'ISBN-10'] = None
    df.loc[:, 'REFERÊNCIA'] = None
    df.loc[:, 'CONFIABILIDADE TOTAL'] = None

    total_linhas = len(df)

    # Usa progress manualmente
    for idx, row in enumerate(df.itertuples(index=False)):
        titulo = row._asdict()['TÍTULO']
        autor = row._asdict()['AUTOR']
        editora = row._asdict()['EDITORA']

        # Buscar info
        response = search(titulo, autor, editora)
        finds = process_response(response)

        df.at[idx, 'ISBN-13'] = finds.get('ISBN-13')
        df.at[idx, 'ISBN-10'] = finds.get('ISBN-10')
        df.at[idx, 'REFERÊNCIA'] = finds.get('REFERÊNCIA')
        df.at[idx, 'CONFIABILIDADE TOTAL'] = finds.get('CONFIABILIDADE TOTAL')

        # Atualiza progresso manualmente
        progress((idx + 1) / total_linhas)

    # Salvar CSV final
    output_path = f"Results/resultado_final_{id}.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    return df, output_path

id = data_e_hora_atual()
# Interface Gradio
with gr.Blocks() as iface:
    gr.Markdown("# 📚 Processador de Livros com ISBN e Confiabilidade")
    gr.Markdown("Faça upload de um arquivo CSV ou XLSX de livros. Vamos buscar automaticamente os ISBNs e referências.")

    with gr.Row():
        arquivo_input = gr.File(label="Selecione um arquivo CSV ou XLSX")
    
    botao_processar = gr.Button("🔍 Processar arquivo")
    
    with gr.Row():
        preview_df = gr.DataFrame(label="🔎 Preview do resultado")
    
    arquivo_saida = gr.File(label=f"⬇️ Baixar CSV ({id}) Final")

    botao_processar.click(
        fn=processar_arquivo,
        inputs=[arquivo_input],
        outputs=[preview_df, arquivo_saida]
    )

if __name__ == "__main__":
    iface.launch()
