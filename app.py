import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÕES FIXAS ---
SHEET_URL_READ = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCwT5_FsR4MqsYTuoLLuQd8tOZLBXPPsNZIcpNyO-7aZpFtN5u6YLvP3cv-YBSewznpw/exec"
SESSION_TIMEOUT = 3600 
ID_BASE_COBLI = "12768cf5-e959-4f2a-a804-e0f8bbdcaeeb" # Frota ignorada pela trava

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

# --- 4. FUNÇÃO DE PROCESSAMENTO COM EXCEÇÃO PARA BASE COBLI ---
def processar_dispositivo(row, token, user_email):
    imei_alvo = str(row['imei'])
    fleet_alvo = str(row['fleet_id'])
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    nota = f"Ferramenta Python - Usuario: {user_email}" # Rastreabilidade

    try:
        # Consulta de frota atual
        check = requests.get(f'https://api.cobli.co/v1/devices?imei={imei_alvo}', headers=headers, timeout=10)
        if check.status_code == 200:
            dados = check.json()
            if dados and len(dados) > 0:
                fleet_atual = str(dados[0].get('fleet_id'))
                
                # SE JÁ ESTÁ NA FROTA ALVO: Aviso
                if fleet_atual == fleet_alvo:
                    return {"imei": imei_alvo, "res": "Aviso", "msg": "Ja associado a esta frota"}
                
                # SE ESTÁ NA BASE COBLI OU É NOVO: Permite seguir para a associação
                elif fleet_atual == ID_BASE_COBLI:
                    pass 
                
                # SE ESTÁ EM QUALQUER OUTRA FROTA REAL: Bloqueio
                else:
                    return {"imei": imei_alvo, "res": "Falha", "msg": f"Bloqueado: associado a frota {fleet_atual}"}

        # Importação / Vínculo
        payload = [{
            "id": str(row['id']), "imei": imei_alvo, "cobli_id": str(row['cobli_id']),
            "type": str(row['type']), "icc_id": str(row['icc_id']),
            "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']),
            "fleet_id": fleet_alvo, "note": nota
        }]
        
        r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=10)
        if r.status_code in [200, 201]: return {"imei": imei_alvo, "res": "Sucesso", "msg": "Associacao realizada"}
        return {"imei": imei_alvo, "res": "Falha", "msg": f"Erro API {r.status_code}"}
    except:
        return {"imei": imei_alvo, "res": "Erro", "msg": "Timeout"}

# --- 5. PAINEL PRINCIPAL ---
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
            token_fixo = st.session_state.token
            user_fixo = st.session_state.user_email
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                resultados = list(executor.map(lambda r: processar_dispositivo(r[1], token_fixo, user_fixo), df.iterrows()))
            
            logs_nuvem = []
            for res in resultados:
                logs_nuvem.append({"data_hora": data_atual, "imei": res["imei"], "resultado": res["res"], "mensagem": res["msg"], "nota": f"Ferramenta Python - Usuario: {user_fixo}"})

            requests.post(APPS_SCRIPT_URL, json=logs_nuvem, timeout=15)
            status.update(label="Processo concluído", state="complete")
            
            with container_resultados.container():
                st.divider()
                st.write("Relatório da Sessão")
                st.dataframe(pd.DataFrame(logs_nuvem), use_container_width=True, hide_index=True)