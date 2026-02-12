import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURACAO DA PAGINA ---
st.set_page_config(page_title="Gerenciador Cobli", layout="centered")

# --- 2. LOGO E TITULO ---
try:
    st.image("logo.png", width=220)
except:
    pass

st.title("Cadastro de Dispositivos - Cobli")
st.caption("Sistema de Importacao Direta e Rastreabilidade")
st.divider()

# --- 3. BARRA LATERAL ---
st.sidebar.header("Acesso ao Sistema")
email = st.sidebar.text_input("E-mail Cobli", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha", type="password").strip()

if st.sidebar.button("Limpar Sessao"):
    st.session_state.clear()
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. ENTRADA DE DADOS ---
if st.button("Sincronizar Planilha Google", use_container_width=True):
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
        st.toast("Dados sincronizados")
    except Exception as e:
        st.error(f"Erro na sincronizacao: {e}")

# --- 5. PROCESSAMENTO ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"Itens na fila: {len(df)}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    container_resultados = st.empty()

    if st.button("INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        if not email or not password:
            st.error("Insira as credenciais na barra lateral")
        else:
            with st.status("Processando dados...", expanded=True) as status:
                res_auth = requests.post('https://api.cobli.co/herbie-1.1/account/authenticate', 
                                         json={"email": email, "password": password}, timeout=10)
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha, logs_execucao = 0, 0, []

                    for idx, row in df.iterrows():
                        imei_alvo = str(row['imei'])
                        nota_auditoria = f"Ferramenta Python - Usuario: {email}" # Mantendo rastreabilidade
                        
                        payload = [{
                            "id": str(row['id']), 
                            "imei": imei_alvo, 
                            "cobli_id": str(row['cobli_id']),
                            "type": str(row['type']), 
                            "icc_id": str(row['icc_id']),
                            "chip_number": str(row['chip_number']), 
                            "chip_operator": str(row['chip_operator']),
                            "fleet_id": str(row['fleet_id']),
                            "note": nota_auditoria
                        }]

                        try:
                            r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                            
                            # Traducao dos codigos de erro para mensagens reais
                            if r.status_code in [200, 201]:
                                sucesso += 1
                                msg_api = "Sucesso na associacao"
                                resultado_texto = "Sucesso"
                            elif r.status_code == 409:
                                falha += 1
                                msg_api = "Dispositivo ja consta associado"
                                resultado_texto = "Falha"
                            elif r.status_code == 400:
                                falha += 1
                                msg_api = "Dados invalidos (Verifique Fleet ID ou IMEI)"
                                resultado_texto = "Falha"
                            else:
                                falha += 1
                                msg_api = f"Erro inesperado ({r.status_code})"
                                resultado_texto = "Falha"

                            logs_execucao.append({
                                "IMEI": imei_alvo, 
                                "Resultado": resultado_texto, 
                                "Mensagem": msg_api, 
                                "Nota": nota_auditoria
                            })
                        except:
                            falha += 1
                            logs_execucao.append({
                                "IMEI": imei_alvo, 
                                "Resultado": "Erro", 
                                "Mensagem": "Sem resposta do servidor", 
                                "Nota": nota_auditoria
                            })

                    status.update(label=f"Processamento concluido: {sucesso} Sucessos", state="complete")

                    with container_resultados.container():
                        st.divider()
                        st.write("Log Detalhado")
                        log_df = pd.DataFrame(logs_execucao)
                        st.dataframe(log_df, use_container_width=True, hide_index=True)
                        
                        csv_data = log_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Baixar Log de Execucao (CSV)",
                            data=csv_data,
                            file_name="log_cobli.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                else:
                    st.error("Falha na autenticacao")