import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google publicada como CSV
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Cadastro de Dispositivos - Cobli", 
    page_icon="🚚", 
    layout="centered"
)

# --- 2. LOGO E TÍTULO ---
try:
    st.image("logo.png", width=180) 
except:
    st.info("💡 Carregando sem logo local.")

st.title("Gerenciador de Dispositivos - Cobli")
st.caption("Automação de Associações e Desassociações via API")
st.divider()

# --- 3. MEMÓRIA E BARRA LATERAL ---
if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

st.sidebar.header("🔑 Acesso Cobli")
email = st.sidebar.text_input("E-mail corporativo", placeholder="seu.nome@cobli.co").strip()
password = st.sidebar.text_input("Senha API", type="password").strip()

if st.sidebar.button("🗑️ Limpar Sessão"):
    st.session_state.dados_planilha = None
    st.rerun()

# --- 4. SINCRONIZAÇÃO DE DADOS ---
if st.button("🔄 Sincronizar Planilha Google", use_container_width=True, type="secondary"): 
    with st.spinner("Buscando dados na nuvem..."):
        try:
            st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
            st.success("Planilha sincronizada com sucesso!")
        except Exception as e:
            st.error(f"Erro ao acessar planilha: {e}")

# --- 5. INTERFACE PRINCIPAL (ABAS RENOMEADAS) ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"### Dispositivos na Planilha ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True) 

    # Abas atualizadas conforme sua solicitação
    tab1, tab2 = st.tabs(["🔗 Associar dispositivo", "🔓 Desassociar dispositivo"])

    # --- ABA 1: ASSOCIAR DISPOSITIVO ---
    with tab1:
        st.markdown("Vincula os dispositivos aos veículos e frotas configurados.")
        if st.button("🚀 INICIAR ASSOCIAÇÃO", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Preencha o acesso na lateral.")
            else:
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                res_auth = requests.post(auth_url, json={"email": email, "password": password})
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    import_url = 'https://api.cobli.co/v1/devices-import'
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha = 0, 0
                    logs_erro = [] # Lista para armazenar erros detalhados
                    progress = st.progress(0)
                    
                    for idx, row in df.iterrows():
                        payload = [{
                            "id": str(row['id']), "imei": str(row['imei']),
                            "cobli_id": str(row['cobli_id']), "type": str(row['type']),
                            "icc_id": str(row['icc_id']), "chip_number": str(row['chip_number']),
                            "chip_operator": str(row['chip_operator']), "fleet_id": str(row['fleet_id'])
                        }]
                        r = requests.post(import_url, json=payload, headers=headers)
                        if r.status_code in [200, 201]:
                            sucesso += 1
                        else:
                            falha += 1
                            logs_erro.append({"IMEI": row['imei'], "Status": r.status_code, "Mensagem": r.text})
                        
                        progress.progress((idx + 1) / len(df))
                        
                    st.divider()
                    st.success(f"Processo finalizado: {sucesso} Sucessos | {falha} Falhas")
                    
                    # Exibição do Log de Erros Detalhado
                    if logs_erro:
                        with st.expander("🔍 Ver Log de Erros Detalhado"):
                            st.table(pd.DataFrame(logs_erro))
                else:
                    st.error("Credenciais inválidas.")

    # --- ABA 2: DESASSOCIAR DISPOSITIVO ---
    with tab2:
        st.warning("⚠️ Esta ação removerá o rastreador do painel")
        if st.button("⚠️ CONFIRMAR DESASSOCIAÇÃO", use_container_width=True):
            if not email or not password:
                st.error("Preencha o acesso na lateral.")
            else:
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                res_auth = requests.post(auth_url, json={"email": email, "password": password})
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    headers = {'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha = 0, 0
                    logs_erro = []
                    progress = st.progress(0)
                    
                    for idx, row in df.iterrows():
                        device_id = str(row['id'])
                        del_url = f'https://api.cobli.co/v1/device-vehicle-association/{device_id}'
                        
                        r = requests.delete(del_url, headers=headers)
                        
                        if r.status_code in [200, 204]:
                            sucesso += 1
                        else:
                            falha += 1
                            logs_erro.append({"ID": device_id, "IMEI": row['imei'], "Status": r.status_code, "Mensagem": r.text})
                            
                        progress.progress((idx + 1) / len(df))
                    
                    st.divider()
                    st.success(f"Desassociação finalizada: {sucesso} Sucessos | {falha} Falhas")
                    
                    if logs_erro:
                        with st.expander("🔍 Ver Log de Erros Detalhado"):
                            st.table(pd.DataFrame(logs_erro))
                else:
                    st.error("Credenciais inválidas.")