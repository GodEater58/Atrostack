# AstroStack 1.2.0 Preview

## Qualità dello stack

- Nuova modalità **Automatico**: sceglie Media con pochissimi frame, Winsorized Sigma con sessioni piccole e Kappa-Sigma dalle sessioni più robuste.
- Nuovo **Linear-fit clipping** per sessioni con fondo cielo e luminosità differenti: normalizza ogni frame al riferimento robusto prima del rigetto degli outlier.
- Subframe Analyzer ampliato con **percentuale di stelle sature** e indice di **trasparenza** relativo alla sessione.
- La trasparenza entra con peso leggero nel quality score solo quando le pose sono confrontabili, così gli stack HDR non vengono penalizzati.
- Live Stack aggiornato per usare le nuove metriche anche sui frame aggiunti successivamente.

## Editor / Sviluppo

- Nuovo **Masked Stretch**: usa MTF sulle strutture deboli e Arcsinh sulle alte luci per preservare stelle e nuclei luminosi.
- **Rimozione gradiente** regolabile direttamente nell'Editor standalone, quindi utilizzabile anche su TIFF/FITS già pronti.
- **Neutralizzazione cielo** regolabile come parte del flusso non distruttivo.
- Nuova **Protezione stelle** per limitare l'effetto di denoise, wavelet, deconvoluzione e sharpening sui nuclei stellari.
- Nuovo pulsante **Assistito**: analizza gradiente, rumore, dinamica, saturazione e stelle e costruisce una ricetta di sviluppo usando i normali controlli visibili. Nulla viene nascosto o reso irreversibile.

## Test

- Confermato il test di regressione Live incrementale + Ricombina Drizzle 2x.
- Aggiunti test sintetici per Masked Stretch, sviluppo assistito e Linear-fit clipping.
