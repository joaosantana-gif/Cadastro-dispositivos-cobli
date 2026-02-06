import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA (Aba do Navegador) ---
st.set_page_config(
    page_title="Cadastro de Dispositivos - Cobli", 
    page_icon="🚚",
    layout="centered"
)

# --- 2. LOGO E TÍTULO PRINCIPAL ---
# Tenta carregar o logo local 'logo.png'
try:
    st.image("logo.png", width=200)
except Exception:
    st.info("💡 Para exibir seu logo, certifique-se de que o arquivo se chama 'logo.png' e está na pasta C:\\associacao")

st.title("Cadastro de Dispositivos - Cobli")
st.caption("Automação para ativação de hardware via API")
st.divider()

# --- 3. MEMÓRIA DO SISTEMA (Session State) ---
if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. BARRA LATERAL (Credenciais) ---
st.sidebar.header("🔑 Acesso ao Sistema")
email = st.sidebar.text_input("E-mail Cobli", placeholder="seu.email@cobli.co").strip()
password = st.sidebar.text_input("Senha", type="password").strip()

st.sidebar.divider()
if st.sidebar.button("🗑️ Limpar Dados da Tela"):
    st.session_state.dados_planilha = None
    st.rerun()

# --- 5. INTERFACE DE ENTRADA DE DADOS ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Puxar da Planilha Google", use_container_width=True, type="secondary"):
        with st.spinner("Sincronizando com a nuvem..."):
            try:
                st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
                st.success("Planilha atualizada!")
            except Exception as e:
                st.error(f"Erro ao acessar Google Sheets: {e}")

with col2:
    with st.popover("📁 Upload Manual de CSV", use_container_width=True):
        uploaded_file = st.file_uploader("Escolha o arquivo", type=["csv"])
        if uploaded_file:
            st.session_state.dados_planilha = pd.read_csv(uploaded_file)
            st.success("Arquivo carregado com sucesso!")

# --- 6. VISUALIZAÇÃO E EXECUÇÃO ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    
    st.write(f"### Dispositivos na Fila ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Botão de Ação Principal
    if st.button("🚀 INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        if not email or not password:
            st.error("❌ Erro: Insira seu e-mail e senha na barra lateral.")
        else:
            # Etapa 1: Autenticação
            auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
            auth_payload = {"email": email, "password": password}
            
            with st.spinner('Validando acesso...'):
                res_auth = requests.post(auth_url, json=auth_payload)
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    st.toast("Autenticado com sucesso!", icon="🔑")
                    
                    # Etapa 2: Cadastro dos Dispositivos
                    import_url = 'https://api.cobli.co/v1/devices-import'
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha, logs = 0, 0, []
                    progress = st.progress(0)
                    status_text = st.empty()

                    for idx, row in df.iterrows():
                        # Montagem do payload conforme exigência da API
                        payload = [{
                            "id": str(row['id']),
                            "imei": str(row['imei']),
                            "cobli_id": str(row['cobli_id']),
                            "type": str(row['type']),
                            "icc_id": str(row['icc_id']),
                            "chip_number": str(row['chip_number']),
                            "chip_operator": str(row['chip_operator']),
                            "fleet_id": str(row['fleet_id'])
                        }]
                        
                        try:
                            r = requests.post(import_url, json=payload, headers=headers)
                            if r.status_code in [200, 201]:
                                sucesso += 1
                            else:
                                falha += 1
                                logs.append(f"❌ Erro no IMEI {row['imei']}: {r.text}")
                        except Exception as e:
                            falha += 1
                            logs.append(f"⚠️ Erro crítico na linha {idx+1}: {e}")
                        
                        # Atualização visual do progresso
                        progress.progress((idx + 1) / len(df))
                        status_text.text(f"Processando: {idx + 1} de {len(df)}")

                    # Relatório de Resultado
                    st.divider()
                    res_c1, res_c2 = st.columns(2)
                    res_c1.metric("Sucesso ✅", sucesso)
                    res_c2.metric("Falha ❌", falha)

                    if logs:
                        with st.expander("Clique para ver os detalhes das falhas"):
                            for log in logs:
                                st.write(log)
                    
                    if sucesso == len(df):
                        st.balloons()
                        st.success("Todos os dispositivos foram cadastrados perfeitamente!")
                else:
                    st.error("❌ Senha ou e-mail incorretos. Tente novamente.")