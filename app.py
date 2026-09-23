# -----------------------------------------------------------------------------
# 3. SIDEBAR: GESTIONE COOKIE E CARICAMENTO ROSA
# -----------------------------------------------------------------------------
st.sidebar.header("📥 Gestione Rosa")

# Inizializza il manager specificando una chiave univoca
cookie_manager = stx.CookieManager(key="cookie_manager")

# FUNZIONI CALLBACK: Vengono eseguite PRIMA che la pagina si ricarichi
def rimuovi_rosa_callback():
    st.session_state["svuota_memoria"] = True

def salva_rosa_callback():
    st.session_state["richiesta_salvataggio"] = True

if "svuota_memoria" not in st.session_state:
    st.session_state["svuota_memoria"] = False
    
if "richiesta_salvataggio" not in st.session_state:
    st.session_state["richiesta_salvataggio"] = False

# Legge il cookie attuale
rosa_salvata_str = cookie_manager.get(cookie="algo_custom_rosa")

# Esegue l'eliminazione se richiesta
if st.session_state["svuota_memoria"]:
    cookie_manager.delete("algo_custom_rosa")
    rosa_salvata_str = None
    st.session_state["svuota_memoria"] = False  # Reset

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
    
    st.sidebar.button("🗑️ Rimuovi Rosa (Inserisci Nuova)", on_click=rimuovi_rosa_callback, use_container_width=True)

# SCENARIO B: NESSUNA ROSA SALVATA -> MOSTRA OPZIONI DI INSERIMENTO
else:
    metodo_rosa = st.sidebar.radio(
        "Scegli come importare la rosa:",
        ["📸 Scansiona Screenshot OCR", "🔍 Ricerca Nome Lega", "✏️ Incolla Nomi", "📁 File CSV/Excel"]
    )

    # --- METODO 1: OCR MULTISCREEN ---
    if metodo_rosa == "📸 Scansiona Screenshot OCR":
        st.sidebar.markdown("---")
        usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
        st.sidebar.info("Scatta 2 o 3 screenshot per inquadrare tutta la rosa e caricali insieme.")
        
        uploaded_imgs = st.sidebar.file_uploader("Carica Screenshot", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        
        if uploaded_imgs:
            with st.spinner("🧠 Intelligenza Artificiale in lettura..."):
                testo_grezzo_totale = ""
                for uploaded_img in uploaded_imgs:
                    img = Image.open(uploaded_img)
                    testo_grezzo_totale += pytesseract.image_to_string(img) + "\n"
                
                righe = [r.strip() for r in testo_grezzo_totale.split('\n') if len(r.strip()) > 2]
                nomi_db = df_serie_a["Nome"].tolist()
                
                giocatori_trovati = []
                for riga in righe:
                    risultato = process.extractOne(riga, nomi_db)
                    if risultato:
                        match, score = risultato
                        if score >= 80:
                            giocatori_trovati.append(match)
                
                giocatori_unici = list(set(giocatori_trovati))
                rosa_utente = df_serie_a[df_serie_a["Nome"].isin(giocatori_unici)].copy()
                st.sidebar.success(f"Scansione completata! Trovati {len(rosa_utente)} giocatori.")

    # --- METODO 2: RICERCA LEGA ---
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

    # --- METODO 3: INCOLLA NOMI MANUALMENTE ---
    elif metodo_rosa == "✏️ Incolla Nomi":
        st.sidebar.markdown("---")
        usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
        testo = st.text_area("Incolla i nomi separati da una virgola:")
        if testo: 
            rosa_utente = df_serie_a[df_serie_a["Nome"].isin([n.strip() for n in testo.split(',') if n.strip()])].copy()

    # --- METODO 4: UPLOAD CSV ---
    elif metodo_rosa == "📁 File CSV/Excel":
        st.sidebar.markdown("---")
        usa_modificatore = st.sidebar.checkbox("Modificatore di Difesa", value=True)
        uploaded_file = st.file_uploader("Trascina file", type=["xlsx", "csv"])
        if uploaded_file:
            df_user = pd.read_csv(uploaded_file, sep=';', encoding='latin1') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            col_nome = [c for c in df_user.columns if 'nome' in str(c).lower() or 'giocatore' in str(c).lower()]
            if col_nome: 
                rosa_utente = df_serie_a[df_serie_a["Nome"].isin(df_user[col_nome[0]].dropna().unique())].copy()

    # SALVATAGGIO MANUALE (Pulsante opzionale)
    if not rosa_utente.empty:
        st.sidebar.markdown("---")
        st.sidebar.button("💾 Salva Rosa per il futuro", on_click=salva_rosa_callback, use_container_width=True)
        
        # Esegue il salvataggio se l'utente ha premuto il tasto
        if st.session_state["richiesta_salvataggio"]:
            nomi_da_salvare = ",".join(rosa_utente["Nome"].tolist())
            cookie_manager.set("algo_custom_rosa", nomi_da_salvare, expires_at=datetime.datetime.now() + datetime.timedelta(days=365))
            st.sidebar.success("✅ Rosa salvata! Dalla prossima volta si caricherà in automatico.")
            st.session_state["richiesta_salvataggio"] = False # Reset
