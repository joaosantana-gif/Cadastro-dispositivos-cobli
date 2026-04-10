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
SESSION_TIMEOUT = 3600  
ID_BASE_COBLI = "12768cf5-e959-4f2a-a804-e0f8bbdcaeeb" 

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

# --- 4. FUNÇÃO DE LIMPEZA DE DADOS VAZIOS (ATUALIZADA) ---
def limpar_valor(val):
    """Destrói dados ausentes ou palavras como 'None' geradas pelo conversor de texto."""
    if pd.isna(val): return ""
    texto = str(val).strip()
    # Bloqueia as palavras que o sistema gera quando a célula está vazia
    if texto.lower() in ['nan', 'none', 'null', '']: 
        return ""
    return texto

# --- 5. FUNÇÃO DE PROCESSAMENTO COM REGRA DE EXCEÇÃO ---
def processar_dispositivo(row, token, user_email):
    imei_alvo = limpar_valor(row.get('imei', ''))
    cobli_id = limpar_valor(row.get('cobli_id', ''))
    id_alvo = limpar_valor(row.get('id', ''))
    fleet_planilha = limpar_valor(row.get('fleet_id', '')).lower()
    
    # Identificador para o log (Usa IMEI se existir, caso contrário usa Cobli ID)
    identificador_log = imei_alvo if imei_alvo else (cobli_id if cobli_id else id_alvo)

    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    nota_audit = f"Ferramenta Python - Usuario: {user_email}"

    try:
        # Passo 1: Verificar situação atual na API (APENAS SE TIVER IMEI)
        if imei_alvo:
            check = requests.get(f'https://api.cobli.co/v1/devices?imei={imei_alvo}', headers=headers, timeout=10)
            if check.status_code == 200:
                dados = check.json()
                if dados and len(dados) > 0:
                    fleet_api = str(dados[0].get('fleet_id', '')).strip().lower()
                    
                    if fleet_api == ID_BASE_COBLI.lower():
                        pass 
                    elif fleet_api == fleet_planilha:
                        return {"imei": identificador_log, "res": "Falha", "msg": "Dispositivo já está associado no fleet id informado"} 
                    else:
                        return {"imei": identificador_log, "res": "Falha", "msg": "Dispositivo já está associado a outro Fleet ID"} 

        # Passo 2: Montar o Payload apenas com as colunas reais e validadas
        dispositivo_payload = {
            "fleet_id": fleet_planilha,
            "note": nota_audit
        }
        
        if id_alvo: dispositivo_payload["id"] = id_alvo
        if imei_alvo: dispositivo_payload["imei"] = imei_alvo
        if cobli_id: dispositivo_payload["cobli_id"] = cobli_id
        
        # Adiciona colunas opcionais APENAS se não forem "None" ou vazias
        for campo in ['type', 'icc_id', 'chip_number', 'chip_operator']:
            val = limpar_valor(row.get(campo, ''))
            if val:
                dispositivo_payload[campo] = val

        # Passo 3: Enviar para API
        r = requests.post('https://api.cobli.co/v1/devices-import', json=[dispositivo_payload], headers=headers, timeout=12)
        if r.status_code in [200, 201]:
            return {"imei": identificador_log, "res": "Sucesso", "msg": "Associacao realizada"} 
        return {"imei": identificador_log, "res": "Falha", "msg": f"Erro API {r.status_code}"}
    except:
        return {"imei": identificador_log, "res": "Erro", "msg": "Sem resposta da API"}

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
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL_READ, dtype=str)
        st.toast("Dados sincronizados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")

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
                    "resultado": res["res"], "mensagem": res["msg"], 
                    "nota": f"Ferramenta Python - Usuario: {u_fixo}"
                })

            try: requests.post(APPS_SCRIPT_URL, json=logs_nuvem, timeout=15)
            except: pass
                
            status.update(label="Processamento finalizado", state="complete")
            
            with container_resultados.container():
                st.divider()
                st.write("Relatório da Sessão")
                st.dataframe(pd.DataFrame(logs_nuvem), use_container_width=True, hide_index=True)