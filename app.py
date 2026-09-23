import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import re

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
    st.error(f"Errore nel caricamento del database 'statistiche.csv': {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. SCRAPING ED ESTRAZIONE SMART (NOME LEGA + SQUADRA)
# -----------------------------------------------------------------------------
def cerca_lega_e_dettagli(nome_lega, nome_squadra, df_database):
    slug_lega = re.sub(r'[^a-zA-Z0-9\s]', '', nome_lega).strip().lower().replace(' ', '-')
    url_rose = f"https://leghe.fantacalcio.it/{slug_lega}/rose"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        res = requests.get(url_rose, headers=headers, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            giocatori_trovati = []
            for el in soup.find_all(text=True):
                pulito = el.strip()
                if pulito in df_database["Nome"].values:
                    giocatori_trovati.append(pulito)
            
            giocatori_unici = list(set(giocatori_trovati))
            rosa = df_database[df_database["Nome"].isin(giocatori_unici)].copy()
            
            if not rosa.empty:
                return {
                    "esito": True,
                    "url": url_rose,
                    "rosa": rosa,
                    "num_giocatori": len(rosa)
                }
    except Exception:
        pass
        
    return {"esito": False}

# -----------------------------------------------------------------------------
# 4. SIDEBAR: SELEZIONE MODALITÀ DI IMPORTAZIONE (TRIPLA SOLUZIONE)
# -----------------------------------------------------------------------------
st.sidebar.header("📥 Caricamento Rosa Utente")

metodo_rosa = st.sidebar.radio(
    "Scegli la modalità:",
    ["🔍 Ricerca Nome Lega & Squadra (2 Step)", "✏️ Incolla Nomi Manualmente", "📁 Carica File CSV/Excel"]
)

rosa_utente = pd.DataFrame()
usa_modificatore = True
bonus_porta_inviolata = False
modalita_gioco = "Classic"

# --- OPZIONE 1: RICERCA LEGA & SQUADRA (2 STEP) ---
if metodo_rosa == "🔍 Ricerca Nome Lega & Squadra (2 Step)":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Step 1: Inserisci Dati")
    
    if "step_ricerca" not in st.session_state:
        st.session_state["step_ricerca"] = 1

    if st.session_state["step_ricerca"] == 1:
        with st.sidebar.form("form_ricerca_lega"):
            input_lega = st.text_input("Nome della tua Lega", placeholder="Es. FantaAmici")
            input_squadra = st.text_input("Nome della tua Squadra", placeholder="Es. FC Milano")
            btn_cerca = st.form_submit_button("Trova la mia Lega")
            
        if btn_cerca and input_lega and input_squadra:
            with st.spinner("Ricerca lega in corso..."):
                risultato = cerca_lega_e_dettagli(input_lega, input_squadra, df_serie_a)
                if risultato["esito"]:
                    st.session_state["dati_trovati"] = risultato
                    st.session_state["step_ricerca"] = 2
                    st.rerun()
                else:
                    st.sidebar.error("Lega non trovata o impostata su Privata. Prova l'incollaggio manuale o il file CSV!")

    elif st.session_state["step_ricerca"] == 2:
        dati = st.session_state["dati_trovati"]
        st.sidebar.success("✅ Lega e Rosa individuate!")
        st.sidebar.info(f"Giocatori estratti: **{dati['num_giocatori']}**")
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("Step 2: Regolamento Lega")
        modalita_gioco = st.sidebar.selectbox("Modalità di Gioco", ["Classic", "Mantra (In arrivo)"])
        num_partecipanti = st.sidebar.number_input("Numero Partecipanti Lega", min_value=4, max_value=20, value=10)
        crediti_asta = st.sidebar.number_input("Crediti Iniziali Asta", min_value=100, max_value=1000, value=500, step=50)
        usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa Attivo", value=True)
        bonus_porta_inviolata = st.sidebar.checkbox("Bonus Porta Inviolata (+1)", value=False)
        
        rosa_utente = dati["rosa"]
        
        if st.sidebar.button("🔄 Cambia Lega / Nuova Ricerca"):
            st.session_state["step_ricerca"] = 1
            st.rerun()

# --- OPZIONE 2: INCOLLA NOMI MANUALMENTE ---
elif metodo_rosa == "✏️ Incolla Nomi Manualmente":
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Impostazioni Lega")
    modalita_gioco = st.sidebar.selectbox("Modalità di Gioco", ["Classic", "Mantra (In arrivo)"])
    usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa Attivo", value=True)
    bonus_porta_inviolata = st.sidebar.checkbox("Bonus Porta Inviolata (+1)", value=False)
    
    st.subheader("✏️ Inserimento Manuale Rosa")
    testo = st.text_area("Incolla i nomi dei tuoi giocatori separati da una virgola:", placeholder="Es: Svilar, Carnesecchi, Bastoni, Bremer, Dimarco, Calhanoglu, Lautaro...")
    if testo:
        nomi = [n.strip() for n in testo.split(',') if n.strip()]
        rosa_utente = df_serie_a[df_serie_a["Nome"].isin(nomi)].copy()
        st.success(f"Rosa riconosciuta! Trovati {len(rosa_utente)} giocatori su {len(nomi)} inseriti.")

# --- OPZIONE 3: CARICA FILE CSV / EXCEL ---
elif metodo_rosa == "📁 Carica File CSV/Excel":
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Impostazioni Lega")
    modalita_gioco = st.sidebar.selectbox("Modalità di Gioco", ["Classic", "Mantra (In arrivo)"])
    usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa Attivo", value=True)
    bonus_porta_inviolata = st.sidebar.checkbox("Bonus Porta Inviolata (+1)", value=False)
    
    st.subheader("📁 Carica File Rosa")
    uploaded_file = st.file_uploader("Trascina qui il file scaricato da Fantacalcio.it", type=["xlsx", "csv"])
    if uploaded_file is not None:
        try:
            df_user = pd.read_csv(uploaded_file, sep=';', encoding='latin1') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            col_nome = [c for c in df_user.columns if 'nome' in str(c).lower() or 'giocatore' in str(c).lower()]
            if col_nome:
                nomi = df_user[col_nome[0]].dropna().unique()
                rosa_utente = df_serie_a[df_serie_a["Nome"].isin(nomi)].copy()
                st.success(f"Rosa caricata con successo! Trovati {len(rosa_utente)} giocatori.")
        except Exception as e:
            st.error(f"Errore nella lettura del file: {e}")

# Fallback di test se nessuna rosa è ancora caricata
if rosa_utente.empty:
    st.info("💡 Nessuna rosa selezionata. Visualizzazione della Rosa di Esempio.")
    rosa_default = [
        "Svilar", "Carnesecchi", "Martinez Jo.",
        "Buongiorno", "Bastoni", "Bremer", "Dimarco", "Di Lorenzo", "Pavard", "Gatti",
        "Calhanoglu", "Pulisic", "Zaccagni", "Barella", "Pellegrini Lo.", "Loftus-Cheek", "Ederson",
        "Lautaro", "Vlahovic", "Lookman", "Dybala", "Castellanos", "Pinamonti"
    ]
    rosa_utente = df_serie_a[df_serie_a["Nome"].isin(rosa_default)].copy()

# -----------------------------------------------------------------------------
# 5. MOTORE DI CALCOLO E GENERAZIONE FORMAZIONE
# -----------------------------------------------------------------------------
def calcola_indici(df_rosa, mod_attivo, porta_inv):
    df = df_rosa.copy()
    cond_mov = df["R"] != "P"
    df.loc[cond_mov, "Indice_Algo"] = (df["Fm"] * 0.7) + (df["Debolezza_Difesa"] * 0.3) + df["Fattore_Campo"] + df["Bonus_Specialista"]
    
    cond_por = df["R"] == "P"
    bonus_p = 0.5 if porta_inv else 0.0
    df.loc[cond_por, "Indice_Algo"] = (df["Fm"] * 0.7) + ((10 - df["Forza_Attacco"]) * 0.3) + df["Fattore_Campo"] + bonus_p

    if mod_attivo:
        cond_def = df["R"] == "D"
        df.loc[cond_def, "Indice_Algo"] = (df["Mv"] * 0.6) + (df["Debolezza_Difesa"] * 0.2) + (df["Fm"] * 0.2) + df["Fattore_Campo"]
        df.loc[cond_def & (df["Mv"] >= 6.25), "Indice_Algo"] += 0.80

    df["Indice_Algo"] = df["Indice_Algo"].round(2)
    return df

df_rosa_calcolata = calcola_indici(rosa_utente, usa_modificatore, bonus_porta_inviolata)

moduli_classic = {
    "3-4-3": {"D": 3, "C": 4, "A": 3},
    "3-5-2": {"D": 3, "C": 5, "A": 2},
    "4-3-3": {"D": 4, "C": 3, "A": 3},
    "4-4-2": {"D": 4, "C": 4, "A": 2},
    "4-5-1": {"D": 4, "C": 5, "A": 1},
    "5-3-2": {"D": 5, "C": 3, "A": 2},
    "5-4-1": {"D": 5, "C": 4, "A": 1}
}

def genera_formazione(df_calcolato, schema_mod, mod_attivo):
    schema = moduli_classic[schema_mod]
    p_tit = df_calcolato[df_calcolato["R"] == "P"].sort_values(by="Indice_Algo", ascending=False).head(1)
    d_tit = df_calcolato[df_calcolato["R"] == "D"].sort_values(by="Indice_Algo", ascending=False).head(schema["D"])
    c_tit = df_calcolato[df_calcolato["R"] == "C"].sort_values(by="Indice_Algo", ascending=False).head(schema["C"])
    a_tit = df_calcolato[df_calcolato["R"] == "A"].sort_values(by="Indice_Algo", ascending=False).head(schema["A"])
    
    tit = pd.concat([p_tit, d_tit, c_tit, a_tit])
    pnt = tit["Indice_Algo"].sum()
    
    if mod_attivo and schema["D"] >= 4:
        top_3_d = d_tit.sort_values(by="Mv", ascending=False).head(3)
        if not top_3_d.empty and not p_tit.empty:
            media_mod = (top_3_d["Mv"].sum() + p_tit["Mv"].values[0]) / 4
            if media_mod >= 6.5:
                pnt += 3.0
            elif media_mod >= 6.25:
                pnt += 1.5

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
            diff = u_tit.iloc[0]["Indice_Algo"] - p_pan.iloc[0]["Indice_Algo"]
            if diff <= 0.35:
                switches.append(f"🔄 **{r}**: {u_tit.iloc[0]['Nome']} ({u_tit.iloc[0]['Indice_Algo']}) vs {p_pan.iloc[0]['Nome']} ({p_pan.iloc[0]['Indice_Algo']})")

    return pnt.round(2), tit, pan, switches

miglior_mod = None
pnt_max = -1
for m in moduli_classic:
    p, _, _, _ = genera_formazione(df_rosa_calcolata, m, usa_modificatore)
    if p > pnt_max:
        pnt_max = p
        miglior_mod = m

# -----------------------------------------------------------------------------
# 6. OUTPUT E VISUALIZZAZIONE
# -----------------------------------------------------------------------------
st.markdown("---")
col_mod, col_info = st.columns([2, 1])

with col_mod:
    modulo_selezionato = st.selectbox(
        "Modulo Tattico",
        options=list(moduli_classic.keys()),
        index=list(moduli_classic.keys()).index(miglior_mod)
    )
    if modulo_selezionato == miglior_mod:
        st.caption(f"⭐ **Modulo consigliato da Algo-Custom** (Punteggio proiettato: {pnt_max})")

pnt_totale, df_titolari, df_panchina, lista_switches = genera_formazione(df_rosa_calcolata, modulo_selezionato, usa_modificatore)

col_tit, col_pan = st.columns(2)

with col_tit:
    st.subheader("🟢 11 Titolari")
    st.dataframe(
        df_titolari[["R", "Nome", "Squadra", "Prossimo_Avversario", "Indice_Algo"]],
        use_container_width=True,
        hide_index=True
    )

with col_pan:
    st.subheader("🟡 Panchina Ordinata")
    st.dataframe(
        df_panchina[["R", "Nome", "Squadra", "Prossimo_Avversario", "Indice_Algo"]],
        use_container_width=True,
        hide_index=True
    )

if lista_switches:
    st.warning("⚠️ **Ballottaggi / Switch Caldi Rilevati:**")
    for sw in lista_switches:
        st.markdown(f"- {sw}")
