import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google publicada como CSV
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", page_icon="🚚", layout="centered")

# --- 2. LOGO E TÍTULO ---
try:
    st.image("logo.png", width=180) 
except:
    pass

st.title("Gerenciador de Dispositivos - Cobli")
st.caption("Nível: Administrador | Resolução Automática de IDs")
st.divider()

# --- 3. BARRA LATERAL ---
st.sidebar.header("🔑 Acesso Cobli")
email = st.sidebar.text_input("E-mail corporativo", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha API", type="password").strip()

if st.sidebar.button("🗑️ Forçar Limpeza de Token"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.toast("Sessão reiniciada!")
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. CARREGAMENTO ---
if st.button("🔄 Sincronizar Planilha Google", use_container_width=True, type="secondary"): 
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
        st.toast("Dados sincronizados!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao acessar planilha: {e}")

# --- 5. INTERFACE PRINCIPAL ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"### Dispositivos na Planilha ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True) 

    # Abas atualizadas
    tab1, tab2 = st.tabs(["🔗 Associar dispositivo", "🔓 Desassociar dispositivo"])

    # --- ABA 1: ASSOCIAR ---
    with tab1:
        if st.button("🚀 INICIAR ASSOCIAÇÃO EM MASSA", use_container_width=True, type="primary"):
            # Lógica de associação (POST) mantida aqui
            st.info("Iniciando processo de associação...")

    # --- ABA 2: DESASSOCIAR (COM BUSCA DE ID) ---
    with tab2:
        st.warning("⚠️ Esta ação removerá o rastreador do painel")
        res_container = st.container()

        if st.button("⚠️ CONFIRMAR DESASSOCIAÇÃO EM MASSA", use_container_width=True):
            if not email or not password:
                st.error("Preencha o acesso na lateral.")
            else:
                with st.status("Validando acesso de Administrador...", expanded=True) as status:
                    # Renovação de Token
                    auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                    res_auth = requests.post(auth_url, json={"email": email, "password": password})
                    
                    if res_auth.status_code == 200:
                        token = res_auth.json().get("authentication_token")
                        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                        
                        sucessos, falhas, logs = 0, 0, []

                        for idx, row in df.iterrows():
                            imei_alvo = str(row['imei'])
                            
                            # PASSO 1: Buscar o ID Real da associação pelo IMEI
                            # Isso resolve o problema de usar o IMEI como ID
                            search_url = f'https://api.cobli.co/v1/devices?imei={imei_alvo}'
                            res_search = requests.get(search_url, headers=headers)
                            
                            device_internal_id = None
                            if res_search.status_code == 200:
                                data = res_search.json()
                                if data and len(data) > 0:
                                    device_internal_id = data[0].get('id')

                            # PASSO 2: Se encontramos o ID, tentamos desassociar
                            if device_internal_id:
                                patch_url = f'https://api.cobli.co/v1/device-vehicle-association/{device_internal_id}'
                                r = requests.patch(patch_url, json={"vehicle_id": None}, headers=headers)
                                
                                if r.status_code in [200, 204]:
                                    sucessos += 1
                                else:
                                    falhas += 1
                                    logs.append({"IMEI": imei_alvo, "Status": r.status_code, "Erro": "Permissão Negada (403)" if r.status_code == 403 else r.text})
                            else:
                                falhas += 1
                                logs.append({"IMEI": imei_alvo, "Status": "Não Encontrado", "Erro": "IMEI não localizado no sistema"})

                        status.update(label=f"Processo finalizado: {sucessos} Sucessos", state="complete")
                        
                        with res_container:
                            if sucessos > 0: st.success(f"✅ {sucessos} dispositivos desvinculados!")
                            if falhas > 0:
                                st.error(f"❌ {falhas} falhas detectadas.")
                                with st.expander("🔍 Ver Log Detalhado das Falhas", expanded=True):
                                    st.table(pd.DataFrame(logs))
                    else:
                        st.error("Falha na autenticação. Verifique sua senha.")