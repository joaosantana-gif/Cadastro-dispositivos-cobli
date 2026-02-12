import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÕES FIXAS ---
SHEET_URL_READ = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCwT5_FsR4MqsYTuoLLuQd8tOZLBXPPsNZIcpNyO-7aZpFtN5u6YLvP3cv-YBSewznpw/exec"
SESSION_TIMEOUT = 3600  # 1 hora de sessão ativa
ID_BASE_COBLI = "12768cf5-e959-4f2a-a804-e0f8bbdcaeeb" # Frota ignorada pela trava

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerenciador Cobli", layout="centered")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'login_time' not in st.session_state:
    st.session_state.login_time = 0

# --- 2. CONTROLE DE SESSÃO E EXPIRAÇÃO ---
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
            st.error("Acesso negado. Verifique seu login e senha.")
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
                
                # SE FOR A BASE COBLI: Ignora a trava e permite associar
                if fleet_api == ID_BASE_COBLI.lower():
                    pass 
                
                # REGRA 1: Já está no mesmo Fleet ID da planilha
                elif fleet_api == fleet_planilha:
                    return {"imei": imei_alvo, "res": "Falha", "msg": "Dispositivo já está associado no fleet id informado"}
                
                # REGRA 2: Já está em outro Fleet ID real
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

if st.sidebar.button("Sair do Sistema"):
    st.session_state.clear()
    st.rerun()

if st.button("Sincronizar Planilha Google", use_container_width=True):
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL_READ)
        st.toast("Dados sincronizados")
    except:
        st.error("Falha ao carregar planilha.")

if 'dados_planilha' in st.session_state and st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    container_resultados = st.empty()

    if st.button("INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        with st.status("Validando frotas e processando...", expanded=True) as status:
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            t_fixo, u_fixo = st.session_state.token, st.session_state.user_email
            
            # Processamento em Threads (Alta Velocidade)
            with ThreadPoolExecutor(max_workers=5) as executor:
                resultados = list(executor.map(lambda r: processar_dispositivo(r[1], t_fixo, u_fixo), df.iterrows()))
            
            logs_nuvem = []
            for res in resultados:
                logs_nuvem.append({
                    "data_hora": data_atual, "imei": res["imei"], 
                    "resultado": res["res"], "mensagem": res["msg"], 
                    "nota": f"Ferramenta Python - Usuario: {u_fixo}"
                })

            # Envio de logs para a planilha via Apps Script
            try: requests.post(APPS_SCRIPT_URL, json=logs_nuvem, timeout=15)
            except: pass
                
            status.update(label="Processamento finalizado", state="complete")
            
            with container_resultados.container():
                st.divider()
                st.write("Relatório da Sessão")
                st.dataframe(pd.DataFrame(logs_nuvem), use_container_width=True, hide_index=True)