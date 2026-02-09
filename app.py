import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cadastro de Dispositivos - Cobli", page_icon="🚚", layout="centered")

# --- 2. LOGO E TÍTULO ---
try:
    st.image("logo.png", width=180)
except:
    st.info("💡 Carregando sem logo local.")

st.title("Cadastro de Dispositivos - Cobli")
st.caption("Gerenciamento de Ativos e Associações via API")
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

# --- 5. INTERFACE PRINCIPAL (ABAS) ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"### Dispositivos Detectados ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True)

    tab1, tab2 = st.tabs(["🚀 Cadastro em Massa", "🗑️ Desassociar Veículos"])

    # --- ABA 1: CADASTRO ---
    with tab1:
        st.markdown("Esta ação associa os dispositivos às frotas e veículos configurados na planilha.")
        if st.button("🚀 INICIAR IMPORTAÇÃO", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Preencha o e-mail e a senha na lateral.")
            else:
                # Autenticação
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                res_auth = requests.post(auth_url, json={"email": email, "password": password})
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    import_url = 'https://api.cobli.co/v1/devices-import'
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha = 0, 0
                    progress = st.progress(0)
                    for idx, row in df.iterrows():
                        payload = [{
                            "id": str(row['id']), "imei": str(row['imei']),
                            "cobli_id": str(row['cobli_id']), "type": str(row['type']),
                            "icc_id": str(row['icc_id']), "chip_number": str(row['chip_number']),
                            "chip_operator": str(row['chip_operator']), "fleet_id": str(row['fleet_id'])
                        }]
                        r = requests.post(import_url, json=payload, headers=headers)
                        if r.status_code in [200, 201]: sucesso += 1
                        else: falha += 1
                        progress.progress((idx + 1) / len(df))
                    st.success(f"Cadastro Concluído! ✅ {sucesso} Sucessos | ❌ {falha} Falhas")
                else:
                    st.error("Credenciais inválidas.")

    # --- ABA 2: DESASSOCIAÇÃO ---
    with tab2:
        st.warning("⚠️ Esta ação removerá o rastreador do veículo no painel, mas ele continuará sendo um ativo da frota.")
        if st.button("⚠️ CONFIRMAR DESASSOCIAÇÃO", use_container_width=True):
            if not email or not password:
                st.error("Preencha o e-mail e a senha na lateral.")
            else:
                # Autenticação
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                res_auth = requests.post(auth_url, json={"email": email, "password": password})
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    headers = {'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha = 0, 0
                    progress = st.progress(0)
                    for idx, row in df.iterrows():
                        # Endpoint para remover o vínculo dispositivo-veículo
                        device_id = str(row['id'])
                        del_url = f'https://api.cobli.co/v1/device-vehicle-association/{device_id}'
                        
                        r = requests.delete(del_url, headers=headers)
                        
                        if r.status_code in [200, 204]:
                            sucesso += 1
                        else:
                            falha += 1
                        progress.progress((idx + 1) / len(df))
                    
                    st.success(f"Desassociação Concluída! ✅ {sucesso} Removidos | ❌ {falha} Falhas")
                else:
                    st.error("Credenciais inválidas.")