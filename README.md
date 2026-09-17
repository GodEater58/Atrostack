# AstroStack

Stacking ed editing di immagini per astrofotografia. AstroStack ha due ambienti principali:
**Stack**, per partire dai frame grezzi, ed **Editor**, per aprire e sviluppare direttamente
TIFF, FITS, PNG, JPG o RAW senza dover eseguire uno stack. Calibrazione, allineamento,
scarto dei frame peggiori e rimozione dell'inquinamento luminoso restano automatici nel flusso di stacking.

## Cosa fa

| Passo | Come |
|---|---|
| Lettura RAW | LibRaw (tramite `rawpy`): CR2, CR3, NEF, ARW, DNG, RAF, ORF, PEF, RW2 e ~1000 fotocamere. Anche FITS, TIFF, PNG, JPG |
| Calibrazione | Master bias / dark / flat (mediana) nel dominio Bayer, come DeepSkyStacker e Siril. Riscalatura dei dark se la posa è diversa |
| Hot pixel | Mappa esatta dal master dark; senza dark, correzione cosmetica automatica che non tocca le stelle |
| Qualità | Per ogni frame: stelle, FWHM, eccentricità, rumore, saturazione e trasparenza → punteggio e peso |
| Scarto automatico | I frame mossi, nuvolosi o sfocati vengono esclusi (severità regolabile); gli altri sono pesati per qualità |
| Allineamento | Matching di triangoli di stelle (invarianti a rotazione, scala e traslazione) + RANSAC: precisione sub-pixel, gestisce rotazione di campo e deriva. Riserva: correlazione di fase |
| Stacking | Automatico, Kappa-sigma, Winsorized Sigma, Linear-fit clipping, mediana o media per bande: memoria limitata anche con 100 frame da 24 MP |
| Inquinamento luminoso | Campionamento robusto del fondo (esclude nebulose **e** primo piano: alberi, orizzonte), polinomio 2D, sottrazione con mantenimento del livello |
| Colori | Bilanciamento del bianco dai coefficienti del RAW (prima del debayer), fondo neutralizzato, calibrazione dei colori sulle stelle (riferimento bianco = colore medio delle stelle, come Siril / PixInsight) |
| Anteprima | Migliora frame dopo frame durante l'elaborazione, con auto-stretch tipo Siril |
| Salvataggio | TIFF 16 bit, FITS 32 bit, PNG 16 bit, JPG (con stretch) |

## Installazione (Windows)

