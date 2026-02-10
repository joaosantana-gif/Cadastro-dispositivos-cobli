import streamlit as st
import pandas as pd
import requests

SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gerenciador Cobli", page_icon="🚚", layout="centered")

# --- 2. TÍTULO E ESTILO ---
st.title("Gerenciador de Dispositivos - Cobli")
st.caption("Status: Administrador Ativado | Diagnóstico de Protocolo 🛡️")
st.divider()

# --- 3. BARRA LATERAL ---
st.sidebar.header("🔑 Autenticação")
email = st.sidebar.text_input("E-mail", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha API", type="password").strip()

if st.sidebar.button("🗑️ Forçar Limpeza de Token"):
    st.session_state.clear()
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. SINCRONIZAÇÃO ---
if st.button("🔄 Sincronizar Planilha Google", use_container_width=True): 
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
        st.toast("Dados sincronizados!")
    except Exception as e:
        st.error(f"Erro: {e}")

# --- 5. INTERFACE ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.dataframe(df, use_container_width=True, hide_index=True)

    tab1, tab2 = st.tabs(["🔗 Associar dispositivo", "🔓 Desassociar dispositivo"])

    with tab1:
        if st.button("🚀 INICIAR ASSOCIAÇÃO", use_container_width=True, type="primary"):
            st.info("Iniciando processo...")

    with tab2:
        st.warning("⚠️ Esta ação removerá o rastreador do painel")
        log_container = st.container()

        if st.button("⚠️ CONFIRMAR DESASSOCIAÇÃO EM MASSA", use_container_width=True):
            with st.status("Protocolo de Administrador em execução...", expanded=True) as status:
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                res_auth = requests.post(auth_url, json={"email": email, "password": password})
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                    
                    sucessos, falhas, lista_erros = 0, 0, []

                    for idx, row in df.iterrows():
                        imei = str(row['imei'])
                        
                        # PASSO 1: Busca ID interno (Evita erro de identificador)
                        search = requests.get(f'https://api.cobli.co/v1/devices?imei={imei}', headers=headers)
                        internal_id = search.json()[0].get('id') if search.status_code == 200 and search.json() else None
                        
                        if internal_id:
                            # PASSO 2: Tenta DELETE (Método Padrão)
                            del_url = f'https://api.cobli.co/v1/device-vehicle-association/{internal_id}'
                            r = requests.delete(del_url, headers=headers)
                            
                            # PASSO 3: Se DELETE for 403, tenta PATCH como alternativa
                            if r.status_code == 403:
                                r = requests.patch(del_url, json={"vehicle_id": None}, headers=headers)

                            if r.status_code in [200, 204]:
                                sucessos += 1
                            else:
                                falhas += 1
                                lista_erros.append({"IMEI": imei, "Status": r.status_code, "Resposta": r.text[:100]})
                        else:
                            falhas += 1
                            lista_erros.append({"IMEI": imei, "Status": "Erro", "Resposta": "ID não encontrado"})

                    status.update(label=f"Processo finalizado. {sucessos} Sucessos.", state="complete")
                    
                    with log_container:
                        if sucessos > 0: st.success(f"✅ {sucessos} desvinculados!")
                        if falhas > 0:
                            st.error(f"❌ {falhas} falhas. Verifique os logs abaixo.")
                            st.expander("🔍 Detalhes Técnicos", expanded=True).table(pd.DataFrame(lista_erros))
                else:
                    st.error("Falha na autenticação.")