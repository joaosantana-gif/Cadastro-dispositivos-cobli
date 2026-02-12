import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- CONFIGURAÇÕES DE INTEGRAÇÃO ---
SHEET_URL_READ = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCwT5_FsR4MqsYTuoLLuQd8tOZLBXPPsNZIcpNyO-7aZpFtN5u6YLvP3cv-YBSewznpw/exec"
SESSION_TIMEOUT = 10  # Tempo em segundos (3600s = 1 hora)

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", layout="centered")

# Inicialização do estado da sessão
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'login_time' not in st.session_state:
    st.session_state.login_time = 0

# --- 2. VERIFICAÇÃO DE EXPIRAÇÃO (CONTROLO DE ACESSO) ---
if st.session_state.autenticado:
    tempo_passado = time.time() - st.session_state.login_time
    if tempo_passado > SESSION_TIMEOUT:
        st.session_state.clear()
        st.warning("A sua sessão expirou por segurança. Por favor, faça login novamente.")
        st.rerun()

# --- 3. TELA DE LOGIN ---
if not st.session_state.autenticado:
    try:
        st.image("logo.png", width=220)
    except:
        pass
        
    st.title("Acesso ao Sistema")
    login_email = st.text_input("E-mail corporativo", placeholder="seu.email@cobli.co").strip()
    login_password = st.text_input("Senha", type="password").strip()
    
    if st.button("Entrar", use_container_width=True, type="primary"):
        with st.spinner("Validando acesso..."):
            res_auth = requests.post('https://api.cobli.co/herbie-1.1/account/authenticate', 
                                     json={"email": login_email, "password": login_password}, timeout=10)
            
            if res_auth.status_code == 200:
                st.session_state.autenticado = True
                st.session_state.token = res_auth.json().get("authentication_token")
                st.session_state.user_email = login_email
                st.session_state.login_time = time.time() # Regista o início da sessão
                st.rerun()
            else:
                st.error("Acesso negado. Verifique as suas credenciais.")
    st.stop()

# --- 4. PAINEL PRINCIPAL (AUTORIZADO) ---
try:
    st.image("logo.png", width=220)
except:
    pass

st.title("Cadastro de Dispositivos - Cobli")
st.caption(f"Sessão ativa: {st.session_state.user_email}")
st.divider()

# Botão de Logout na barra lateral
if st.sidebar.button("Sair do Sistema"):
    st.session_state.clear()
    st.rerun()

if 'dados_planilha' not in st.session_state:
    st.session_state.dados_planilha = None

# Sincronização de dados
if st.button("Sincronizar Planilha Google", use_container_width=True):
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL_READ)
        st.toast("Dados sincronizados")
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")

# Processamento em Massa
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.write(f"Itens na fila: {len(df)}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    container_resultados = st.empty()

    if st.button("INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        with st.status("Processando e Gravando Logs...", expanded=True) as status:
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {st.session_state.token}'}
            sucesso, falha, logs_para_nuvem = 0, 0, []
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            for idx, row in df.iterrows():
                imei_alvo = str(row['imei'])
                nota_auditoria = f"Ferramenta Python - Usuario: {st.session_state.user_email}"
                
                payload = [{
                    "id": str(row['id']), "imei": imei_alvo, "cobli_id": str(row['cobli_id']),
                    "type": str(row['type']), "icc_id": str(row['icc_id']),
                    "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']),
                    "fleet_id": str(row['fleet_id']), "note": nota_auditoria
                }]

                try:
                    r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                    
                    if r.status_code in [200, 201]:
                        sucesso += 1
                        msg_api, res_texto = "Sucesso na associacao", "Sucesso"
                    elif r.status_code == 409: # Mapeamento solicitado
                        falha += 1
                        msg_api, res_texto = "Dispositivo ja consta associado", "Falha"
                    else:
                        falha += 1
                        msg_api, res_texto = f"Erro {r.status_code}", "Falha"

                    logs_para_nuvem.append({
                        "data_hora": data_atual, "imei": imei_alvo,
                        "resultado": res_texto, "mensagem": msg_api, "nota": nota_auditoria
                    })
                except:
                    falha += 1
                    logs_para_nuvem.append({
                        "data_hora": data_atual, "imei": imei_alvo, 
                        "resultado": "Erro", "mensagem": "Sem resposta", "nota": nota_auditoria
                    })

            # Envio para Google Sheets (via Apps Script URL)
            try:
                requests.post(APPS_SCRIPT_URL, json=logs_para_nuvem, timeout=15)
                status.update(label=f"Concluído: {sucesso} Sucessos. Logs gravados na nuvem.", state="complete")
            except:
                status.update(label="Processamento feito, mas erro ao gravar logs na planilha.", state="error")

            with container_resultados.container():
                st.divider()
                st.write("Log da Sessão (Enviado para Nuvem)")
                log_df = pd.DataFrame(logs_para_nuvem)
                st.dataframe(log_df, use_container_width=True, hide_index=True)