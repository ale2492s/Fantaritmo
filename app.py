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
from thefuzz import process, fuzz

# -----------------------------------------------------------------------------
# 1. CONFIGURAZIONE PAGINA STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Algo-Custom | Fantacalcio Premium",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚽ Algo-Custom: Formazione Premium")
st.caption("Intelligenza Artificiale, Controllo Totale e Analisi Matchup")

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

    # Scala da 1 a 10 per la forza delle squadre
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
st.sidebar.header("📥 La Tua Rosa")
cookie_manager = stx.CookieManager(key="cookie_manager")

if "ignora_cookie" not in st.session_state: st.session_state["ignora_cookie"] = False
if "svuota_memoria" not in st.session_state: st.session_state["svuota_memoria"] = False
if "richiesta_salvataggio" not in st.session_state: st.session_state["richiesta_salvataggio"] = False
if "widget_key" not in st.session_state: st.session_state["widget_key"] = 1

def rimuovi_rosa_callback():
    st.session_state["svuota_memoria"] = True
    st.session_state["ignora_cookie"] = True
    st.session_state["widget_key"] += 1

def salva_rosa_callback():
    st.session_state["richiesta_salvataggio"] = True
    st.session_state["ignora_cookie"] = False
    st.session_state["widget_key"] += 1

rosa_salvata_str = cookie_manager.get(cookie="algo_custom_rosa")

if st.session_state["svuota_memoria"]:
    cookie_manager.delete("algo_custom_rosa")
    st.session_state["svuota_memoria"] = False

if st.session_state["ignora_cookie"]:
    rosa_salvata_str = None

rosa_utente = pd.DataFrame()

# SCENARIO A: ROSA GIÀ SALVATA
if rosa_salvata_str:
    nomi_salvati = rosa_salvata_str.split(",")
    rosa_utente = df_serie_a[df_serie_a["Nome"].isin(nomi_salvati)].copy()
    st.sidebar.success(f"✅ Trovati {len(rosa_utente)} giocatori in memoria!")
    st.sidebar.button("🔄 Cambia/Rimuovi Rosa", on_click=rimuovi_rosa_callback, use_container_width=True)

# SCENARIO B: NESSUNA ROSA SALVATA -> MOSTRA OPZIONI
else:
    metodo_rosa = st.sidebar.radio(
        "Importa la tua squadra:",
        ["📸 OCR (Screenshot)", "🔍 Ricerca Lega", "✏️ Testo", "📁 CSV/Excel"]
    )

    if metodo_rosa == "📸 OCR (Screenshot)":
        uploaded_imgs = st.sidebar.file_uploader("Carica 2-3 Screenshot", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"ocr_{st.session_state['widget_key']}")
        if uploaded_imgs:
            with st.spinner("🧠 Scansione in corso..."):
                testo_grezzo_totale = "".join([pytesseract.image_to_string(Image.open(i)) + "\n" for i in uploaded_imgs])
                righe = testo_grezzo_totale.split('\n')
                nomi_db = df_serie_a["Nome"].tolist()
                squadre_db = [str(s).lower() for s in df_serie_a["Squadra"].unique()]
                
                giocatori_trovati = []
                for riga in righe:
                    r_pulita = re.sub(r'\b(por|dif|cen|att|portieri|difensori|centrocampisti|attaccanti|voto|media|fantamedia|quotazione|svincola|giocatore|ruolo)\b', '', ''.join([c for c in riga.lower() if not c.isdigit()]), flags=re.IGNORECASE).strip()
                    if len(r_pulita) < 3 or r_pulita in squadre_db: continue
                    risultato = process.extractOne(r_pulita, nomi_db, scorer=fuzz.token_set_ratio)
                    if risultato and risultato[1] >= 85: giocatori_trovati.append(risultato[0])
                
                rosa_utente = df_serie_a[df_serie_a["Nome"].isin(list(set(giocatori_trovati)))].copy()
                if len(rosa_utente) > 0: st.sidebar.success(f"Trovati {len(rosa_utente)} giocatori!")

    elif metodo_rosa == "🔍 Ricerca Lega":
        with st.sidebar.form("form_ricerca"):
            input_lega = st.text_input("Nome Lega")
            input_squadra = st.text_input("Nome Squadra")
            if st.form_submit_button("Cerca") and input_lega and input_squadra:
                with st.spinner("Ricerca..."):
                    ris = cerca_lega_e_dettagli(input_lega, input_squadra, df_serie_a)
                    if ris["esito"]: rosa_utente = ris["rosa"]
                    else: st.sidebar.error("Lega Privata o non trovata.")

    elif metodo_rosa == "✏️ Testo":
        testo = st.text_area("Incolla i nomi (separati da virgola):", key=f"testo_{st.session_state['widget_key']}")
        if testo: rosa_utente = df_serie_a[df_serie_a["Nome"].isin([n.strip() for n in testo.split(',') if n.strip()])].copy()

    elif metodo_rosa == "📁 CSV/Excel":
        uploaded_file = st.sidebar.file_uploader("Trascina file", type=["xlsx", "csv"], key=f"csv_{st.session_state['widget_key']}")
        if uploaded_file:
            df_user = pd.read_csv(uploaded_file, sep=';', encoding='latin1') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            col_nome = [c for c in df_user.columns if 'nome' in str(c).lower() or 'giocatore' in str(c).lower()]
            if col_nome: rosa_utente = df_serie_a[df_serie_a["Nome"].isin(df_user[col_nome[0]].dropna().unique())].copy()

    if not rosa_utente.empty:
        st.sidebar.button("💾 Salva Rosa in memoria", on_click=salva_rosa_callback, use_container_width=True)
        if st.session_state["richiesta_salvataggio"]:
            cookie_manager.set("algo_custom_rosa", ",".join(rosa_utente["Nome"].tolist()), expires_at=datetime.datetime.now() + datetime.timedelta(days=365))
            st.session_state["richiesta_salvataggio"] = False
            st.rerun()

