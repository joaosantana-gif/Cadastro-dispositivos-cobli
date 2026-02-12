import streamlit as st
import pandas as pd
import requests

# URL da sua planilha Google
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cadastro Cobli - Final", page_icon="🚚", layout="centered")

# --- 2. LOGO E TÍTULO ---
# Centralizando e restaurando o logo
try:
    st.image("logo.png", width=200)
except:
    st.info("💡 Coloque o arquivo 'logo.png' na pasta do projeto.")

st.title("Cadastro de Dispositivos - Cobli")
st.caption("Versão Estabilizada com Rastreabilidade e Logs Detalhados 🛡️")
st.divider()

# --- 3. BARRA LATERAL ---
st.sidebar.header("🔑 Acesso ao Sistema")
email = st.sidebar.text_input("E-mail Cobli", value="joao.santana@cobli.co").strip()
password = st.sidebar.text_input("Senha", type="password").strip()

if st.sidebar.button("🗑️ Limpar Dados"):
    st.session_state.clear()
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# --- 4. CARREGAMENTO ---
if st.button("🔄 Puxar da Planilha Google", use_container_width=True):
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
        st.toast("Dados sincronizados!", icon="✅")
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
            with st.status("Processando...", expanded=True) as status:
                res_auth = requests.post('https://api.cobli.co/herbie-1.1/account/authenticate', 
                                         json={"email": email, "password": password}, timeout=10)
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha, ja_registrado = 0, 0, 0
                    logs_execucao = []

                    for idx, row in df.iterrows():
                        imei_alvo = str(row['imei'])
                        nota_auditoria = f"Automação Python - Usuário: {email}" #
                        
                        # 1. Ajuste na verificação: O IMEI existe?
                        res_check = requests.get(f'https://api.cobli.co/v1/devices?imei={imei_alvo}', headers=headers, timeout=10)
                        
                        device_exists = False
                        if res_check.status_code == 200 and len(res_check.json()) > 0:
                            device_exists = True

                        # 2. Lógica de Importação
                        payload = [{
                            "id": str(row['id']), "imei": imei_alvo, "cobli_id": str(row['cobli_id']),
                            "type": str(row['type']), "icc_id": str(row['icc_id']),
                            "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']),
                            "fleet_id": str(row['fleet_id']),
                            "note": nota_auditoria # Enviando para a Cobli
                        }]

                        # Se já existe, avisamos mas tentamos a associação se for necessário atualizar
                        if device_exists:
                            ja_registrado += 1
                            logs_execucao.append({
                                "IMEI": imei_alvo,
                                "Resultado": "⚠️ Aviso",
                                "Mensagem API": "Dispositivo já registrado na base de dados Cobli",
                                "Nota Enviada": nota_auditoria
                            })
                        else:
                            try:
                                r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                                if r.status_code in [200, 201]:
                                    sucesso += 1
                                    logs_execucao.append({"IMEI": imei_alvo, "Resultado": "✅ Sucesso", "Mensagem API": "Novo vínculo criado", "Nota Enviada": nota_auditoria})
                                else:
                                    falha += 1
                                    logs_execucao.append({"IMEI": imei_alvo, "Resultado": "❌ Falha", "Mensagem API": f"Erro {r.status_code}", "Nota Enviada": nota_auditoria})
                            except:
                                falha += 1
                                logs_execucao.append({"IMEI": imei_alvo, "Resultado": "❌ Erro", "Mensagem API": "Timeout", "Nota Enviada": nota_auditoria})

                    status.update(label="Processamento finalizado", state="complete")

                    # --- EXIBIÇÃO ---
                    st.divider()
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Novos Sucessos", sucesso)
                    c2.metric("Já Registrados", ja_registrado)
                    c3.metric("Falhas", falha)

                    st.write("### 📜 Log Detalhado de Respostas")
                    log_df = pd.DataFrame(logs_execucao)
                    st.dataframe(log_df, use_container_width=True, hide_index=True)

                    # Restaurando o botão de download
                    csv = log_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Log de Execução (CSV)",
                        data=csv,
                        file_name="log_associacao_cobli.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.error("Falha na autenticação.")