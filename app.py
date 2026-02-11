import streamlit as st
import pandas as pd
import requests

SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRirnHsHNFNULPC-fq3JyULMJT0ImV4f6ojJwblaL2CxeKQf7erAoGwCYF7hce8hiDB68WqD_9QcLcM/pub?output=csv"

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cadastro Cobli - Validação Ativa", page_icon="🚚", layout="centered")

# --- 2. TÍTULO ---
st.title("Cadastro de Dispositivos - Cobli")
st.caption("Versão com Verificação de Duplicidade e Rastreabilidade 🛡️")
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

# --- 4. ENTRADA DE DADOS ---
if st.button("🔄 Puxar da Planilha Google", use_container_width=True):
    try:
        st.session_state.dados_planilha = pd.read_csv(SHEET_URL)
        st.toast("Dados sincronizados!")
    except Exception as e:
        st.error(f"Erro: {e}")

# --- 5. EXECUÇÃO COM VALIDAÇÃO ---
if st.session_state.dados_planilha is not None:
    df = st.session_state.dados_planilha
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    if st.button("🚀 INICIAR CADASTRO EM MASSA", use_container_width=True, type="primary"):
        if not email or not password:
            st.error("❌ Preencha as credenciais.")
        else:
            with st.status("Validando acesso e duplicidades...", expanded=True) as status:
                res_auth = requests.post('https://api.cobli.co/herbie-1.1/account/authenticate', 
                                         json={"email": email, "password": password}, timeout=10)
                
                if res_auth.status_code == 200:
                    token = res_auth.json().get("authentication_token")
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    
                    sucesso, falha, ja_existente = 0, 0, 0
                    detalhes_execucao = []

                    for idx, row in df.iterrows():
                        imei_alvo = str(row['imei'])
                        status.update(label=f"Verificando IMEI {imei_alvo} ({idx+1}/{len(df)})...")
                        
                        # PASSO 1: Verificação Prévia (O dispositivo já existe/está associado?)
                        # Buscamos o dispositivo pelo IMEI para ver se ele já tem um vínculo
                        check_url = f'https://api.cobli.co/v1/devices?imei={imei_alvo}'
                        res_check = requests.get(check_url, headers=headers, timeout=10)
                        
                        dispositivo_ja_associado = False
                        if res_check.status_code == 200:
                            data = res_check.json()
                            # Se a lista não estiver vazia, o dispositivo já está no sistema
                            if len(data) > 0:
                                dispositivo_ja_associado = True

                        # PASSO 2: Lógica de Decisão
                        if dispositivo_ja_associado:
                            ja_existente += 1
                            detalhes_execucao.append({
                                "IMEI": imei_alvo,
                                "Resultado": "⚠️ Aviso",
                                "Status": "Pulei",
                                "Mensagem API": "Dispositivo já consta associado no sistema"
                            })
                        else:
                            # Tenta a importação apenas se não houver duplicidade
                            payload = [{
                                "id": str(row['id']), "imei": imei_alvo, "cobli_id": str(row['cobli_id']),
                                "type": str(row['type']), "icc_id": str(row['icc_id']),
                                "chip_number": str(row['chip_number']), "chip_operator": str(row['chip_operator']),
                                "fleet_id": str(row['fleet_id']),
                                "note": f"Cadastro via Automação - Usuário: {email}" # Rastreabilidade solicitada
                            }]
                            
                            try:
                                r = requests.post('https://api.cobli.co/v1/devices-import', json=payload, headers=headers, timeout=15)
                                if r.status_code in [200, 201]:
                                    sucesso += 1
                                    detalhes_execucao.append({"IMEI": imei_alvo, "Resultado": "✅ Sucesso", "Status": 201, "Mensagem API": "Novo vínculo criado"})
                                else:
                                    falha += 1
                                    detalhes_execucao.append({"IMEI": imei_alvo, "Resultado": "❌ Falha", "Status": r.status_code, "Mensagem API": r.text[:100]})
                            except:
                                falha += 1
                                detalhes_execucao.append({"IMEI": imei_alvo, "Resultado": "❌ Erro", "Status": "Timeout", "Mensagem API": "Conexão perdida"})

                    status.update(label="Processamento finalizado", state="complete")

                    # --- EXIBIÇÃO DO RELATÓRIO ---
                    st.divider()
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Novos Sucessos", sucesso)
                    c2.metric("Já Associados", ja_existente)
                    c3.metric("Falhas Reais", falha)

                    st.write("### 📜 Log Detalhado de Respostas")
                    log_df = pd.DataFrame(detalhes_execucao)
                    st.dataframe(log_df, use_container_width=True, hide_index=True) #
                else:
                    st.error("Falha na autenticação.")