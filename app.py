import streamlit as st
import pandas as pd
import requests
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÕES DE INTEGRAÇÃO ---
SHEET_URL_READ = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCwT5_FsR4MqsYTuoLLuQd8tOZLBXPPsNZIcpNyO-7aZpFtN5u6YLvP3cv-YBSewznpw/exec"

# Configurações de Sessão e Regras de Negócio
SESSION_TIMEOUT = 3600  # 1 hora de sessão
ID_BASE_COBLI = "12768cf5-e959-4f2a-a804-e0f8bbdcaeeb" # Frota de estoque (sempre permitida)

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", layout="centered")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'login_time' not in st.session_state:
    st.session_state.login_time = 0

# --- 2. CONTROLE DE SESSÃO ---
if st.session_state.autenticado:
    if (time.time() - st.session_state.login_time) > SESSION_TIMEOUT:
        st.session_state.clear()
        st.warning("Sessão expirada. Por favor, faça login novamente.")
        st.rerun()

# --- 3. TELA DE LOGIN ---
if not st.session_state.autenticado:
    try: st.image("logo.png", width=220)
    except: pass
    st.title("Acesso ao Sistema")
    login_email = st.text_input("E-mail corporativo", placeholder="seu.email@cobli.co").strip()
    login_password = st.text_input("Senha", type="password").strip()
    
    if st.button("Entrar", use_container_width=True, type="primary"):
        res_auth = requests.post('https://api.cobli.co/herbie-1.1/account/authenticate', 
                                 json={"email": login_email, "password": login_password}, timeout=10)
        if res_auth.status_code == 200:
            st.session_state.autenticado = True
            st.session_state.token = res_auth.json().get("authentication_token")
            st.session_state.user_email = login_email
            st.session_state.login_time = time.time()
            st.rerun()
        else:
            st.error("Acesso negado. Verifique suas credenciais.")
    st.stop()

# --- 4. FUNÇÃO DE PROCESSAMENTO COM REGRAS ESTRITAS ---
def processar_dispositivo(row, token, user_email):
    imei_alvo = str(row['imei']).strip()
    fleet_planilha = str(row['fleet_id']).strip().lower()
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    nota_audit = f"Ferramenta Python - Usuario: {user_email}" # Rastreabilidade

    try:
        # Passo 1: Verificar situação atual na API
        check = requests.get(f'https://api.cobli.co/v1/devices?imei={imei_alvo}', headers=headers, timeout=10)
        if check.status_code == 200:
            dados = check.json()
            if dados and len(dados) > 0:
                fleet_api = str(dados[0].get('fleet_id', '')).strip().lower()
                
                # EXCEÇÃO: Frota base da Cobli (permite associar)
                if fleet_api == ID_BASE_COBLI.lower():
                    pass 
                
                # REGRA 1: Já associado ao mesmo Fleet ID informado
                elif fleet_api == fleet_planilha:
                    return {"imei": imei_alvo, "res": "Falha", "msg": "Dispositivo já está associado no fleet id informado"}
                
                # REGRA 2: Já associado a outro Fleet ID real
                else:
                    return {"imei": imei_alvo, "res": "Falha", "msg": "Dispositivo já está associado a outro Fleet ID"}

        # Passo 2: Executar Associação (Só para novos ou vindos da Base)
        payload = [{
            "id": str(row['id']), "imei": imei_alvo, "cobli_id": str(row['cobli_id']),
            "type": str(row['type']), "icc_id": str(row['icc_id']),
            "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']),
            "fleet_id": fleet_planilha, "note": nota_audit
        }]
        
        r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=12)
        if r.status_code in [200, 201]:
            return {"imei": imei_alvo, "res": "Sucesso", "msg": "Associacao realizada"}
        return {"imei": imei_alvo, "res": "Falha", "msg": f"Erro API {r.status_code}"}
    except:
        return {"imei": imei_alvo, "res": "Erro", "msg": "Sem resposta da API"}

# --- 5. PAINEL PRINCIPAL ---
try: st.image("logo.png", width=220)
except: pass
st.title("Cadastro de Dispositivos - Cobli")
st.caption(f"Sessão ativa: {st.session_state.user_email}")
st.divider()

if st.sidebar.button("Sair