Serve solo Python 3.10–3.14 ([python.org](https://www.python.org/downloads/), spuntare "Add Python to PATH").

1. Estrai lo zip.
2. Doppio clic su **`AstroStack.exe`**: apre il programma senza finestre nere. La prima volta chiede il permesso
   di scaricare le librerie (alcuni minuti), poi parte subito. Tasto destro → *Invia a* → *Desktop* per avere
   l'icona sul desktop. Se Windows SmartScreen avvisa (file non firmato): *Ulteriori informazioni → Esegui comunque*.

In alternativa: `AvviaAstroStack.bat` fa la stessa cosa ma tiene aperta la finestra dei messaggi (utile se qualcosa
non va); `CreaEseguibile.bat` costruisce una versione completamente indipendente da Python in `dist\AstroStack\`.

Test rapido senza fotocamera (dal prompt dei comandi aperto nella cartella): `python tests\synthetic_test.py`.

Test regressioni Live/Drizzle: `python tests\regression_live_drizzle.py`.

Su macOS/Linux: `pip install -r requirements.txt` e `python main.py`.

## Uso

1. Trascina i file (o intere cartelle) nelle quattro zone: **Light** (obbligatori), **Dark**, **Flat**, **Bias**.
   In alternativa **Importa sessione…** riconosce da solo le sottocartelle `Lights / Darks / Flats / Bias (Offset)`.
   Passando il mouse su qualsiasi opzione, zona o pulsante compare una breve spiegazione di cosa fa e cosa cambia
   attivandola o alzandola/abbassandola.
2. Premi **Stack** (o `Ctrl+Invio`). L'anteprima si aggiorna frame dopo frame; la tabella **Frame** mostra
   stelle, FWHM, saturazione, trasparenza, punteggio, spostamento e rotazione di ogni scatto e perché un frame è stato scartato.
3. A fine elaborazione puoi attivare/disattivare la rimozione del gradiente e la neutralizzazione del fondo:
   si riapplicano in pochi secondi senza ri-stackare. **Salva…** (`Ctrl+S`) esporta il risultato.

**Quale formato salvare?** L'anteprima mostra l'immagine con un *auto-stretch* (curva non lineare che tira
fuori il segnale debole). Il file salvato può essere:
- **TIFF come anteprima** (16 bit): identico a ciò che vedi, pronto per Lightroom, Photoshop, GIMP;
- **TIFF / FITS lineare**: i dati grezzi dello stack, per chi continua l'elaborazione in Siril o PixInsight.
  Aperto in Lightroom un file lineare appare quasi nero: è normale, non è un errore.
Il pulsante *Stretch automatico / Lineare* sopra l'anteprima mostra la differenza.

## Colori

Uno stack di RAW "grezzi" è sempre verde: il sensore ha il doppio dei pixel verdi e nessun bilanciamento del
bianco. AstroStack risolve in tre passi, tutti su dati lineari (come raccomanda la documentazione di Siril):

1. **Bianco dal RAW** (*Avanzate → Bianco*): applica i coefficienti "luce diurna" del file RAW prima del debayer.
2. **Neutralizza il fondo**: porta il fondo cielo allo stesso livello nei tre canali (toglie la dominante dell'inquinamento luminoso).
3. **Calibra i colori sulle stelle**: misura il colore di centinaia di stelle non sature e riscala R e B in modo che
   la stella "media" sia bianca; il fondo resta neutro. Gli ultimi due passi si possono riattivare/disattivare a fine
   stack senza ricalcolare.

Con un primo piano (alberi, orizzonte) tieni il **grado del modello** a 1–2: i gradi 3–4 possono creare aloni.

## Consigli

- **Dark**: stessa posa, stesso ISO e temperatura simile ai light. Con i dark gli hot pixel vengono rimossi
  in modo esatto; senza dark interviene la correzione cosmetica automatica (buona ma non perfetta).
- **Flat**: correggono vignettatura e polvere; sono normalizzati per canale, quindi non alterano il colore.
- **Bias**: servono soprattutto per riscalare i dark quando la posa è diversa e per calibrare i flat.
- **Dithering** (spostare leggermente l'inquadratura tra uno scatto e l'altro) + kappa-sigma = hot pixel,
  satelliti e raggi cosmici spariscono da soli.
- Con meno di 5 light il rigetto kappa-sigma non è affidabile: il programma passa da solo a mediana/media.
- Le opzioni vengono ricordate tra una sessione e l'altra.

## Sviluppo (stile Lightroom)

Il pannello **Sviluppo** (pulsante in alto a destra o `Ctrl+D`) si apre da solo a fine stack e permette di
rifinire la foto direttamente in AstroStack, con anteprima in tempo reale e istogramma:

| Gruppo | Regolazioni |
|---|---|
| Base | Tipo di stretch (MTF, **Arcsinh**, ibrido, **Masked Stretch**), Fondo cielo e taglio ombre, Esposizione, Contrasto, Alte luci, Ombre, Bianchi, Neri, **Auto** e **Assistito** |
| Colore | Temperatura, Tinta, Vividezza, Saturazione |
| Astrofoto | Rimozione gradiente, neutralizzazione cielo, protezione stelle |
| HSL | Tonalità, Saturazione e Luminanza per otto gamme di colore (rosso, arancione, giallo, verde, acqua, blu, viola, magenta) |
| Dettaglio | Chiarezza, Riduci velatura, Nitidezza (quantità, raggio, mascheratura), Riduzione rumore luminanza e colore, **Riduzione stelle** |
| Curva dei toni | Curva a punti: trascina, clic per aggiungere, tasto destro per togliere |
| Effetti | Vignettatura, Grana |
| Geometria | Rotazione (con eliminazione dei bordi neri), ritaglio per lato, riflessioni |

Le regolazioni sono non distruttive: si applicano a piena risoluzione solo all'esportazione. *Reimposta* riporta
tutto a zero, doppio clic su un'etichetta azzera quel cursore, *Salva/Carica preset* riusa le impostazioni su
altre foto. La modalità **Editor** apre direttamente TIFF/PNG/JPG/FITS e i principali RAW senza stack; offre
anche preset rapidi, snapshot dello sviluppo e cronologia delle regolazioni.

## Progetti, smistamento, live

- **Salva progetto… / Apri progetto…**: un file `.astrostack` (più una cartella `_dati`) conserva file usati,
  opzioni, sviluppo, livelli, maschere, snapshot e modalità attiva. I livelli vengono copiati nei dati del
  progetto, quindi restano riapribili anche se il file sorgente esterno viene spostato.
- **Smista file…** (o trascina file misti sulla finestra): ogni scatto finisce da solo in Light, Dark, Flat o Bias
  in base a EXIF e anteprima; il Registro spiega il perché di ogni scelta.
- **Live**: scegli la cartella dove arrivano gli scatti. Dopo il primo stack, i nuovi light vengono calibrati e
  allineati incrementando la cache esistente; i frame precedenti non vengono più riletti e ricalibrati.
- **Libreria master** (*Avanzate*): dark e bias calcolati vengono salvati per fotocamera/ISO/posa e riusati quando
  in una sessione mancano.
- **Scie stellari**: in *Combinazione* scegli "Scie stellari": nessun allineamento, il pixel più luminoso vince.
- **Drizzle 2×** (*Avanzate*): stack a risoluzione doppia dai frame ditherati.
- **Prima / Dopo**: confronto a tendina sull'anteprima (cursore per spostare la linea).

## Livelli (fusione di più foto)

Il pannello **Livelli** (pulsante in alto) permette di comporre più immagini, come in Photoshop: il livello base è
lo stack (o l'immagine aperta), sopra si aggiungono altre foto, per esempio lo scatto lungo del primo piano.
Per ogni livello: opacità, metodo di fusione (Normale, Schiarisci, Scurisci, Moltiplica, Scherma, Sovrapponi,
Luce soffusa, Somma, Differenza), posizione e scala, e una maschera: sfumatura lineare, luminosità, **pennello**
(si dipinge direttamente sull'anteprima), primo piano automatico, o da file. Il pannello Sviluppo regola il
livello selezionato, così cielo e primo piano hanno ciascuno il proprio sviluppo. L'esportazione salva la
composizione a piena risoluzione.

## Esportazione

**Esporta…** (`Ctrl+S`) apre la finestra con: formato (TIFF 16/8 bit, PNG 16/8 bit, JPG, FITS lineare),
qualità JPG, livello di compressione PNG, compressione TIFF, risoluzione (originale, percentuale fino al 400 %,
larghezza in pixel) con ingrandimento Lanczos/cubico/lineare, nitidezza in uscita e scelta se applicare le
regolazioni di Sviluppo. Dopo StarNet viene esportato anche il file delle sole stelle.

## Strumenti IA (gratuiti)

Nel pannello **Strumenti IA** (colonna sinistra) AstroStack richiama programmi esterni gratuiti sull'immagine
appena stackata; ogni passo si può annullare con *Annulla ultima modifica*.

| Strumento | Cosa fa | Come attivarlo |
|---|---|---|
| **GraXpert** – Denoise IA | Riduce il rumore con una rete neurale, preservando le stelle | Scarica [GraXpert](https://www.graxpert.com) (open source), aprilo una volta perché scarichi i modelli IA, indica il file `.exe` nel pannello |
| **GraXpert** – Gradiente IA | Rimuove l'inquinamento luminoso con il modello IA (alternativa al polinomio) | Come sopra |
| **StarNet++** – Rimuovi le stelle | Immagine senza stelle + file delle sole stelle (salvato accanto al risultato) | Scarica la versione a riga di comando da [starnetastro.com](https://www.starnetastro.com), indica `starnet++.exe` |
| **astrometry.net** – Riconosci oggetti | Identifica il campo e scrive i nomi di costellazioni, nebulose, galassie sull'anteprima | Account gratuito su [nova.astrometry.net](https://nova.astrometry.net) → Profilo → API key, da incollare nel pannello (serve internet) |
| **Paesaggio: primo piano nitido** (in *Opzioni*) | Riconosce alberi/orizzonte (zona scura senza stelle), li allinea su sé stessi e li ricostruisce nitidi con la mediana dei frame | Spunta l'opzione prima di premere Stack. È un algoritmo automatico, non una rete neurale |

I modelli IA di GraXpert e StarNet++ sono gratuiti per uso personale (licenza non commerciale).

## Comodità d'uso

| Funzione | Dove |
|---|---|
| **Gestisci…** in ogni zona | Elenco dei file: rimuovi o sposta i singoli scatti in un'altra zona |
| **Ricombina** | Rifà solo la somma dai frame già calibrati (pochi secondi): cambia metodo, kappa o frame esclusi |
| Casella nella tabella | Togli la spunta a uno scatto per escluderlo, poi premi Ricombina |
| Doppio clic su una riga | Mostra quel singolo frame nell'anteprima: capisci perché è stato scartato |
| Tempo rimanente | Stimato e mostrato nella barra di stato; a fine stack la finestra lampeggia |
| `Ctrl+Z` / `Ctrl+Y` | Annulla e ripeti nello Sviluppo (40 passi) |
| Barra spaziatrice | Prima / Dopo istantaneo |
| Controlli prima dello stack | Avvisa se dark e light hanno ISO o pose diverse, se un file è in due zone, se i bias sono troppo lunghi |
| Cartelle ricordate, progetto salvato alla chiusura | Meno clic, niente lavoro perso |
| **Report…** | Pagina HTML con statistiche, grafici per frame, anteprima e tabella completa |
| **Lotti…** | Più sessioni una dopo l'altra: salva stack, JPG e report in ogni cartella |
| **☀ / ☾** | Tema chiaro o notturno, in tempo reale |
| Guida rapida | Alla prima apertura (poi si può disattivare) |

## Novità fotografiche

- **Modello di allineamento** (*Avanzate*): similarità, affine oppure **omografia**, che corregge la prospettiva:
  con un 14–24 mm le stelle restano tonde anche negli angoli.
- **Somma di più notti**: carica come light gli stack FITS di serate diverse; il numero di frame di ognuno viene
  letto dall'intestazione e usato come peso.
- **Deconvoluzione** e **wavelet** (dettaglio fine / medio / grandi strutture) nel pannello Sviluppo.
- **Pipetta**: un clic su una zona di cielo e temperatura e tinta si regolano perché quel punto sia neutro.
- **Maschera "Stelle del livello"** nei Livelli: elaborazione selettiva di nebulose e stelle.
- **Rilevamento delle scie** di satelliti e aerei: colonna *Scie* nella tabella.
- **Esportazione**: preset (Instagram, Web, Sfondo 4K, Stampa A3), autore e copyright nei metadati, firma
  stampata sull'immagine.

## Lingua

In alto a destra c'è l'interruttore **IT | EN**: l'interfaccia cambia lingua all'istante, senza riavviare e senza
perdere il lavoro in corso. Vengono tradotti pulsanti, opzioni, popup di aiuto, tabella dei frame, pannelli
Sviluppo e Livelli, finestre di esportazione e messaggi di stato. La scelta viene ricordata per la volta dopo.

The **IT | EN** switch in the top-right corner changes the interface language instantly, without restarting and
without losing your work: buttons, options, help popups, the frames table, the Develop and Layers panels, the
export window and the status messages. Your choice is remembered.

## Interfaccia

Caratteri IBM Plex Sans / Mono inclusi (licenza SIL OFL), icona dell'applicazione, tema notturno con accento oro.

Pulsanti e zone hanno transizioni animate (passaggio del mouse, pressione, lampo colorato quando arrivano i file),
l'anteprima sfuma da un frame al successivo e lo zoom è fluido (rotella, *Adatta*, *100 %*). Durante lo stacking il
pulsante pulsa; a fine lavoro e dopo ogni salvataggio compare una notifica che sparisce da sola.

## Requisiti di sistema

- RAM: circa 700 MB per ogni thread di calibrazione (impostazione *Avanzate → Thread*), più la memoria
  per banda di stacking (default 900 MB). Con 8 GB di RAM usa 1–2 thread.
- Disco: i frame calibrati vengono messi in cache come `.npy` a 16 bit (~120 MB per frame da 20 MP)
  nella cartella temporanea (o in quella scelta in *Avanzate → Cache*); la cache viene cancellata a fine lavoro.
- Tempi indicativi (PC desktop moderno): 2–4 s per frame da 20 MP + 1–2 minuti di combinazione per 30 frame.

## Note tecniche

- I RAW vengono letti come mosaico Bayer con sottrazione del livello di nero per canale; la
  demosaicizzazione (OpenCV, algoritmo edge-aware a 16 bit) avviene solo dopo la calibrazione.
- Il tempo di posa e l'ISO sono letti dall'EXIF (CR2/NEF/ARW/DNG); per CR3 non sono disponibili, quindi
  la riscalatura dei dark non è attiva (usa dark con la stessa posa).
- TIFF/JPG prodotti dalla fotocamera sono già non lineari: lo stacking funziona, ma la calibrazione con
  dark/flat è corretta solo con dati lineari (RAW o FITS).
- Il riferimento per l'allineamento è il frame con il punteggio di qualità più alto.
- Il ritaglio automatico elimina i bordi non coperti da tutti i frame (disattivabile in *Avanzate*).

## Struttura del codice

```
main.py                    avvio
astrostack/core/loader.py        lettura RAW / FITS / TIFF / PNG
astrostack/core/calibration.py   master frame, hot pixel, correzione cosmetica, debayer
astrostack/core/stars.py         rilevamento stelle, FWHM, punteggio di qualità
astrostack/core/registration.py  allineamento (triangoli + RANSAC, correlazione di fase)
astrostack/core/stacking.py      cache su disco e combinazione per bande (kappa-sigma…)
astrostack/core/gradient.py      inquinamento luminoso e neutralizzazione del fondo
astrostack/core/stretch.py       auto-stretch per anteprima
astrostack/core/io_out.py        salvataggio
astrostack/core/develop.py       sviluppo stile Lightroom ed esportazione
astrostack/core/layers.py        livelli: fusione, maschere, pennello
astrostack/core/project.py       progetto .astrostack
astrostack/core/sorter.py        smistamento automatico dei file
astrostack/core/master_library.py libreria dei master dark/bias
astrostack/core/report.py        report HTML della sessione
astrostack/core/foreground.py    paesaggio: primo piano nitido
astrostack/core/ai_tools.py      GraXpert, StarNet++, astrometry.net
astrostack/core/pipeline.py      orchestrazione completa (usabile anche senza GUI)
astrostack/gui/                  interfaccia PySide6 (i18n.py: italiano/inglese)
tests/synthetic_test.py          test end-to-end con dati sintetici
```

Uso da script, senza interfaccia:

```python
from astrostack.core.pipeline import Pipeline, Settings
from astrostack.core.io_out import save_result

res = Pipeline(lights, darks, flats, bias, Settings()).run()
save_result("stack.tif", res.image)
```
