"""Spiegazioni che compaiono passando il mouse sulle opzioni (tooltip)."""
from __future__ import annotations

WIDTH = 360  # larghezza del popup in pixel


def tip(title: str, body: str) -> str:
    """Testo formattato per il popup: titolo in grassetto, righe a capo con <br>."""
    return (f'<table width="{WIDTH}"><tr><td><b>{title}</b><br>{body}</td></tr></table>')


OPTIONS = {
    "method": tip("Combinazione", "Come vengono fusi i pixel dei frame allineati.<br>"
                  "• <b>Kappa-sigma</b>: media che esclude i valori anomali (satelliti, aerei, raggi cosmici, hot pixel). "
                  "Il migliore con 5 o più frame.<br>"
                  "• <b>Sigma winsorizzato</b>: come kappa-sigma, ma i valori anomali vengono limitati invece che esclusi: "
                  "leggermente meno rumore, un po' meno efficace sulle scie.<br>"
                  "• <b>Mediana</b>: molto robusta ma più rumorosa (circa 25 % in più della media).<br>"
                  "• <b>Media semplice</b>: minimo rumore ma nessun rigetto: le scie dei satelliti restano."),
    "auto_reject": tip("Scarto automatico", "Esclude i frame peggiori (mossi, sfocati, con nuvole o poche stelle) "
                       "confrontandoli con la mediana della sessione.<br>"
                       "<b>Attivo</b>: risultato più nitido, ma meno frame quindi un po' più rumore.<br>"
                       "<b>Disattivo</b>: usa tutti i frame allineabili; quelli mossi allargano le stelle."),
    "severity": tip("Severità dello scarto", "Quanto deve essere peggiore un frame per essere scartato.<br>"
                    "<b>Verso sinistra</b>: si scarta solo ciò che è chiaramente rovinato.<br>"
                    "<b>Verso destra</b>: si tengono solo i frame migliori (mai meno del 40 %).<br>"
                    "A zero non si scarta nulla."),
    "weights": tip("Pesi per qualità", "I frame con stelle più fini e meno rumore contano di più nella media "
                   "(peso da 0,2 a 1).<br><b>Attivo</b>: leggero guadagno di nitidezza.<br>"
                   "<b>Disattivo</b>: tutti i frame pesano uguale."),
    "gradient": tip("Rimozione del gradiente", "Misura il fondo cielo su una griglia, esclude stelle, nebulose e "
                    "primo piano, adatta un modello matematico e lo sottrae: il fondo diventa uniforme.<br>"
                    "<b>Attivo</b>: cielo omogeneo, colori più puliti.<br>"
                    "<b>Disattivo</b>: restano gradiente e alone dell'inquinamento luminoso "
                    "(utile se tutto il campo è pieno di nebulosità).<br>"
                    "Si può cambiare dopo lo stack senza ricalcolare."),
    "degree": tip("Grado del modello", "Complessità del modello del gradiente.<br>"
                  "<b>1</b>: piano inclinato (un lato del cielo più chiaro).<br>"
                  "<b>2</b>: consigliato, gestisce curvature e vignettatura leggera.<br>"
                  "<b>3–4</b>: gradienti complessi; con alberi o orizzonte nel campo creano aloni "
                  "e possono 'mangiare' la Via Lattea."),
    "neutralize": tip("Neutralizza il fondo", "Porta il fondo cielo allo stesso livello nei tre canali: elimina la "
                      "dominante (arancione dei lampioni, verde del sensore).<br>"
                      "<b>Disattivo</b>: il fondo mantiene il colore originale."),
    "star_color": tip("Calibra i colori sulle stelle", "Riferimento bianco = colore medio delle stelle non sature: "
                      "R e B vengono riscalati in modo che la stella 'media' sia bianca (riferimento stellare medio). "
                      "Il fondo resta neutro.<br><b>Disattivo</b>: i colori dipendono solo dal bilanciamento del RAW."),
    "white_balance": tip("Bilanciamento del bianco", "Coefficienti letti dal file RAW, applicati prima del debayer.<br>"
                         "• <b>Luce diurna</b>: coefficienti standard della fotocamera, uguali per tutti gli scatti (consigliato).<br>"
                         "• <b>Come scattato</b>: il bilanciamento impostato in camera (con AWB può cambiare da scatto a scatto).<br>"
                         "• <b>Nessuno</b>: dati grezzi, immagine verde: solo se elabori i colori altrove."),
    "kappa_low": tip("Kappa basso", "Soglia di rigetto verso il basso, in deviazioni standard (σ): un pixel più scuro "
                     "della mediana di oltre questo valore viene escluso.<br>"
                     "<b>Più basso</b> (2): rigetto aggressivo, un po' più rumore.<br>"
                     "<b>Più alto</b> (4–5): quasi nessun rigetto dei valori scuri."),
    "kappa_high": tip("Kappa alto", "Soglia di rigetto verso l'alto (σ): esclude satelliti, aerei, raggi cosmici "
                      "e hot pixel residui.<br>"
                      "<b>Più basso</b> (2): rigetto aggressivo, con pochi frame può erodere i nuclei delle stelle.<br>"
                      "<b>Più alto</b> (4): rigetta solo le anomalie evidenti."),
    "iterations": tip("Iterazioni del rigetto", "Quante volte si ripete il rigetto ricalcolando media e σ sui pixel "
                      "rimasti.<br><b>1</b>: rapido. <b>2</b>: consigliato. <b>3–5</b>: più preciso sulle scie forti, più lento."),
    "debayer": tip("Debayer", "Come si ricavano i colori dal mosaico Bayer del sensore.<br>"
                   "• <b>Piena risoluzione</b>: interpolazione edge-aware a 16 bit, tutti i megapixel.<br>"
                   "• <b>Super-pixel</b>: ogni blocco 2×2 diventa un pixel: metà risoluzione, meno rumore, "
                   "nessun artefatto di colore. Utile per campi larghi o prove rapide."),
    "interp": tip("Interpolazione", "Metodo di ricampionamento durante l'allineamento.<br>"
                  "• <b>Cubica</b>: equilibrio tra nitidezza e artefatti (consigliata).<br>"
                  "• <b>Lanczos</b>: più nitida, possibili anellini attorno alle stelle brillanti.<br>"
                  "• <b>Lineare</b>: più veloce, stelle leggermente più morbide."),
    "hot_sigma": tip("Soglia hot pixel", "Quanto un pixel deve superare i vicini (in σ) per essere considerato "
                     "difettoso quando non ci sono dark.<br>"
                     "<b>Più bassa</b> (3–4): corregge più pixel, rischia di toccare le stelle più piccole.<br>"
                     "<b>Più alta</b> (8–10): solo i pixel chiaramente difettosi."),
    "auto_cosmetic": tip("Hot pixel automatici", "Senza master dark cerca e sostituisce i pixel isolati anomali in ogni light.<br>"
                         "<b>Attivo</b>: consigliato se non hai dark.<br>"
                         "<b>Disattivo</b>: gli hot pixel restano (il kappa-sigma li elimina solo se hai fatto dithering).<br>"
                         "Con i dark questa opzione non interviene."),
    "dark_scaling": tip("Riscala i dark", "Se la posa dei dark è diversa da quella dei light, il segnale termico viene "
                        "riscalato in proporzione (servono anche i bias).<br>"
                        "<b>Disattivo</b>: i dark vengono sottratti così come sono."),
    "auto_crop": tip("Ritaglia i bordi", "Elimina i bordi che, per gli spostamenti tra i frame, non sono coperti da "
                     "tutti gli scatti.<br><b>Disattivo</b>: immagine intera, con bordi più rumorosi o scuri."),
    "workers": tip("Thread", "Quanti frame vengono calibrati in parallelo.<br>"
                   "<b>Più alto</b>: più veloce, ma circa 700 MB di RAM in più per ogni thread (foto da 20 MP).<br>"
                   "<b>1–2</b>: se hai 8 GB di RAM o meno."),
    "band_mb": tip("Memoria per banda", "RAM usata per ogni banda di righe durante lo stacking.<br>"
                   "<b>Più alta</b>: meno passaggi, più veloce.<br>"
                   "<b>Più bassa</b>: più lento ma sicuro su PC con poca memoria."),
    "landscape": tip("Paesaggio: primo piano nitido", "Nelle foto con alberi, orizzonte o edifici lo stack "
                     "allineato sulle stelle sfoca il primo piano. Con questa opzione il primo piano viene "
                     "riconosciuto in automatico (zona scura senza stelle), allineato su sé stesso e ricostruito "
                     "nitido con la mediana dei frame.<br><b>Disattivo</b>: solo cielo (consigliato per il profondo cielo)."),
    "align_model": tip("Modello di allineamento", "Come vengono adattati i frame al riferimento.<br>"
                       "• <b>Similarità</b>: spostamento, rotazione e scala (va bene quasi sempre).<br>"
                       "• <b>Affine</b>: aggiunge l'inclinazione del campo.<br>"
                       "• <b>Omografia</b>: corregge anche la prospettiva: con obiettivi grandangolari (14–24 mm) "
                       "le stelle restano tonde anche negli angoli. Serve un buon numero di stelle."),
    "keep_cache": tip("Tieni i frame in cache", "I frame calibrati e allineati restano sul disco finché non chiudi "
                      "o rifai lo Stack: così <b>Ricombina</b> cambia metodo, kappa o frame esclusi in pochi secondi "
                      "invece di minuti.<br>Costa spazio su disco (~120 MB per frame da 20 MP)."),
    "drizzle": tip("Drizzle 2×", "Produce lo stack a risoluzione doppia sfruttando i piccoli spostamenti tra i "
                   "frame (dithering). Con frame non ditherati ottieni solo un'immagine più grande. File e tempi ×4."),
    "master_library": tip("Libreria master", "Ogni master dark e bias calcolato viene salvato (fotocamera, ISO, posa). "
                          "Quando in una sessione mancano i dark o i bias, viene ripreso quello compatibile "
                          "(stessa fotocamera e ISO, posa entro il 25 %)."),
    "library_dir": tip("Cartella libreria", "Dove vengono salvati i master riutilizzabili. Vuoto = cartella predefinita."),
    "cache_dir": tip("Cache su disco", "Cartella dove vengono salvati i frame calibrati (circa 120 MB per frame da 20 MP), "
                     "cancellati a fine lavoro. Scegli un disco veloce (SSD) con spazio libero.<br>"
                     "Vuoto = cartella temporanea di Windows."),
}