# Fallback di emergenza
if rosa_utente.empty:
    st.info("💡 Nessuna rosa caricata. Visualizzazione della Rosa Demo.")
    rosa_utente = df_serie_a[df_serie_a["Nome"].isin(["Svilar", "Carnesecchi", "Martinez Jo.", "Buongiorno", "Bastoni", "Bremer", "Dimarco", "Di Lorenzo", "Pavard", "Gatti", "Calhanoglu", "Pulisic", "Zaccagni", "Barella", "Pellegrini Lo.", "Loftus-Cheek", "Ederson", "Lautaro", "Vlahovic", "Lookman", "Dybala", "Castellanos", "Pinamonti"])].copy()

# -----------------------------------------------------------------------------
# 4. PANNELLO ALLENATORE (SLIDER & INFORTUNATI)
# -----------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("🎛️ Pannello Allenatore")

# A) Gestione Infortunati
indisponibili = st.sidebar.multiselect(
    "🚑 Giocatori Indisponibili (Esclusi)",
    options=rosa_utente["Nome"].sort_values().tolist(),
    help="Seleziona chi è infortunato o squalificato. Verrà ignorato dall'algoritmo."
)

# B) Slider Personalizzazione Algoritmo
st.sidebar.markdown("**Bilanciamento Algoritmo**")
peso_forma = st.sidebar.slider("Peso Storico (Fantamedia)", min_value=0.0, max_value=1.0, value=0.6, step=0.1, help="Più è alto, più l'algoritmo andrà sul sicuro scegliendo i top player. Più è basso, più rischierà in base alla partita facile.")
peso_match = 1.0 - peso_forma

usa_modificatore = st.sidebar.checkbox("Usa Modificatore Difesa", value=True)

# -----------------------------------------------------------------------------
# 5. MOTORE DI CALCOLO
# -----------------------------------------------------------------------------
def calcola_indici(df_rosa, mod_attivo, p_forma, p_match, indisponibili_list):
    df = df_rosa.copy()
    
    # Calcolo Semáforo Difficoltà Matchup (1-10)
    # Per i giocatori di movimento (Difesa avversaria alta = 🟢)
    cond_mov = df["R"] != "P"
    df.loc[cond_mov, "Difficolta_Match"] = df["Debolezza_Difesa"].apply(lambda x: "🟢" if x >= 6.5 else ("🔴" if x <= 3.5 else "🟡"))
    
    # Per i portieri (Attacco avversario basso = 🟢)
    cond_por = df["R"] == "P"
    df.loc[cond_por, "Difficolta_Match"] = df["Forza_Attacco"].apply(lambda x: "🟢" if x <= 3.5 else ("🔴" if x >= 6.5 else "🟡"))

    # Calcolo Indice Ponderato
    df.loc[cond_mov, "Indice_Algo"] = (df["Fm"] * p_forma) + (df["Debolezza_Difesa"] * (p_match / 3)) + df["Fattore_Campo"] + df["Bonus_Specialista"]
    df.loc[cond_por, "Indice_Algo"] = (df["Fm"] * p_forma) + ((10 - df["Forza_Attacco"]) * (p_match / 3)) + df["Fattore_Campo"]
    
    if mod_attivo:
        cond_def = df["R"] == "D"
        df.loc[cond_def, "Indice_Algo"] = (df["Mv"] * (p_forma-0.1)) + (df["Debolezza_Difesa"] * (p_match/3)) + (df["Fm"] * 0.2) + df["Fattore_Campo"]
        df.loc[cond_def & (df["Mv"] >= 6.25), "Indice_Algo"] += 0.80
        
    df["Indice_Algo"] = df["Indice_Algo"].round(2)
    
    # Applica filtro indisponibili (azzera il punteggio)
    df.loc[df["Nome"].isin(indisponibili_list), "Indice_Algo"] = -100

    return df

df_calcolata = calcola_indici(rosa_utente, usa_modificatore, peso_forma, peso_match, indisponibili)

moduli_classic = {"3-4-3": {"D":3,"C":4,"A":3}, "3-5-2": {"D":3,"C":5,"A":2}, "4-3-3": {"D":4,"C":3,"A":3}, "4-4-2": {"D":4,"C":4,"A":2}}

