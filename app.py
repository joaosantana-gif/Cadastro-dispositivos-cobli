import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÕES DE INTEGRAÇÃO ---
SHEET_URL_READ = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCwT5_FsR4MqsYTuoLLuQd8tOZLBXPPsNZIcpNyO-7aZpFtN5u6YLvP3cv-YBSewznpw/exec"

# Configurações de Sessão e Regras de Negócio
SESSION_TIMEOUT = 3600  # 1 hora em segundos
ID_BASE_COBLI = "12768cf5-e959-4f2a-a804-e0f8bbdcaeeb" # Frota desconsiderada na trava

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", layout="centered")

# Inicialização do estado do sistema
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'login_time' not in st.session_state:
    st.session_state.login_time = 0

# --- 2. CONTROLE DE ACESSO E EXPIRAÇÃO ---
if st.session_state.autenticado:
    # Verifica se a sessão expirou
    if (time.time() - st.session_state.login_time) > SESSION_TIMEOUT:
        st.session_state.clear()
        st.warning("Sessão expirada. Por favor, faça login novamente.")
        st.rerun()

# --- 3. TELA DE LOGIN (SÓ LIBERA O ACESSO SE AUTENTICAR NA COBLI) ---
if not st.session_state.autenticado:
    try:
        st.image("logo.png", width=220)
    except:
        pass
        
    st.title("Acesso ao Sistema")
    st.write("Insira suas credenciais corporativas.")
    
    login_email = st.text_input("E-mail corporativo", placeholder="exemplo@cobli.co").strip()
    login_password = st.text_input("Senha", type="password").strip()
    
    if st.button("Entrar", use_container_width=True, type="primary"):
        if login_email and login_password:
            with st.spinner("Validando..."):
                res_auth = requests.post('https://api.cobli.co/herbie-1.1/account/authenticate', 
                                         json={"email": login_email, "password": login_password}, timeout=10)
                
                if res_auth.status_code == 200:
                    st.session_state.autenticado = True
                    st.session_state.token = res_auth.json().get("authentication_token")
                    st.session_state.user_email = login_email
                    st.session_state.login_time = time.time()
                    st.rerun()
                else:
                    st.error("Credenciais inválidas ou sem permissão de acesso.")
    st.stop()

# --- 4. FUNÇÃO DE PROCESSAMENTO COM REGRAS ESTRITAS ---
def processar_dispositivo(row, token, user_email):
    imei_alvo = str(row['ime