ZONES = {
    "light": tip("Light", "Le foto del soggetto: obbligatorie. Più light = meno rumore "
                 "(4 volte i frame = metà rumore). Devono avere tutte le stesse dimensioni."),
    "dark": tip("Dark", "Scatti con il tappo sull'obiettivo, stessa posa, stessa ISO e temperatura simile ai light. "
                "Servono a mappare e rimuovere hot pixel e rumore termico. Consigliati 10–20."),
    "flat": tip("Flat", "Scatti di un campo uniforme (cielo del crepuscolo, pannello luminoso, maglietta bianca "
                "sull'obiettivo) con la stessa messa a fuoco, diaframma e zoom dei light, esposti a metà istogramma. "
                "Correggono vignettatura e polvere. Consigliati 15–30."),
    "bias": tip("Bias / Offset", "Scatti con il tappo alla posa più breve possibile (es. 1/4000 s), stessa ISO. "
                "Contengono solo il rumore di lettura: servono per calibrare i flat e riscalare i dark. "
                "Consigliati 20–50.<br><b>Non caricare qui i light!</b>"),
}

BUTTONS = {
    "project_open": tip("Apri progetto", "Riapre un progetto .astrostack: file, impostazioni, sviluppo, livelli e maschere."),
    "project_save": tip("Salva progetto", "Salva tutto (file usati, opzioni, sviluppo, livelli, maschere e lo stack "
                        "calcolato) in un file .astrostack, per riprendere il lavoro più tardi."),
    "sort": tip("Smista file", "Scegli file o cartelle miste: dall'EXIF e dall'anteprima ogni file finisce da solo "
                "nella zona giusta (light, dark, flat, bias)."),
    "live": tip("Live", "Osserva una cartella: ogni volta che arrivano nuovi scatti lo stack riparte da solo con tutti "
                "i file, così vedi il risultato crescere durante la sessione."),
    "compare": tip("Prima / Dopo", "Confronto a tendina: a sinistra della linea l'immagine senza sviluppo, a destra "
                   "quella sviluppata. Trascina il cursore per spostare la linea."),
    "stack": tip("Stack", "Avvia tutto: master di calibrazione → calibrazione → stelle → allineamento → "
                 "stacking → gradiente e colori. Scorciatoia: Ctrl+Invio."),
    "cancel": tip("Annulla", "Interrompe l'elaborazione in corso e cancella la cache su disco."),
    "save": tip("Esporta", "Apre la finestra di esportazione: formato (TIFF/PNG/JPG/FITS), qualità e compressione, "
                "risoluzione (anche ingrandimento), nitidezza in uscita. Scorciatoia: Ctrl+S."),
    "stretch": tip("Sviluppo / Lineare", "Sviluppo = anteprima con stiramento e regolazioni del pannello Sviluppo. "
                   "Lineare = dati grezzi dello stack (quasi neri): è ciò che contiene il FITS lineare."),
    "fit": tip("Adatta", "Adatta tutta l'immagine alla finestra. Rotella del mouse per lo zoom, trascina per spostarti."),
    "zoom100": tip("100 %", "Mostra i pixel reali: 1 pixel dello stack = 1 pixel dello schermo. "
                   "Utile per controllare la forma delle stelle."),
    "session": tip("Importa sessione", "Scegli una cartella con sottocartelle Lights / Darks / Flats / Bias (o Offset): "
                   "le quattro zone si riempiono da sole."),
    "frames": tip("Frame", "Mostra o nasconde la tabella con qualità, allineamento e stato di ogni frame."),
    "log": tip("Registro", "Mostra o nasconde il registro dettagliato dell'elaborazione."),
}

