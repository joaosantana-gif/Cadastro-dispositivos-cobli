import streamlit as st
import pandas as pd
import requests
import time

SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gerenciador Cobli", page_icon="🚚", layout="centered")

# --- 2. LOGO E TÍTULO ---
try:
    st.image("logo.png", width=180) 
except:
    pass

st.title("Gerenciador de Dispositivos - Cobli")
st.caption("Versão Estabilizada - Automação de Frota")
st.divider()

# --- 3. PERSISTÊNCIA DE DADOS ---
if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# Barra lateral
st.sidebar.header("🔑 Acesso Cobli")
email = st.sidebar.text_input("E-mail corporativo", placeholder="seu.nome@cobli.co").strip()
password = st.sidebar.text_input("Senha API", type="password").strip()

if st.sidebar.button("🗑️ Limpar Sessão"):
    st.session_state.dados_planilha = None
    st.rerun()

# --- 4. CARREGAMENTO ---
if st.button("🔄 Sincronizar Planilha Google", use_container_width=True): 
    with st.spinner("Sincronizando..."):
        try:
            st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
            st.toast("Dados atualizados!", icon="✅")
        except Exception as e:
            st.error(f"Erro na planilha: {e}")

# --- 5. INTERFACE PRINCIPAL ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"### Dispositivos na Planilha ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True) 

    # Abas
    tab1, tab2 = st.tabs(["🔗 Associar dispositivo", "🔓 Desassociar dispositivo"])

    # --- ABA 1: ASSOCIAÇÃO ---
    with tab1:
        if st.button("🚀 INICIAR ASSOCIAÇÃO EM MASSA", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Preencha o acesso na lateral.")
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
                            payload = [{"id": str(row['id']), "imei": str(row['imei']), "cobli_id": str(row['cobli_id']), "type": str(row['type']), "icc_id": str(row['icc_id']), "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']), "fleet_id": str(row['fleet_id'])}]
                            r = requests.post(import_url, json=payload, headers=headers)
                            if r.status_code in [200, 201]: sucesso += 1
                            else:
                                falha += 1
                                logs.append({"IMEI": row['imei'], "Erro": r.status_code})
                        
                        status.update(label=f"Concluído! {sucesso} Sucessos.", state="complete", expanded=False)
                        if logs: st.error(f"{falha} falhas detectadas. Verifique os logs.")
                    else:
                        st.error("Falha no login.")

    # --- ABA 2: DESASSOCIAÇÃO ---
    with tab2:
        st.warning("⚠️ Esta ação removerá o rastreador do painel") #
        if st.button("⚠️ CONFIRMAR DESASSOCIAÇÃO EM MASSA", use_container_width=True):
            if not email or not password:
                st.error("Acesso necessário.")
            else:
                # Usamos st.status para evitar o "flicker" (piscar) da página
                with st.status("Executando desassociação...", expanded=True) as status:
                    auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                    res_auth = requests.post(auth_url, json={"email": email, "password": password})
                    
                    if res_auth.status_code == 200:
                        token = res_auth.json().get("authentication_token")
                        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                        sucesso, falha, logs_erro = 0, 0, []
                        
                        for idx, row in df.iterrows():
                            device_id = str(row['id'])
                            # Usando o endpoint de associação para desplugar
                            patch_url = f'https://api.cobli.co/v1/device-vehicle-association/{device_id}'
                            r = requests.patch(patch_url, json={"vehicle_id": None}, headers=headers)
                            
                            if r.status_code in [200, 204]: sucesso += 1
                            else:
                                falha += 1
                                logs_erro.append({"ID": device_id, "Status": r.status_code, "Resposta API": r.text})
                        
                        status.update(label=f"Processo Finalizado. Sucessos: {sucesso}", state="complete", expanded=False)
                        if logs_erro:
                            st.write("### 🔍 Ver Log de Erros Detalhado")
                            st.table(pd.DataFrame(logs_erro)) #
                    else:
                        st.error("Credenciais inválidas.")