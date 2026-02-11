import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Importador Cobli", page_icon="🚚", layout="centered")

# --- 2. TÍTULO ---
st.title("Gerenciador de Dispositivos - Cobli")
st.caption("Ferramenta de Associação em Massa")
st.divider()

# --- 3. BARRA LATERAL ---
st.sidebar.header("🔑 Acesso Cobli")
email = st.sidebar.text_input("E-mail corporativo", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha API", type="password").strip()

if st.sidebar.button("🗑️ Limpar Sessão"):
    st.session_state.clear()
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. SINCRONIZAÇÃO ---
if st.button("🔄 Sincronizar Planilha Google", use_container_width=True): 
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
        st.toast("Dados carregados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")

# --- 5. EXECUÇÃO DA ASSOCIAÇÃO ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"### Dispositivos prontos para importar ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True) #

    if st.button("🚀 INICIAR ASSOCIAÇÃO EM MASSA", use_container_width=True, type="primary"):
        if not email or not password:
            st.error("Por favor, preencha o e-mail e a senha na barra lateral.")
        else:
            # st.status evita que a tela pareça congelada durante o processo
            with st.status("Iniciando importação...", expanded=True) as status:
                auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
                
                try:
                    # Timeout de 10s para evitar travamento na autenticação
                    res_auth = requests.post(auth_url, json={"email": email, "password": password}, timeout=10)
                    
                    if res_auth.status_code == 200:
                        token = res_auth.json().get("authentication_token")
                        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                        
                        sucesso, falha, logs = 0, 0, []
                        
                        for idx, row in df.iterrows():
                            # Atualiza a mensagem para o usuário acompanhar o progresso
                            status.update(label=f"Processando dispositivo {idx + 1} de {len(df)}...")
                            
                            payload = [{
                                "id": str(row['id']),
                                "imei": str(row['imei']),
                                "cobli_id": str(row['cobli_id']),
                                "type": str(row['type']),
                                "fleet_id": str(row['fleet_id'])
                            }]
                            
                            try:
                                # POST para o endpoint de importação
                                r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                                
                                if r.status_code in [200, 201]:
                                    sucesso += 1
                                else:
                                    falha += 1
                                    logs.append({"IMEI": row['imei'], "Status": r.status_code, "Resposta": r.text[:100]})
                            except requests.exceptions.Timeout:
                                falha += 1
                                logs.append({"IMEI": row['imei'], "Status": "Timeout", "Resposta": "Servidor demorou a responder"})

                        status.update(label=f"Processo concluído: {sucesso} Sucessos", state="complete")
                        
                        if sucesso > 0:
                            st.success(f"✅ {sucesso} dispositivos associados com sucesso!")
                        if falha > 0:
                            st.error(f"❌ {falha} dispositivos falharam.")
                            with st.expander("🔍 Ver detalhes das falhas"):
                                st.table(pd.DataFrame(logs))
                    else:
                        st.error("Erro na autenticação. Verifique suas credenciais.")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")