COLUMNS = {
    "nome": "Nome del file",
    "stato": "ok = usato · riferimento = frame su cui sono allineati gli altri · scartato / errore = escluso (vedi Note)",
    "stelle": "Stelle rilevate nel frame: poche stelle = nuvole, sfocato o cielo chiaro",
    "fwhm": "Larghezza delle stelle a metà altezza, in pixel: più bassa = più a fuoco e meno mosso",
    "ecc": "Eccentricità: 0 = stelle rotonde, sopra 0,6 = stelle allungate (mosso, inseguimento, coma)",
    "punteggio": "Punteggio di qualità combinato (FWHM, stelle, rumore, eccentricità): 1 = il migliore",
    "peso": "Peso del frame nella media finale (da 0,2 a 1)",
    "spost": "Spostamento in pixel rispetto al frame di riferimento (x, y)",
    "rot": "Rotazione rispetto al riferimento",
    "rms": "Errore residuo dell'allineamento in pixel: sotto 0,5 ottimo, sopra 1,5 sospetto",
    "metodo": "stelle = triangoli di stelle (preciso) · fase = correlazione di fase (solo traslazione) · identità = riferimento",
    "posa": "Tempo di posa letto dall'EXIF",
    "iso": "Sensibilità ISO letta dall'EXIF",
    "hot": "Pixel difettosi corretti in questo frame",
    "scie": "Scie rettilinee rilevate (satelliti, aerei): con il rigetto kappa-sigma spariscono dallo stack",
    "motivo": "Perché il frame è stato scartato o ha dato errore",
}

