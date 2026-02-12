import streamlit as st
import pandas as pd
import requests
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÕES ---
SHEET_URL_READ = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCwT5_FsR4MqsYTuoLLuQd8tOZLBXPPsNZIcpNyO-7aZpFtN5u6YLvP3cv-YBSewznpw/exec"
SESSION_TIMEOUT = 3600 
# ID da Base/Estoque da Cobli (ignorada pela trava)
ID_BASE_COBLI = "12768cf5-e959-4f2a-a804-e0f8bbdcaeeb" #

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", layout="centered")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'login_time' not in st.session_state:
    st.session_state.login_time = 0

# --- 2. CONTROLE DE ACESSO ---
if st.session_state.autenticado:
    if (time.time() - st.session_state.login_time) > SESSION_TIMEOUT:
        st.session_state.clear()
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
            st.error("Acesso negado")
    st.stop()

# --- 4. FUNÇÃO DE LIMPEZA DE ID (GARANTE COMPARAÇÃO EXATA) ---
def limpar_id(id_string):
    """Remove tudo que não for letra ou número para evitar falhas de comparação."""
    return re.sub(r'[^a-zA-Z0-9]', '', str(id_string)).lower()

# --- 5. FUNÇÃO DE PROCESSAMENTO ---
def processar_dispositivo(row, token, user_email):
    imei_alvo = str(row['imei']).strip()
    fleet_alvo_original = str(row['fleet_id']).strip()
    fleet_alvo_limpo = limpar_id(fleet_alvo_original)
    base_limpa = limpar_id(ID_BASE_COBLI)
    
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    nota_audit = f"Ferramenta Python - Usuario: {user_email}" #

    try:
        # Consulta de frota atual na Cobli
        check = requests.get(f'https://api.cobli.co/v1/devices?imei={imei_alvo}', headers=headers, timeout=10)
        
        if check.status_code == 200:
            dados = check.json()
            if dados and isinstance(dados, list) and len(dados) > 0:
                fleet_atual_limpo = limpar_id(dados[0].get('fleet_id', ''))
                
                # CASO 1: JÁ ESTÁ NA FROTA CERTA (Apenas aviso com texto combinado)
                if fleet_atual_limpo == fleet_alvo_limpo:
                    return {"imei": imei_alvo, "res": "Aviso", "msg": "Dispositivo já conta associado"} #
                
                # CASO 2: ESTÁ EM OUTRA FROTA REAL (Bloqueio de segurança)
                elif fleet_atual_limpo != base_limpa:
                    return {"imei": imei_alvo, "res": "Falha", "msg": f"Bloqueado: associado a frota {dados[0].get('fleet_id')}"} #

        # CASO 3: ESTÁ NA BASE OU É NOVO (Realiza a associação)
        payload = [{
            "id": str(row['id']), "imei": imei_alvo, "cobli_id": str(row['cobli_id']),
            "type": str(row['type']), "icc_id": str(row['icc_id']),
            "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']),
            "fleet_id": fleet_alvo_original, "note": nota_audit
        }]
        
        r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=10)
        
        if r.status_code in [200, 201]:
            return {"imei": imei_alvo, "res": "Sucesso", "msg": "Associacao realizada"} #
        return {"imei": imei_alvo, "res": "Falha", "msg": f"Erro API {r.status_code}"}
        
    except:
        return {"imei": imei_alvo, "res": "Erro", "msg": "Sem resposta"}

# --- 6. PAINEL PRINCIPAL ---
try: st.image("logo.png", width=220)
except: pass
st.title("Cadastro de Dispositivos - Cobli")
st.caption(f"Sessão ativa: {st.session_state.user_email}")
st.divider()

if st.sidebar.button("Sair do Sistema"):
    st.session_state.clear()
    st.rerun()

if st.button("Sincronizar Planilha Google", use_container_width=True):
    st.session_state.dados_planilha = pd.read_csv(SHEET_URL_READ)
    st.toast("Dados sincronizados")

if 'dados_planilha' in st.session_state and st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    container_resultados = st.empty()

    if st.button("INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        with st.status("Processando...", expanded=True) as status:
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            t_fixo, u_fixo = st.session_state.token, st.session_state.user_email
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                resultados = list(executor.map(lambda r: processar_dispositivo(r[1], t_fixo, u_fixo), df.iterrows()))
            
            logs_nuvem = []
            for res in resultados:
                logs_nuvem.append({
                    "data_hora": data_atual, "imei": res["imei"],
                    "resultado": res["res"], "mensagem": res["msg"], "nota": f"Ferramenta Python - Usuario: {u_fixo}"
                })

            # Gravação no Google Sheets
            requests.post(APPS_SCRIPT_URL, json=logs_nuvem, timeout=15)
            status.update(label="Processo concluído", state="complete")
            
            with container_resultados.container():
                st.divider()
                st.write("Relatório da Sessão (Sincronizado com Nuvem)")
                st.dataframe(pd.DataFrame(logs_nuvem), use_container_width=True, hide_index=True)