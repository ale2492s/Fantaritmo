import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import re
import datetime
import extra_streamlit_components as stx
from PIL import Image
import pytesseract
from thefuzz import process, fuzz  # Importato fuzz per le regole rigorose

# -----------------------------------------------------------------------------
# 1. CONFIGURAZIONE PAGINA STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Algo-Custom | Fantacalcio Advisory App",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Algo-Custom: Schiera la Formazione Ideale")
st.caption("Il tuo assistente algoritmico personalizzato per vincere al Fantacalcio")

# -----------------------------------------------------------------------------
# 2. CARICAMENTO DATABASE SERIE A
# -----------------------------------------------------------------------------
@st.cache_data
def load_database():
    df = pd.read_excel('statistiche.csv', header=1)
    
    calendario = {
        "Monza": "Sassuolo", "Sassuolo": "Monza", "Bologna": "Torino", "Torino": "Bologna",
        "Udinese": "Cagliari", "Cagliari": "Udinese", "Roma": "Inter", "Inter": "Roma",
        "Venezia": "Lazio", "Lazio": "Venezia", "Fiorentina": "Napoli", "Napoli": "Fiorentina",
        "Frosinone": "Como", "Como": "Frosinone", "Parma": "Genoa", "Genoa": "Parma",
        "Juventus": "Atalanta", "Atalanta": "Juventus", "Milan": "Lecce", "Lecce": "Milan"
    }
    squadre_in_casa = ["Monza", "Bologna", "Udinese", "Roma", "Venezia", "Fiorentina", "Frosinone", "Parma", "Juventus", "Milan"]
    rigoristi = ["Calhanoglu", "Vlahovic", "Dybala", "Kvaratskhelia", "Gudmundsson", "Zaccagni", "Orsolini", "Pessina", "Pinamonti", "Retegui", "Pulisic"]

    df["Prossimo_Avversario"] = df["Squadra"].map(calendario)
    df["Fattore_Campo"] = df["Squadra"].apply(lambda x: 0.5 if x in squadre_in_casa else 0.0)
    df["Bonus_Specialista"] = df["Nome"].apply(lambda x: 1.0 if x in rigoristi else 0.0)

    stat = df.groupby('Squadra').agg({'Gf': 'sum', 'Gs': 'sum'})
    min_gf, max_gf = stat['Gf'].min(), stat['Gf'].max()
    min_gs, max_gs = stat['Gs'].min(), stat['Gs'].max()

    df["Debolezza_Difesa"] = df["Prossimo_Avversario"].map(1 + 9 * ((stat['Gs'] - min_gs) / (max_gs - min_gs)))
    df["Forza_Attacco"] = df["Prossimo_Avversario"].map(1 + 9 * ((stat['Gf'] - min_gf) / (max_gf - min_gf)))

    return df

try:
    df_serie_a = load_database()
except Exception as e:
    st.error(f"Errore caricamento database: {e}")
    st.stop()

def cerca_lega_e_dettagli(nome_lega, nome_squadra, df_database):
    slug_lega = re.sub(r'[^a-zA-Z0-9\s]', '', nome_lega).strip().lower().replace(' ', '-')
    url_rose = f"https://leghe.fantacalcio.it/{slug_lega}/rose"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url_rose, headers=headers, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            giocatori_trovati = [el.strip() for el in soup.find_all(text=True) if el.strip() in df_database["Nome"].values]
            rosa = df_database[df_database["Nome"].isin(list(set(giocatori_trovati)))].copy()
            if not rosa.empty: return {"esito": True, "url": url_rose, "rosa": rosa, "num_giocatori": len(rosa)}
    except: pass
    return {"esito": False}

# -----------------------------------------------------------------------------
# 3. SIDEBAR: GESTIONE COOKIE E CARICAMENTO ROSA
# -----------------------------------------------------------------------------
st.sidebar.header("📥 Gestione Rosa")

cookie_manager = stx.CookieManager(key="cookie_manager")

if "ignora_cookie" not in st.session_state: st.session_state["ignora_cookie"] = False
if "svuota_memoria" not in st.session_state: st.session_state["svuota_memoria"] = False
if "richiesta_salvataggio" not in st.session_state: st.session_state["richiesta_salvataggio"] = False

def rimuovi_rosa_callback():
    st.session_state["svuota_memoria"] = True
    st.session_state["ignora_cookie"] = True

def salva_rosa_callback():
    st.session_state["richiesta_salvataggio"] = True
    st.session_state["ignora_cookie"] = False