TOOLS = {
    "gx_path": tip("GraXpert", "Programma gratuito e open source (graxpert.com) con reti neurali per denoise e "
                   "rimozione del gradiente. Scaricalo, aprilo una volta per scaricare i modelli IA, poi indica qui "
                   "il file .exe. AstroStack lo richiama in automatico."),
    "gx_strength": tip("Forza del denoise", "Quanto rumore togliere.<br><b>Bassa</b> (20–40 %): naturale, conserva le "
                       "stelle più deboli.<br><b>Alta</b> (70–100 %): cielo molto liscio, rischio di effetto 'plastica'."),
    "gx_gpu": tip("Scheda video", "Usa la GPU per l'IA: molto più veloce. Se GraXpert dà errore, disattiva e usa la CPU."),
    "denoise": tip("Denoise IA", "Riduce il rumore dello stack con la rete neurale di GraXpert (1–5 minuti). "
                   "Si può annullare con 'Annulla ultima modifica'."),
    "gradient_ai": tip("Gradiente IA", "Rimuove l'inquinamento luminoso con il modello IA di GraXpert: alternativa al "
                       "polinomio di AstroStack, migliore con gradienti complessi."),
    "sn_path": tip("StarNet++", "Programma gratuito (starnetastro.com) che toglie le stelle con una rete neurale. "
                   "Scarica la versione a riga di comando, scompattala e indica starnet++.exe (i file dei pesi devono "
                   "restare nella stessa cartella)."),
    "starnet": tip("Rimuovi le stelle", "Produce l'immagine senza stelle (l'immagine viene prima stirata, come "
                   "richiede StarNet). Le sole stelle vengono salvate accanto al file quando salvi: utili per "
                   "elaborare nebulose e stelle separatamente."),
    "api_key": tip("Chiave API astrometry.net", "Gratuita: registrati su nova.astrometry.net, poi Profilo → API key. "
                   "Serve solo per il riconoscimento degli oggetti (viene inviata una piccola anteprima)."),
    "annotate": tip("Riconosci oggetti", "Invia un'anteprima ridotta a nova.astrometry.net che identifica il campo "
                    "(coordinate, scala) e scrive i nomi di costellazioni, nebulose, galassie e ammassi sull'anteprima. "
                    "Serve internet; ci vogliono 1–3 minuti."),
    "labels": tip("Mostra etichette", "Mostra o nasconde i nomi degli oggetti riconosciuti sull'anteprima "
                  "(non vengono salvati nel file)."),
    "undo": tip("Annulla ultima modifica", "Torna all'immagine prima dell'ultimo strumento IA applicato "
                "(fino a 5 passi indietro)."),
}

