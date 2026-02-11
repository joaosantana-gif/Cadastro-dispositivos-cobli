import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Cadastro de Dispositivos - Cobli", 
    page_icon="🚚",
    layout="centered"
)

# --- 2. LOGO E TÍTULO ---
try:
    st.image("logo.png", width=200)
except Exception:
    pass

st.title("Cadastro de Dispositivos - Cobli")
st.caption("Automação com rastreabilidade interna e logs detalhados")
st.divider()

# --- 3. MEMÓRIA E BARRA LATERAL ---
if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

st.sidebar.header("🔑 Acesso ao Sistema")
email = st.sidebar.text_input("E-mail Cobli", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha", type="password").strip()

if st.sidebar.button("🗑️ Limpar Dados da Tela"):
    st.session_state.dados_planilha = None
    st.rerun()

# --- 4. ENTRADA DE DADOS ---
if st.button("🔄 Puxar da Planilha Google", use_container_width=True):
    with st.spinner("Sincronizando..."):
        try:
            st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
            st.success("Planilha atualizada!")
        except Exception as e:
            st.error(f"Erro: {e}")

# --- 5. EXECUÇÃO ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"### Fila de Processamento ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    if st.button("🚀 INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        if not email or not password:
            st.error("❌ Preencha as credenciais na barra lateral.")
        else:
            auth_url = 'https://api.cobli.co/herbie-1.1/account/authenticate'
            
            with st.spinner('Validando acesso de administrador...'): #
                res_auth = requests.post(auth_url, json={"email": email, "password": password})
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    import_url = 'https://api.cobli.co/v1/devices-import'
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha = 0, 0
                    # Nova estrutura de logs para rastreabilidade total
                    detalhes_execucao = []
                    
                    progress = st.progress(0)
                    status_text = st.empty()

                    for idx, row in df.iterrows():
                        status_text.text(f"Processando: {idx + 1} de {len(df)}")
                        
                        # Payload com campo 'note' para auditoria interna
                        payload = [{
                            "id": str(row['id']),
                            "imei": str(row['imei']),
                            "cobli_id": str(row['cobli_id']),
                            "type": str(row['type']),
                            "icc_id": str(row['icc_id']),
                            "chip_number": str(row['chip_number']),
                            "chip_operator": str(row['chip_operator']),
                            "fleet_id": str(row['fleet_id']),
                            "note": f"Cadastro via Automação Python - Usuário: {email}"
                        }]
                        
                        try:
                            r = requests.post(import_url, json=payload, headers=headers, timeout=15)
                            resultado = "✅ Sucesso" if r.status_code in [200, 201] else "❌ Falha"
                            
                            if r.status_code in [200, 201]: sucesso += 1
                            else: falha += 1
                            
                            # Registra log positivo ou negativo
                            detalhes_execucao.append({
                                "IMEI": row['imei'],
                                "Resultado": resultado,
                                "Status": r.status_code,
                                "Mensagem API": r.text[:150] # Captura resposta curta
                            })
                        except Exception as e:
                            falha += 1
                            detalhes_execucao.append({
                                "IMEI": row['imei'], "Resultado": "⚠️ Erro Crítico", "Status": "N/A", "Mensagem API": str(e)
                            })
                        
                        progress.progress((idx + 1) / len(df))

                    # --- RELATÓRIO FINAL ---
                    st.divider()
                    c1, c2 = st.columns(2)
                    c1.metric("Sucessos", sucesso)
                    c2.metric("Falhas", falha)

                    st.write("### 📜 Log Completo de Respostas")
                    log_df = pd.DataFrame(detalhes_execucao)
                    st.dataframe(log_df, use_container_width=True, hide_index=True)
                    
                    # Botão para baixar o log
                    st.download_button(
                        label="📥 Baixar Log em CSV",
                        data=log_df.to_csv(index=False).encode('utf-8'),
                        file_name="log_associacao_cobli.csv",
                        mime="text/csv"
                    )

                    if sucesso == len(df):
                        st.balloons()
                else:
                    st.error("❌ Falha na autenticação (Erro 401/403).") #