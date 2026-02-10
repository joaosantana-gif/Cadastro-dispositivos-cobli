import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google publicada como CSV
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gerenciador de Dispositivos - Cobli", 
    page_icon="🚚", 
    layout="centered"
)

# --- 2. LOGO E TÍTULO ---
try:
    st.image("logo.png", width=180) 
except:
    pass

st.title("Gerenciador de Dispositivos - Cobli")
st.caption("Modo Administrador Ativado | Automação de Frota")
st.divider()

# --- 3. BARRA LATERAL E ESTADO DA SESSÃO ---
if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

st.sidebar.header("🔑 Acesso Cobli")
email = st.sidebar.text_input("E-mail corporativo", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha API", type="password").strip()

if st.sidebar.button("🗑️ Limpar Sessão"):
    st.session_state.dados_planilha = None
    st.rerun()

# --- 4. CARREGAMENTO DE DADOS ---
if st.button("🔄 Sincronizar Planilha Google", use_container_width=True, type="secondary"): 
    with st.spinner("Buscando dados na nuvem..."):
        try:
            st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
            st.toast("Planilha sincronizada!", icon="✅")
        except Exception as e:
            st.error(f"Erro ao acessar planilha: {e}")

# --- 5. INTERFACE PRINCIPAL ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"### Dispositivos na Planilha ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True) 

    # ABAS ATUALIZADAS
    tab1, tab2 = st.tabs(["🔗 Associar dispositivo", "🔓 Desassociar dispositivo"])

    # --- ABA 1: ASSOCIAR DISPOSITIVO ---
    with tab1:
        st.markdown("Vincula os dispositivos aos veículos e frotas configurados.")
        container_assoc = st.container() 
        
        if st.button("🚀 INICIAR ASSOCIAÇÃO EM MASSA", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Preencha a senha na lateral.")
            else:
                with st.status("Processando associações...", expanded=True) as status:
                    auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                    res_auth = requests.post(auth_url, json={"email": email, "password": password})
                    
                    if res_auth.status_code == 200:
                        token = res_auth.json().get("authentication_token")
                        import_url = 'https://api.cobli.co/v1/devices-import'
                        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                        
                        sucesso, falha, logs = 0, 0, []
                        
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
                                logs.append({"IMEI": row['imei'], "Status": r.status_code, "Resposta": r.text[:100]})
                        
                        status.update(label=f"Associação Finalizada. Sucessos: {sucesso}", state="complete", expanded=False)
                        
                        with container_assoc:
                            if sucesso > 0: st.success(f"✅ {sucesso} dispositivos associados!")
                            if falha > 0:
                                st.error(f"❌ {falha} falhas detectadas.")
                                with st.expander("🔍 Ver Logs de Erro"):
                                    st.table(pd.DataFrame(logs))
                    else:
                        st.error("Erro de autenticação.")

    # --- ABA 2: DESASSOCIAR DISPOSITIVO ---
    with tab2:
        # AVISO SIMPLIFICADO
        st.warning("⚠️ Esta ação removerá o rastreador do painel") 
        container_desassoc = st.container()

        if st.button("⚠️ CONFIRMAR DESASSOCIAÇÃO EM MASSA", use_container_width=True):
            if not email or not password:
                st.error("Preencha a senha na lateral.")
            else:
                with st.status("Executando desasociações...", expanded=True) as status:
                    # Autenticação
                    auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                    res_auth = requests.post(auth_url, json={"email": email, "password": password})
                    
                    if res_auth.status_code == 200:
                        token = res_auth.json().get("authentication_token")
                        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                        
                        sucesso, falha, logs_lista = 0, 0, []

                        for idx, row in df.iterrows():
                            # Tentativa via PATCH para desvincular o veículo do dispositivo
                            device_identifier = str(row['id'])
                            url = f'https://api.cobli.co/v1/device-vehicle-association/{device_identifier}'
                            
                            r = requests.patch(url, json={"vehicle_id": None}, headers=headers)
                            
                            if r.status_code in [200, 204]:
                                sucesso += 1
                            else:
                                falha += 1
                                # Captura detalhada do log
                                logs_lista.append({
                                    "ID Usado": device_identifier,
                                    "Status": r.status_code,
                                    "Mensagem da API": r.text[:200]
                                })
                        
                        status.update(label=f"Processo Finalizado. Sucessos: {sucesso}", state="complete", expanded=False)
                        
                        # Resultados exibidos fora do st.status para persistência visual
                        with container_desassoc:
                            if sucesso > 0: 
                                st.success(f"✅ {sucesso} dispositivos desvinculados com sucesso!")
                            if falha > 0:
                                st.error(f"❌ {falha} falhas encontradas durante a desassociação.")
                                with st.expander("🔍 Ver Detalhes das Falhas", expanded=True):
                                    st.table(pd.DataFrame(logs_lista))
                    else:
                        st.error("Credenciais inválidas. Verifique sua senha API.")