DEVELOP = {
    "stretch_type": tip("Tipo di stretch", "Come i dati lineari vengono resi visibili.<br>• <b>Classico (MTF)</b>: "
                        "massimo dettaglio nel fondo.<br>• <b>Arcsinh</b>: le stelle brillanti restano colorate invece di "
                        "diventare bianche.<br>• <b>Ibrido</b>: media dei due."),
    "star_reduce": tip("Riduzione stelle", "Rimpicciolisce le stelle senza cancellarle: la Via Lattea e le nebulose "
                       "risaltano.<br><b>30–50</b>: naturale.<br><b>80–100</b>: molto marcato, le stelle più deboli spariscono."),
    "hsl": tip("HSL", "Regola ogni gamma di colore separatamente: <b>Tonalità</b> la sposta, <b>Saturazione</b> "
               "la rende più o meno viva, <b>Luminanza</b> la schiarisce o scurisce. Esempio: abbassa la saturazione "
               "dell'arancione per attenuare l'inquinamento luminoso, alza il blu del cielo."),
    "enabled": tip("Sviluppo attivo", "Applica le regolazioni all'anteprima e all'esportazione. Disattivo = immagine "
                   "base (solo stiramento automatico)."),
    "auto": tip("Auto", "Regola in automatico Neri e Bianchi in base all'istogramma."),
    "reset": tip("Reimposta", "Riporta tutti i cursori ai valori predefiniti. Doppio clic su una singola etichetta "
                 "reimposta solo quel cursore."),
    "preset_save": tip("Salva preset", "Salva tutte le regolazioni in un file .json da riapplicare ad altre foto."),
    "preset_load": tip("Carica preset", "Carica un preset salvato in precedenza."),
    "stretch_bg": tip("Fondo cielo", "Luminosità a cui viene portato il fondo cielo dallo stiramento automatico.<br>"
                      "<b>Più basso</b> (10–20 %): cielo scuro, contrastato.<br><b>Più alto</b> (30–40 %): più segnale debole "
                      "visibile ma anche più rumore."),
    "stretch_shadows": tip("Taglio ombre", "Quanto fondo viene tagliato a nero dallo stiramento.<br><b>Negativo</b>: tiene "
                           "tutto il segnale debole.<br><b>Positivo</b>: fondo più pulito, rischio di perdere le nebulosità deboli."),
    "exposure": tip("Esposizione", "Luminosità generale, in stop (EV). +1 = doppia luce."),
    "contrast": tip("Contrasto", "Separa chiari e scuri attorno ai mezzitoni. <b>Positivo</b>: più incisivo; "
                    "<b>negativo</b>: più piatto e morbido."),
    "highlights": tip("Alte luci", "Agisce solo sulle zone chiare (nuclei della Via Lattea, stelle grandi).<br>"
                      "<b>Negativo</b>: recupera i dettagli bruciati.<br><b>Positivo</b>: le fa risaltare."),
    "shadows": tip("Ombre", "Agisce solo sulle zone scure.<br><b>Positivo</b>: apre le ombre e mostra il segnale debole.<br>"
                   "<b>Negativo</b>: le chiude, fondo più scuro."),
    "whites": tip("Bianchi", "Sposta il punto di bianco: <b>positivo</b> = le parti più chiare arrivano al bianco puro; "
                  "<b>negativo</b> = le abbassa (utile se le stelle sono bruciate)."),
    "blacks": tip("Neri", "Sposta il punto di nero: <b>negativo</b> = fondo cielo più nero e profondo; "
                  "<b>positivo</b> = solleva i neri."),
    "temperature": tip("Temperatura", "Bilanciamento: <b>verso sinistra</b> più freddo/blu, <b>verso destra</b> più caldo/giallo."),
    "tint": tip("Tinta", "<b>Verso sinistra</b> più verde, <b>verso destra</b> più magenta. Utile contro il verde residuo del sensore."),
    "vibrance": tip("Vividezza", "Aumenta i colori poco saturi lasciando quasi intatti quelli già saturi: più naturale della Saturazione."),
    "saturation": tip("Saturazione", "Intensità di tutti i colori allo stesso modo. Con valori alti il rumore colorato aumenta."),
    "clarity": tip("Chiarezza", "Contrasto locale sui mezzitoni: <b>positivo</b> fa risaltare le nubi della Via Lattea e le nebulose; "
                   "<b>negativo</b> ammorbidisce."),
    "dehaze": tip("Riduci velatura", "Toglie il velo grigio dell'inquinamento luminoso e della foschia: cielo più profondo. "
                  "Esagerando il fondo diventa nero e rumoroso."),
    "sharpen": tip("Nitidezza", "Accentua i dettagli fini. Con la mascheratura alta agisce solo su stelle e strutture, non sul rumore del fondo."),
    "sharpen_radius": tip("Raggio", "Dimensione dei dettagli accentuati: 0,7–1 px per stelle puntiformi, 1,5–3 px per strutture più larghe."),
    "sharpen_masking": tip("Mascheratura", "Protegge il fondo cielo dalla nitidezza: <b>0</b> = tutto viene accentuato (anche il rumore), "
                           "<b>100</b> = solo i bordi netti."),
    "nr_luminance": tip("Riduzione rumore (luminanza)", "Liscia la grana del fondo. Alto = cielo liscio ma dettagli più morbidi."),
    "nr_color": tip("Riduzione rumore (colore)", "Toglie le macchie colorate del rumore senza toccare i dettagli di luminosità. "
                    "Di solito si può alzare molto."),
    "vignette": tip("Vignettatura", "<b>Negativo</b>: scurisce gli angoli (effetto artistico, concentra lo sguardo).<br>"
                    "<b>Positivo</b>: schiarisce gli angoli (compensa la vignettatura dell'obiettivo se non hai i flat)."),
    "grain": tip("Grana", "Aggiunge una grana fine uniforme: maschera il rumore a chiazze e dà un aspetto 'pellicola'."),
    "rotation": tip("Rotazione", "Raddrizza l'orizzonte o inclina la composizione (gradi). I bordi neri vengono tolti se l'opzione sotto è attiva."),
    "auto_crop_rotation": tip("Bordi neri", "Dopo una rotazione ritaglia automaticamente il rettangolo più grande senza angoli neri."),
    "deconv": tip("Deconvoluzione", "Recupera nitidezza invertendo la sfocatura (Richardson-Lucy), applicata solo su "
                  "stelle e dettagli, non sul fondo.<br><b>30–60</b>: stelle più fini.<br>Troppa crea aloni scuri "
                  "attorno alle stelle brillanti."),
    "deconv_radius": tip("Raggio deconvoluzione", "Larghezza stimata delle stelle (FWHM in pixel): guarda la colonna "
                         "FWHM nella tabella dei frame e usa un valore vicino a quello."),
    "wavelet_small": tip("Dettaglio fine", "Struttura più piccola (1–2 px): stelle e granulosità.<br>Negativo = più liscio."),
    "wavelet_medium": tip("Dettaglio medio", "Filamenti di nebulose e bracci di galassie (3–6 px)."),
    "wavelet_large": tip("Strutture grandi", "Nubi e zone estese (10+ px): utile per dare volume alla Via Lattea."),
    "curve": tip("Curva dei toni", "Orizzontale = luminosità originale, verticale = luminosità finale.<br>"
                 "Trascina i punti; clic sulla curva per aggiungerne uno; tasto destro per toglierlo.<br>"
                 "Una S leggera aumenta il contrasto; alzare la parte bassa apre le ombre."),
}

