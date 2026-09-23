import streamlit as st
import pandas as pd
import numpy as np
import requests

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
# 3. SIDEBAR: REGOLAMENTO LEGA & LOGIN FANTACALCIO.IT
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Impostazioni Lega")
modalita = st.sidebar.selectbox("Modalità di Gioco", ["Classic", "Mantra (In arrivo)"])
usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa Attivo", value=True)
bonus_porta_inviolata = st.sidebar.checkbox("Bonus Porta Inviolata (+1)", value=False)

st.sidebar.markdown("---")
st.sidebar.header("🔑 Account Fantacalcio.it")

metodo_rosa = st.sidebar.radio(
    "Metodo di caricamento rosa:",
    ["Login Diretto API", "Carica File CSV/Excel", "Incolla Nomi Manualmente"]
)

rosa_utente = pd.DataFrame()

# -----------------------------------------------------------------------------
# 4. LOGICA DI AUTENTICAZIONE E DOWNLOAD AUTOMATICO ROSA
# -----------------------------------------------------------------------------
def autentica_fanta(username, password):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/json"
    }
    # Endpoint autenticazione API Fantacalcio.it
    url_login = "https://api.fantacalcio.it/v1/user/login"
    payload = {"username": username, "password": password}
    
    try:
        res = session.post(url_login, json=payload, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            return data.get("token"), session
        else:
            return None, None
    except Exception:
        return None, None

def ottieni_rosa_api(token, session):
    headers = {"Authorization": f"Bearer {token}"}
    # Query endpoint rose utente
    url_rose = "https://api.fantacalcio.it/v1/user/leagues"
    try:
        res = session.get(url_rose, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            # Estrazione ID dei giocatori della lega attiva
            giocatori_ids = []
            if "leagues" in data and len(data["leagues"]) > 0:
                for player in data["leagues"][0].get("roster", []):
                    giocatori_ids.append(player.get("id"))
            return giocatori_ids
    except Exception:
        pass
    return []

if metodo_rosa == "Login Diretto API":
    with st.sidebar.form("form_fanta_login"):
        fanta_user = st.text_input("Username o Email")
        fanta_pass = st.text_input("Password", type="password")
        btn_connetti = st.form_submit_button("Accedi e Scarica Rosa")

    if btn_connetti:
        if fanta_user and fanta_pass:
            with st.spinner("Connessione ai server di Fantacalcio.it in corso..."):
                token, sess = autentica_fanta(fanta_user, fanta_pass)
                if token:
                    ids_rosa = ottieni_rosa_api(token, sess)
                    if ids_rosa:
                        rosa_utente = df_serie_a[df_serie_a["Id"].isin(ids_rosa)].copy()
                        st.session_state["rosa_salvata"] = rosa_utente
                        st.sidebar.success(f"Trovati {len(rosa_utente)} giocatori nella tua rosa!")
                    else:
                        st.sidebar.warning("Login riuscito! Inserisci la tua rosa da File/Testo se la lega non è pubblica.")
                else:
                    st.sidebar.error("Credenziali non valide o blocco API temporaneo.")
        else:
            st.sidebar.warning("Compila entrambi i campi.")

    if "rosa_salvata" in st.session_state and rosa_utente.empty:
        rosa_utente = st.session_state["rosa_salvata"]

# -----------------------------------------------------------------------------
# 5. FALLBACK: FILE UPLOADER & TEXT AREA
# -----------------------------------------------------------------------------
if metodo_rosa == "Carica File CSV/Excel":
    st.subheader("📁 Carica File Rosa")
    uploaded_file = st.file_uploader("Trascina qui il file scaricato da Fantacalcio.it", type=["xlsx", "csv"])
    if uploaded_file is not None:
        try:
            df_user = pd.read_csv(uploaded_file, sep=';', encoding='latin1') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            col_nome = [c for c in df_user.columns if 'nome' in str(c).lower() or 'giocatore' in str(c).lower()]
            if col_nome:
                nomi = df_user[col_nome[0]].dropna().unique()
                rosa_utente = df_serie_a[df_serie_a["Nome"].isin(nomi)].copy()
                st.success(f"Rosa riconosciuta! {len(rosa_utente)} giocatori attivi.")
        except Exception as e:
            st.error(f"Errore lettura file: {e}")

elif metodo_rosa == "Incolla Nomi Manualmente":
    st.subheader("✏️ Inserimento Manuale")
    testo = st.text_area("Incolla i nomi dei tuoi giocatori separati da una virgola:")
    if testo:
        nomi = [n.strip() for n in testo.split(',') if n.strip()]
        rosa_utente = df_serie_a[df_serie_a["Nome"].isin(nomi)].copy()

# Rosa di default se nessuna rosa è selezionata
if rosa_utente.empty:
    st.info("💡 Nessuna rosa collegata. Visualizzazione della Rosa di Esempio.")
    rosa_default = [
        "Svilar", "Carnesecchi", "Martinez Jo.",
        "Buongiorno", "Bastoni", "Bremer", "Dimarco", "Di Lorenzo", "Pavard", "Gatti",
        "Calhanoglu", "Pulisic", "Zaccagni", "Barella", "Pellegrini Lo.", "Loftus-Cheek", "Ederson",
        "Lautaro", "Vlahovic", "Lookman", "Dybala", "Castellanos", "Pinamonti"
    ]
    rosa_utente = df_serie_a[df_serie_a["Nome"].isin(rosa_default)].copy()

# -----------------------------------------------------------------------------
# 6. MOTORE ALGORITMICO E GENERAZIONE FORMAZIONE
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

# Identificazione Modulo Migliore
miglior_mod = None
pnt_max = -1
for m in moduli_classic:
    p, _, _, _ = genera_formazione(df_rosa_calcolata, m, usa_modificatore)
    if p > pnt_max:
        pnt_max = p
        miglior_mod = m

# -----------------------------------------------------------------------------
# 7. VISUALIZZAZIONE TABELLE E SWITCH
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
