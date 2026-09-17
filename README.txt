AstroStack 1.4 - Assistito più prudente

Cosa cambia:
- gradiente > 125%: trattato come possibile paesaggio/orizzonte, non corretto automaticamente;
- stretch lineare con ombre più aperte;
- denoise/dettaglio più moderati;
- auto-tone non può più chiudere liberamente il punto nero;
- Shadow Guard: se Assistito introduce troppi pixel quasi neri, riapre Ombre/Neri;
- test sintetico per Via Lattea + primo piano scuro + gradiente forte.

INSTALLAZIONE

1. Estrai fix_astrostack_assisted_140.py nella root:
   C:\Users\nicol\Documents\Atrostack

2. PowerShell:
   cd "C:\Users\nicol\Documents\Atrostack"
   python .\fix_astrostack_assisted_140.py

3. Output atteso:
   ASTROSTACK_140_ASSISTED_FIX_FILES_OK

4. Test:
   cd source\app
   python tests\test_assisted_140.py

5. Output atteso:
   ASTROSTACK_140_ASSISTED_SHADOW_GUARD_OK

6. Avvio:
   Start-Process python -ArgumentList "main.py"

Poi rifai lo stesso stack o riapri il risultato lineare e premi Assistito per confrontare.