EXPORT = {
    "fmt": tip("Formato", "• <b>TIFF 16 bit</b>: massima qualità, per stampa e ulteriori modifiche.<br>"
               "• <b>TIFF/PNG 8 bit</b>: qualità normale, file più piccoli.<br>• <b>PNG 16 bit</b>: senza perdita, compatibile ovunque.<br>"
               "• <b>JPG</b>: per web e social (con perdita).<br>• <b>FITS</b>: dati lineari senza sviluppo, per ulteriori elaborazioni."),
    "quality": tip("Qualità JPG", "80–90 = ottimo compromesso; 95–100 = quasi senza perdita ma file 2–3 volte più grande."),
    "png_level": tip("Compressione PNG", "Senza perdita: cambia solo dimensione del file e tempo di scrittura."),
    "tiff_comp": tip("Compressione TIFF", "Zlib è senza perdita e dimezza il file; 'Nessuna' si apre più in fretta nei programmi vecchi."),
    "scale_mode": tip("Risoluzione", "Originale, in percentuale (200 % = raddoppia la risoluzione) oppure larghezza in pixel "
                      "(es. 2048 per i social)."),
    "upscale": tip("Ingrandimento", "Metodo usato quando si aumenta la risoluzione: Lanczos è il più nitido."),
    "out_sharpen": tip("Nitidezza in uscita", "Piccola nitidezza aggiunta dopo il ridimensionamento, utile "
                       "(consigliata 'Standard' quando si riduce per il web)."),
    "apply_dev": tip("Regolazioni di Sviluppo", "Esporta l'immagine come la vedi nel pannello Sviluppo. Disattivo = solo stiramento automatico."),
}

