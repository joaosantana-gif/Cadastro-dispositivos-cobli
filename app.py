import streamlit as st
import pandas as pd
import requests

SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", page_icon="🚚", layout="centered")

# --- 2. TÍTULO E STATUS ---
st.title("Gerenciador de Dispositivos - Cobli")
st.caption("Status: Administrador Ativado | Versão Anti-Travamento 🛡️")
st.divider()

# --- 3. BARRA LATERAL ---
st.sidebar.header("🔑 Autenticação")
email = st.sidebar.text_input("E-mail", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha API", type="password").strip()

if st.sidebar.button("🗑️ Limpar Sessão"):
    st.session_state.clear()
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. CARREGAMENTO ---
if st.button("🔄 Sincronizar Planilha Google", use_container_width=True): 
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
        st.toast("Dados sincronizados!", icon="✅")
    except Exception as e:
        st.error(f"Erro na planilha: {e}")

# --- 5. INTERFACE PRINCIPAL ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.dataframe(df, use_container_width=True, hide_index=True)

    tab1, tab2 = st.tabs(["🔗 Associar dispositivo", "🔓 Desassociar dispositivo"])

    # --- ABA 1: ASSOCIAR (RESOLVE O TRAVAMENTO E ERRO 400) ---
    with tab1:
        if st.button("🚀 INICIAR ASSOCIAÇÃO", use_container_width=True, type="primary"):
            # O st.status evita que a tela pareça travada
            with st.status("Iniciando comunicação...", expanded=True) as status:
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                try:
                    res_auth = requests.post(auth_url, json={"email": email, "password": password}, timeout=10)
                    if res_auth.status_code == 200:
                        token = res_auth.json().get("authentication_token")
                        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                        
                        sucesso, falha, logs = 0, 0, []
                        for idx, row in df.iterrows():
                            # Atualização visual constante para não parecer travado
                            status.update(label=f"Processando item {idx+1} de {len(df)}...") 
                            
                            # Ajuste de Payload para evitar Erro 400
                            payload = [{
                                "id": str(row['id']), 
                                "imei": str(row['imei']),
                                "cobli_id": str(row['cobli_id']), 
                                "type": str(row['type']),
                                "fleet_id": str(row['fleet_id']),
                                # Nota de rastreabilidade para o Thiago
                                "note": "Associação via ferramenta de automação - João Pedro"
                            }]
                            
                            try:
                                # Timeout de 15 segundos evita o congelamento
                                r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                                if r.status_code in [200, 201]: 
                                    sucesso += 1
                                else: 
                                    falha += 1
                                    logs.append({"IMEI": row['imei'], "Erro": r.status_code, "Detalhe": r.text[:100]})
                            except requests.exceptions.Timeout:
                                falha += 1
                                logs.append({"IMEI": row['imei'], "Erro": "Tempo Esgotado"})
                        
                        status.update(label=f"Concluído: {sucesso} Sucessos", state="complete")
                        if logs: 
                            st.error(f"{falha} dispositivos falharam.")
                            st.table(pd.DataFrame(logs))
                    else:
                        st.error("Credenciais inválidas.")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")

    # --- ABA 2: DESASSOCIAR (AGUARDANDO TI) ---
    with tab2:
        st.info("Aguardando liberação interna para resolver o erro 403.")