def genera_formazione(df_calc, schema_mod):
    schema = moduli_classic[schema_mod]
    p_tit = df_calc[df_calc["R"] == "P"].sort_values(by="Indice_Algo", ascending=False).head(1)
    d_tit = df_calc[df_calc["R"] == "D"].sort_values(by="Indice_Algo", ascending=False).head(schema["D"])
    c_tit = df_calc[df_calc["R"] == "C"].sort_values(by="Indice_Algo", ascending=False).head(schema["C"])
    a_tit = df_calc[df_calc["R"] == "A"].sort_values(by="Indice_Algo", ascending=False).head(schema["A"])
    
    tit = pd.concat([p_tit, d_tit, c_tit, a_tit])
    pnt = tit["Indice_Algo"].sum()
    
    esclusi = df_calc[~df_calc["Id"].isin(tit["Id"])]
    # Togliamo gli indisponibili veri dalla panchina visibile
    pan = esclusi[esclusi["Indice_Algo"] > -50].copy() 
    pan = pd.concat([
        pan[pan["R"] == "P"].sort_values(by="Indice_Algo", ascending=False),
        pan[pan["R"] == "D"].sort_values(by="Indice_Algo", ascending=False),
        pan[pan["R"] == "C"].sort_values(by="Indice_Algo", ascending=False),
        pan[pan["R"] == "A"].sort_values(by="Indice_Algo", ascending=False)
    ])
    
    switches = []
    for r in ["D", "C", "A"]:
        u_tit = tit[tit["R"] == r].sort_values(by="Indice_Algo", ascending=True)
        p_pan = pan[pan["R"] == r].sort_values(by="Indice_Algo", ascending=False)
        if not u_tit.empty and not p_pan.empty:
            if (u_tit.iloc[0]["Indice_Algo"] - p_pan.iloc[0]["Indice_Algo"]) <= 0.35:
                switches.append(f"🔄 **{r}**: {u_tit.iloc[0]['Nome']} ({u_tit.iloc[0]['Difficolta_Match']}) vs {p_pan.iloc[0]['Nome']} ({p_pan.iloc[0]['Difficolta_Match']})")
    return pnt.round(2), tit, pan, switches

miglior_mod = max(moduli_classic.keys(), key=lambda m: genera_formazione(df_calcolata, m)[0])

# -----------------------------------------------------------------------------
# 6. OUTPUT PREMIUM (IL CAMPO VIRTUALE)
# -----------------------------------------------------------------------------
st.markdown("---")
modulo_selezionato = st.selectbox("Seleziona Modulo Tattico", list(moduli_classic.keys()), index=list(moduli_classic.keys()).index(miglior_mod))
_, df_titolari, df_panchina, lista_switches = genera_formazione(df_calcolata, modulo_selezionato)

# Funzione per disegnare la singola Card del giocatore
def draw_card(row):
    color = "#1e1e1e" # Sfondo scuro premium
    border = "2px solid #333"
    html = f"""
    <div style="background-color: {color}; border: {border}; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);">
        <h4 style="margin:0; padding:0; font-size:16px; color:white;">{row['Nome']}</h4>
        <p style="margin:5px 0 0 0; font-size:12px; color:#bbb;">{row['Squadra']} vs {row['Prossimo_Avversario']} {row['Difficolta_Match']}</p>
        <div style="margin-top:5px; font-weight:bold; color:#4da6ff;">⭐ {row['Indice_Algo']}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

st.subheader("🟢 Formazione Titolare (Il Campo)")
st.caption("Legenda Match: 🟢 Facile | 🟡 Medio | 🔴 Difficile")

# Disegna il campo dall'Attacco alla Difesa
ruoli_ordine = [("A", "Attacco"), ("C", "Centrocampo"), ("D", "Difesa"), ("P", "Porta")]

for sigla, nome_ruolo in ruoli_ordine:
    giocatori_ruolo = df_titolari[df_titolari["R"] == sigla]
    if not giocatori_ruolo.empty:
        st.markdown(f"<h5 style='text-align: center; color: #888;'>{nome_ruolo}</h5>", unsafe_allow_html=True)
        cols = st.columns(len(giocatori_ruolo))
        for i, (_, player) in enumerate(giocatori_ruolo.iterrows()):
            with cols[i]:
                draw_card(player)

st.markdown("---")
col_panchina, col_alert = st.columns([1.5, 1])

with col_panchina:
    st.subheader("🟡 Panchina")
    st.dataframe(df_panchina[["R", "Nome", "Squadra", "Prossimo_Avversario", "Difficolta_Match", "Indice_Algo"]], hide_index=True, use_container_width=True)

with col_alert:
    if indisponibili:
        st.error(f"🚑 **Indisponibili Esclusi:**\n\n" + ", ".join(indisponibili))
    if lista_switches:
        st.warning("⚠️ **Ballottaggi Caldi:**")
        for sw in lista_switches: st.markdown(f"- {sw}")