LAYERS = {
    "add": tip("Aggiungi immagine", "Carica una foto (TIFF, PNG, JPG, FITS) come nuovo livello sopra gli altri: "
               "ad esempio lo scatto del primo piano fatto con lunga posa, da fondere con il cielo stackato."),
    "dup": tip("Duplica", "Copia il livello selezionato (utile per applicare due sviluppi diversi alla stessa immagine)."),
    "del": tip("Elimina", "Rimuove il livello selezionato. Il livello base non si può eliminare."),
    "move": tip("Sposta", "Cambia l'ordine: i livelli più in alto nell'elenco coprono quelli sotto."),
    "opacity": tip("Opacità", "Quanto il livello copre quelli sottostanti: 100 % = del tutto, 0 % = invisibile."),
    "blend": tip("Fusione", "Come i pixel del livello si combinano con lo sfondo.<br>"
                 "• <b>Normale</b>: copre.<br>• <b>Schiarisci</b>: tiene il più chiaro (ottimo per unire cielo e stelle).<br>"
                 "• <b>Scurisci</b>: tiene il più scuro.<br>• <b>Moltiplica</b>: scurisce (ombre, vignettature).<br>"
                 "• <b>Scherma</b>: schiarisce (bagliori, Via Lattea).<br>• <b>Sovrapponi / Luce soffusa</b>: aumentano il contrasto.<br>"
                 "• <b>Somma</b>: aggiunge luce.<br>• <b>Differenza</b>: mostra le differenze (utile per allineare)."),
    "position": tip("Posizione", "Spostamento del livello in pixel rispetto alla base (a piena risoluzione)."),
    "scale": tip("Scala", "Ingrandisce o riduce il livello (100 % = dimensione originale)."),
    "mask_type": tip("Maschera", "Dove il livello è visibile.<br>• <b>Sfumatura lineare</b>: passaggio graduale (cielo in alto, "
                     "terra in basso).<br>• <b>Luminosità</b>: visibile solo nelle zone chiare (o scure) del livello stesso.<br>"
                     "• <b>Pennello</b>: dipingi tu la zona sull'anteprima.<br>• <b>Primo piano automatico</b>: riconosce "
                     "alberi/orizzonte del livello.<br>• <b>Da file</b>: un'immagine in scala di grigi (bianco = visibile)."),
    "invert": tip("Inverti", "Scambia le zone visibili e nascoste della maschera."),
    "show_mask": tip("Mostra in rosso", "Colora di rosso, sull'anteprima, la zona dove il livello è visibile."),
    "feather": tip("Sfumatura bordo", "Ammorbidisce i bordi della maschera (in pixel a piena risoluzione)."),
    "gradient": tip("Sfumatura", "Percentuale dall'alto (o da sinistra) dove la maschera passa da nascosta a visibile."),
    "luminosity": tip("Luminosità", "Sotto la soglia scura il livello è nascosto, sopra quella chiara è visibile, in mezzo sfuma."),
    "brush_size": tip("Dimensione pennello", "Diametro del pennello in pixel dell'anteprima."),
    "brush_hard": tip("Durezza", "0 = bordo molto morbido, 100 = bordo netto."),
    "paint": tip("Dipingi", "Attiva il pennello: trascina con il tasto sinistro sull'anteprima per rendere visibile il "
                 "livello (o per cancellare, con la casella apposita). Disattiva per tornare a spostare l'immagine."),
    "load_mask": tip("Carica maschera", "Immagine in scala di grigi (bianco = visibile, nero = nascosto), ridimensionata alla tela."),
}
