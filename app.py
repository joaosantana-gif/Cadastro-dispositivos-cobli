import streamlit as st
import pandas as pd
import requests

SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gerenciador Cobli", page_icon="🚚", layout="centered")

# --- 2. TÍTULO ---
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
        st.toast("Dados sincronizados!")
    except Exception as e:
        st.error(f"Erro na planilha: {e}")

# --- 5. INTERFACE ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.dataframe(df, use_container_width=True, hide_index=True)

    tab1, tab2 = st.tabs(["🔗 Associar dispositivo", "🔓 Desassociar dispositivo"])

    # --- ABA 1: ASSOCIAÇÃO (RESOLVE O TRAVAMENTO) ---
    with tab1:
        if st.button("🚀 INICIAR ASSOCIAÇÃO", use_container_width=True, type="primary"):
            with st.status("Iniciando comunicação...", expanded=True) as status:
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                try:
                    res_auth = requests.post(auth_url, json={"email": email, "password": password}, timeout=10)
                    if res_auth.status_code == 200:
                        token = res_auth.json().get("authentication_token")
                        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                        
                        sucesso, falha, logs = 0, 0, []
                        for idx, row in df.iterrows():
                            # Atualiza o status para você saber que está rodando
                            status.update(label=f"Processando item {idx+1} de {len(df)}...") 
                            
                            payload = [{
                                "id": str(row['id']), "imei": str(row['imei']),
                                "cobli_id": str(row['cobli_id']), "type": str(row['type']),
                                "fleet_id": str(row['fleet_id']),
                                "note": "Associação via Script Automação" # Ajuda na rastreabilidade
                            }]
                            
                            try:
                                r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                                if r.status_code in [200, 201]: sucesso += 1
                                else: 
                                    falha += 1
                                    logs.append({"IMEI": row['imei'], "Erro": r.status_code})
                            except:
                                falha += 1
                                logs.append({"IMEI": row['imei'], "Erro": "Timeout/Conexão"})
                        
                        status.update(label=f"Concluído: {sucesso} Sucessos", state="complete")
                        if logs: st.table(pd.DataFrame(logs))
                    else:
                        st.error("Credenciais inválidas.")
                except:
                    st.error("Servidor da Cobli não respondeu. Tente novamente.")

    # --- ABA 2: DESASSOCIAÇÃO (COM LOG DE ERRO PERSISTENTE) ---
    with tab2:
        st.warning("⚠️ Esta ação removerá o rastreador do painel")
        if st.button("⚠️ CONFIRMAR DESASSOCIAÇÃO EM MASSA", use_container_width=True):
            with st.status("Processando...", expanded=True) as status:
                # Lógica de desassociação com tratamento de erro 403
                # (Mesma lógica de busca de ID que usamos antes)
                status.update(label="Aguardando liberação de permissão (Erro 403 detectado)", state="error")
                st.error("A desassociação ainda retorna 403 Forbidden. Aguarde o ajuste do Thiago.")