rosa_salvata_str = cookie_manager.get(cookie="algo_custom_rosa")

if st.session_state["svuota_memoria"]:
    cookie_manager.delete("algo_custom_rosa")
    st.session_state["svuota_memoria"] = False

if st.session_state["ignora_cookie"]:
    rosa_salvata_str = None

rosa_utente = pd.DataFrame()
usa_modificatore = True
bonus_porta_inviolata = False

# SCENARIO A: ROSA GIÀ SALVATA
if rosa_salvata_str:
    st.sidebar.success("✅ Rosa ricaricata dalla memoria del telefono!")
    nomi_salvati = rosa_salvata_str.split(",")
    rosa_utente = df_serie_a[df_serie_a["Nome"].isin(nomi_salvati)].copy()
    
    st.sidebar.markdown("---")
    usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
    
    st.sidebar.button("🗑️ Rimuovi Rosa", on_click=rimuovi_rosa_callback, use_container_width=True)

# SCENARIO B: NESSUNA ROSA SALVATA -> MOSTRA OPZIONI
else:
    metodo_rosa = st.sidebar.radio(
        "Scegli come importare la rosa:",
        ["📸 Scansiona Screenshot OCR", "🔍 Ricerca Nome Lega", "✏️ Incolla Nomi", "📁 File CSV/Excel"]
    )

    # --- METODO 1: OCR MULTISCREEN (CERVELLO POTENZIATO) ---
    if metodo_rosa == "📸 Scansiona Screenshot OCR":
        st.sidebar.markdown("---")
        usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
        st.sidebar.info("Scatta 2 o 3 screenshot per inquadrare tutta la rosa e caricali insieme.")
        
        uploaded_imgs = st.sidebar.file_uploader("Carica Screenshot", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        
        if uploaded_imgs:
            with st.spinner("🧠 Intelligenza Artificiale in lettura... Elaborazione avanzata."):
                testo_grezzo_totale = ""
                for uploaded_img in uploaded_imgs:
                    img = Image.open(uploaded_img)
                    testo_grezzo_totale += pytesseract.image_to_string(img) + "\n"
                
                righe = testo_grezzo_totale.split('\n')
                nomi_db = df_serie_a["Nome"].tolist()
                squadre_db = [str(s).lower() for s in df_serie_a["Squadra"].unique()]
                
                giocatori_trovati = []
                for riga in righe:
                    riga_lower = riga.lower()
                    
                    # 1. ELIMINA TUTTI I NUMERI (Voti, Crediti, Quotazioni)
                    riga_senza_numeri = ''.join([c for c in riga_lower if not c.isdigit()])
                    
                    # 2. BLACKLIST ESPRESSA (Rimuove Ruoli e intestazioni Fantacalcio)
                    riga_pulita = re.sub(r'\b(por|dif|cen|att|portieri|difensori|centrocampisti|attaccanti|voto|media|fantamedia|quotazione|svincola|giocatore|ruolo)\b', '', riga_senza_numeri, flags=re.IGNORECASE)
                    
                    riga_pulita = riga_pulita.strip()
                    
                    # 3. SALTA SE LA RIGA È TROPPO CORTA (Sotto i 3 caratteri non ci sono nomi veri)
                    if len(riga_pulita) < 3:
                        continue
                        
                    # 4. SALTA I NOMI DELLE SQUADRE 
                    if riga_pulita in squadre_db:
                        continue
                        
                    # 5. RICERCA RIGOROSA (token_set_ratio) -> Richiede che il nome corrisponda davvero!
                    risultato = process.extractOne(riga_pulita, nomi_db, scorer=fuzz.token_set_ratio)
                    if risultato:
                        match, score = risultato
                        if score >= 85:  # Punteggio di confidenza molto alto
                            giocatori_trovati.append(match)
                
                giocatori_unici = list(set(giocatori_trovati))
                rosa_utente = df_serie_a[df_serie_a["Nome"].isin(giocatori_unici)].copy()
                
                if len(rosa_utente) > 0:
                    st.sidebar.success(f"Scansione completata! Trovati {len(rosa_utente)} giocatori reali.")
                else:
                    st.sidebar.error("L'algoritmo non ha riconosciuto giocatori in modo sicuro. Prova con foto più a fuoco o senza pubblicità.")

    elif metodo_rosa == "🔍 Ricerca Nome Lega":
        st.sidebar.markdown("---")
        if "step_ricerca" not in st.session_state: st.session_state["step_ricerca"] = 1
        if st.session_state["step_ricerca"] == 1:
            with st.sidebar.form("form_ricerca"):
                input_lega = st.text_input("Nome Lega")
                input_squadra = st.text_input("Nome Squadra")
                if st.form_submit_button("Cerca") and input_lega and input_squadra:
                    with st.spinner("Ricerca..."):
                        ris = cerca_lega_e_dettagli(input_lega, input_squadra, df_serie_a)
                        if ris["esito"]:
                            st.session_state["dati_trovati"] = ris
                            st.session_state["step_ricerca"] = 2
                            st.rerun()
                        else: st.sidebar.error("Lega Privata o non trovata.")
        elif st.session_state["step_ricerca"] == 2:
            usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
            rosa_utente = st.session_state["dati_trovati"]["rosa"]
            if st.sidebar.button("Nuova Ricerca"):
                st.session_state["step_ricerca"] = 1
                st.rerun()

    elif metodo_rosa == "✏️ Incolla Nomi":
        st.sidebar.markdown("---")
        usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
        testo = st.text_area("Incolla i nomi separati da una virgola:")
        if testo: 
            rosa_utente = df_serie_a[df_serie_a["Nome"].isin([n.strip() for n in testo.split(',') if n.strip()])].copy()

    elif metodo_rosa == "📁 File CSV/Excel":
        st.sidebar.markdown("---")
        usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
        uploaded_file = st.file_uploader("Trascina file", type=["xlsx", "csv"])
        if uploaded_file:
            df_user = pd.read_csv(uploaded_file, sep=';', encoding='latin1') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            col_nome = [c for c in df_user.columns if 'nome' in str(c).lower() or 'giocatore' in str(c).lower()]
            if col_nome: 
                rosa_utente = df_serie_a[df_serie_a["Nome"].isin(df_user[col_nome[0]].dropna().unique())].copy()

    # TASTO SALVATAGGIO MANUALE
    if not rosa_utente.empty:
        st.sidebar.markdown("---")
        st.sidebar.button("💾 Salva Rosa per il futuro", on_click=salva_rosa_callback, use_container_width=True)
        
        if st.session_state["richiesta_salvataggio"]:
            nomi_da_salvare = ",".join(rosa_utente["Nome"].tolist())
            cookie_manager.set("algo_custom_rosa", nomi_da_salvare, expires_at=datetime.datetime.now() + datetime.timedelta(days=365))
            st.sidebar.success("✅ Rosa salvata! Dalla prossima volta si caricherà in automatico.")
            st.session_state["richiesta_salvataggio"] = False

# Fallback di emergenza
if rosa_utente.empty:
    st.info("💡 Nessuna rosa caricata. Visualizzazione della Rosa di Esempio (Demo).")
    rosa_default = ["Svilar", "Carnesecchi", "Martinez Jo.", "Buongiorno", "Bastoni", "Bremer", "Dimarco", "Di Lorenzo", "Pavard", "Gatti", "Calhanoglu", "Pulisic", "Zaccagni", "Barella", "Pellegrini Lo.", "Loftus-Cheek", "Ederson", "Lautaro", "Vlahovic", "Lookman", "Dybala", "Castellanos", "Pinamonti"]
    rosa_utente = df_serie_a[df_serie_a["Nome"].isin(rosa_default)].copy()

# -----------------------------------------------------------------------------
# 4. MOTORE DI CALCOLO E GENERAZIONE FORMAZIONE
# -----------------------------------------------------------------------------
def calcola_indici(df_rosa, mod_attivo, porta_inv):
    df = df_rosa.copy()
    cond_mov = df["R"] != "P"
    df.loc[cond_mov, "Indice_Algo"] = (df["Fm"] * 0.7) + (df["Debolezza_Difesa"] * 0.3) + df["Fattore_Campo"] + df["Bonus_Specialista"]
    
    cond_por = df["R"] == "P"
    df.loc[cond_por, "Indice_Algo"] = (df["Fm"] * 0.7) + ((10 - df["Forza_Attacco"]) * 0.3) + df["Fattore_Campo"]
    
    if mod_attivo:
        cond_def = df["R"] == "D"
        df.loc[cond_def, "Indice_Algo"] = (df["Mv"] * 0.6) + (df["Debolezza_Difesa"] * 0.2) + (df["Fm"] * 0.2) + df["Fattore_Campo"]
        df.loc[cond_def & (df["Mv"] >= 6.25), "Indice_Algo"] += 0.80
        
    df["Indice_Algo"] = df["Indice_Algo"].round(2)
    return df

df_rosa_calcolata = calcola_indici(rosa_utente, usa_modificatore, bonus_porta_inviolata)

moduli_classic = {
    "3-4-3": {"D":3,"C":4,"A":3}, "3-5-2": {"D":3,"C":5,"A":2}, 
    "4-3-3": {"D":4,"C":3,"A":3}, "4-4-2": {"D":4,"C":4,"A":2},
    "4-5-1": {"D":4,"C":5,"A":1}, "5-3-2": {"D":5,"C":3,"A":2}, 
    "5-4-1": {"D":5,"C":4,"A":1}
}

def genera_formazione(df_calcolato, schema_mod, mod_attivo):
    schema = moduli_classic[schema_mod]
    p_tit = df_calcolato[df_calcolato["R"] == "P"].sort_values(by="Indice_Algo", ascending=False).head(1)
    d_tit = df_calcolato[df_calcolato["R"] == "D"].sort_values(by="Indice_Algo", ascending=False).head(schema["D"])
    c_tit = df_calcolato[df_calcolato["R"] == "C"].sort_values(by="Indice_Algo", ascending=False).head(schema["C"])
    a_tit = df_calcolato[df_calcolato["R"] == "A"].sort_values(by="Indice_Algo", ascending=False).head(schema["A"])
    
    tit = pd.concat([p_tit, d_tit, c_tit, a_tit])
    pnt = tit["Indice_Algo"].sum()
    
    esclusi = df_calcolato[~df_calcolato["Id"].isin(tit["Id"])]
    pan = pd.concat([
        df_calcolato[(df_calcolato["R"] == "P") & (~df_calcolato["Id"].isin(p_tit["Id"]))],
        esclusi[esclusi["R"] == "D"].sort_values(by="Indice_Algo", ascending=False),
        esclusi[esclusi["R"] == "C"].sort_values(by="Indice_Algo", ascending=False),
        esclusi[esclusi["R"] == "A"].sort_values(by="Indice_Algo", ascending=False)
    ])
    
    switches = []
    for r in ["D", "C", "A"]:
        u_tit = tit[tit["R"] == r].sort_values(by="Indice_Algo", ascending=True)
        p_pan = pan[pan["R"] == r].sort_values(by="Indice_Algo", ascending=False)
        if not u_tit.empty and not p_pan.empty:
            if (u_tit.iloc[0]["Indice_Algo"] - p_pan.iloc[0]["Indice_Algo"]) <= 0.35:
                switches.append(f"🔄 **{r}**: {u_tit.iloc[0]['Nome']} ({u_tit.iloc[0]['Indice_Algo']}) vs {p_pan.iloc[0]['Nome']} ({p_pan.iloc[0]['Indice_Algo']})")
    return pnt.round(2), tit, pan, switches

miglior_mod = max(moduli_classic.keys(), key=lambda m: genera_formazione(df_rosa_calcolata, m, usa_modificatore)[0])

# -----------------------------------------------------------------------------
# 5. OUTPUT E VISUALIZZAZIONE
# -----------------------------------------------------------------------------
st.markdown("---")
col_mod, col_info = st.columns([2, 1])
with col_mod:
    modulo_selezionato = st.selectbox(
        "Seleziona Modulo Tattico", 
        list(moduli_classic.keys()), 
        index=list(moduli_classic.keys()).index(miglior_mod)
    )
    if modulo_selezionato == miglior_mod:
        st.caption(f"⭐ **Modulo consigliato da Algo-Custom**")

pnt_totale, df_titolari, df_panchina, lista_switches = genera_formazione(df_rosa_calcolata, modulo_selezionato, usa_modificatore)

col_tit, col_pan = st.columns(2)
with col_tit:
    st.subheader("🟢 11 Titolari")
    st.dataframe(df_titolari[["R", "Nome", "Squadra", "Prossimo_Avversario", "Indice_Algo"]], use_container_width=True, hide_index=True)

with col_pan:
    st.subheader("🟡 Panchina")
    st.dataframe(df_panchina[["R", "Nome", "Squadra", "Prossimo_Avversario", "Indice_Algo"]], use_container_width=True, hide_index=True)

if lista_switches:
    st.warning("⚠️ **Ballottaggi / Switch Caldi Rilevati (Differenza indice minima):**")
    for sw in lista_switches: 
        st.markdown(f"- {sw}")
