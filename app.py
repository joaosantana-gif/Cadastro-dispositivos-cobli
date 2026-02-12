import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- CONFIGURAÇÕES DE INTEGRAÇÃO ---
# Planilha de leitura (CSV Público)
SHEET_URL_READ = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# Seu link do Google Apps Script para gravação de logs
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCwT5_FsR4MqsYTuoLLuQd8tOZLBXPPsNZIcpNyO-7aZpFtN5u6YLvP3cv-YBSewznpw/exec"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", layout="centered")

# --- 2. LOGO E TÍTULO ---
try:
    st.image("logo.png", width=220)
except:
    pass

st.title("Cadastro de Dispositivos - Cobli")
st.caption("Sistema de Importação Direta com Registro em Nuvem")
st.divider()

# --- 3. BARRA LATERAL ---
st.sidebar.header("Acesso ao Sistema")
email = st.sidebar.text_input("E-mail Cobli", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha", type="password").strip()

if st.sidebar.button("Limpar Sessão"):
    st.session_state.clear()
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. SINCRONIZAÇÃO DE DADOS ---
if st.button("Sincronizar Planilha Google", use_container_width=True):
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL_READ)
        st.toast("Dados sincronizados")
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")

# --- 5. PROCESSAMENTO E GRAVAÇÃO ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"Itens na fila para processar: {len(df)}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    container_resultados = st.empty()

    if st.button("INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        if not email or not password:
            st.error("Insira as credenciais na barra lateral")
        else:
            with st.status("Processando e Sincronizando com Nuvem...", expanded=True) as status:
                # Passo 1: Autenticação na Cobli
                res_auth = requests.post('https://api.cobli.co/herbie-1.1/account/authenticate', 
                                         json={"email": email, "password": password}, timeout=10)
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha, logs_para_nuvem = 0, 0, []
                    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    for idx, row in df.iterrows():
                        imei_alvo = str(row['imei'])
                        # Rastreabilidade para o Thiago
                        nota_auditoria = f"Ferramenta Python - Usuario: {email}"
                        
                        payload = [{
                            "id": str(row['id']), "imei": imei_alvo, "cobli_id": str(row['cobli_id']),
                            "type": str(row['type']), "icc_id": str(row['icc_id']),
                            "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']),
                            "fleet_id": str(row['fleet_id']), "note": nota_auditoria
                        }]

                        try:
                            # Passo 2: Importação direta para garantir vínculo no painel
                            r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                            
                            # Tradução humana dos erros
                            if r.status_code in [200, 201]:
                                sucesso += 1
                                msg_api, res_texto = "Sucesso na associacao", "Sucesso"
                            elif r.status_code == 409:
                                falha += 1
                                msg_api, res_texto = "Dispositivo ja consta associado", "Falha"
                            else:
                                falha += 1
                                msg_api, res_texto = f"Erro {r.status_code}", "Falha"

                            # Organiza os dados para enviar ao Google Sheets
                            logs_para_nuvem.append({
                                "data_hora": data_atual,
                                "imei": imei_alvo,
                                "resultado": res_texto,
                                "mensagem": msg_api,
                                "nota": nota_auditoria
                            })
                        
                        except:
                            falha += 1
                            logs_para_nuvem.append({
                                "data_hora": data_atual, "imei": imei_alvo, 
                                "resultado": "Erro", "mensagem": "Sem resposta", "nota": nota_auditoria
                            })

                    # Passo 3: Envio dos logs para o seu link do Apps Script
                    try:
                        requests.post(APPS_SCRIPT_URL, json=logs_para_nuvem, timeout=15)
                        status.update(label=f"Concluido: {sucesso} Sucessos. Logs gravados na planilha.", state="complete")
                    except:
                        status.update(label="Processamento feito, mas erro ao gravar logs na nuvem.", state="error")

                    # Passo 4: Exibição persistente na tela
                    with container_resultados.container():
                        st.divider()
                        st.write("Log da Sessao (Sincronizado com Google Sheets)")
                        log_df = pd.DataFrame(logs_para_nuvem)
                        st.dataframe(log_df, use_container_width=True, hide_index=True)
                        
                        # Botão de backup em CSV
                        csv_data = log_df.to_csv(index=False).encode('utf-8')
                        st.download_button(label="Baixar Backup do Log (CSV)", data=csv_data, 
                                           file_name="log_cobli.csv", mime="text/csv", use_container_width=True)
                else:
                    st.error("Falha na autenticacao. Verifique seu login.")