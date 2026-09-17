"""Report della sessione: un file HTML con statistiche, grafico e anteprima incorporati."""
from __future__ import annotations

import base64
import datetime
import html
import io
import os

import numpy as np


def _jpeg_b64(img: np.ndarray, max_dim: int = 1400, quality: int = 86) -> str:
    import cv2
    from .stretch import to_uint8
    h, w = img.shape[:2]
    f = 1
    while max(h, w) / f > max_dim:
        f *= 2
    small = img if f == 1 else cv2.resize(img, (w // f, h // f), interpolation=cv2.INTER_AREA)
    u8 = to_uint8(small, stretch=False)
    ok, buf = cv2.imencode(".jpg", u8[:, :, ::-1] if u8.ndim == 3 else u8, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""


def _bar_svg(values, labels, color="#F2B441", height=120) -> str:
    """Grafico a barre semplice (SVG in linea)."""
    if not values:
        return ""
    vmax = max(values) or 1.0
    w = max(320, 14 * len(values))
    bars = []
    step = w / len(values)
    for i, v in enumerate(values):
        hh = max(2.0, height * float(v) / vmax)
        bars.append(f'<rect x="{i * step + 2:.1f}" y="{height - hh:.1f}" width="{step - 4:.1f}" height="{hh:.1f}" '
                    f'fill="{color}" opacity="0.85"><title>{html.escape(str(labels[i]))}: {v:.2f}</title></rect>')
    return (f'<svg viewBox="0 0 {w} {height}" width="100%" height="{height}" '
            f'style="background:#141A2A;border:1px solid #2E3A57;border-radius:8px">' + "".join(bars) + "</svg>")


def write_report(path: str, result, settings, dev_params=None, zones: dict | None = None,
                 image: np.ndarray | None = None) -> str:
    """Scrive il report HTML e restituisce il percorso."""
    frames = list(result.frames)
    ok = [f for f in frames if f.status == "ok"]
    fw = [f.fwhm for f in ok if f.fwhm > 0]
    ecc = [f.eccentricity for f in ok if f.eccentricity > 0]
    exp = [f.exposure for f in ok if f.exposure]
    total = sum(exp) if exp else 0.0
    rms = [f.transform.rms for f in ok if f.transform is not None]
    rows = []
    for f in frames:
        t = f.transform
        color = {"ok": "#5FD39B", "scartato": "#F07E6E", "errore": "#F07E6E"}.get(f.status, "#94A0BE")
        state = html.escape("riferimento" if f.is_reference else f.status)
        cells = [f"{f.n_stars}", f"{f.fwhm:.2f}", f"{f.eccentricity:.2f}",
                 f"{getattr(f, 'saturated_pct', 0.0):.1f}%", f"{getattr(f, 'transparency', 1.0):.2f}×",
                 f"{f.score:.2f}", f"{f.weight:.2f}",
                 (f"{t.shift[0]:+.1f}, {t.shift[1]:+.1f}" if t else ""), (f"{t.rotation_deg:+.3f}°" if t else ""),
                 (f"{t.rms:.2f}" if t else ""), str(f.trails), html.escape(f.reason or "")]
        rows.append(f'<tr><td>{html.escape(f.name)}</td><td style="color:{color}">{state}</td>'
                    + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    stats = [
        ("Frame usati", f"{result.n_used} su {len(frames)}"),
        ("Tempo totale di posa", f"{total / 60:.1f} min" if total else "n/d"),
        ("Riferimento", result.reference),
        ("FWHM mediana", f"{np.median(fw):.2f} px" if fw else "n/d"),
        ("Eccentricità mediana", f"{np.median(ecc):.2f}" if ecc else "n/d"),
        ("Errore di allineamento", f"{np.median(rms):.2f} px (mediano)" if rms else "n/d"),
        ("Gradiente", result.gradient.describe() + (" → rimosso" if result.gradient.applied else "")),
        ("Colori", result.gradient.describe_color() or "non calibrati"),
        ("Combinazione", settings.method),
        ("Durata elaborazione", f"{result.elapsed:.0f} s"),
    ]
    if zones:
        stats.insert(1, ("File", ", ".join(f"{k} {v if isinstance(v, int) else len(v)}" for k, v in zones.items() if v)))
    img_b64 = _jpeg_b64(image if image is not None else result.image)
    fwhm_svg = _bar_svg([f.fwhm for f in frames], [f.name for f in frames])
    score_svg = _bar_svg([f.score for f in frames], [f.name for f in frames], color="#74B4FF")
    dev_rows = ""
    if dev_params is not None:
        import dataclasses
        d = dataclasses.asdict(dev_params)
        default = type(dev_params)()
        changed = {k: v for k, v in d.items() if v != getattr(default, k)}
        if changed:
            dev_rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k, v in changed.items())

    doc = f"""<!doctype html><html lang="it"><meta charset="utf-8">
<title>AstroStack — report della sessione</title>
<style>
 body {{ background:#141A2A; color:#E8ECF5; font-family:"IBM Plex Sans",Segoe UI,sans-serif; margin:0; padding:28px; }}
 h1 {{ margin:0 0 4px; font-size:26px; }} h2 {{ font-size:16px; color:#F2B441; margin:26px 0 8px; }}
 .sub {{ color:#94A0BE; margin-bottom:18px; }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; }}
 .card {{ background:#1B2336; border:1px solid #2E3A57; border-left:3px solid #F2B441; border-radius:9px; padding:10px 12px; }}
 .card b {{ display:block; color:#94A0BE; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.4px; }}
 img {{ max-width:100%; border:1px solid #2E3A57; border-radius:10px; }}
 table {{ border-collapse:collapse; width:100%; font-size:12.5px; }}
 th,td {{ padding:5px 8px; border-bottom:1px solid #2E3A57; text-align:left; white-space:nowrap; }}
 th {{ color:#94A0BE; font-weight:600; }} tr:hover td {{ background:#1F273D; }}
 .foot {{ color:#94A0BE; font-size:11.5px; margin-top:24px; border-top:2px solid #F2B441; padding-top:10px; }}
</style>
<h1>AstroStack — report della sessione</h1>
<div class="sub">{datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
<div class="grid">{''.join(f'<div class="card"><b>{html.escape(k)}</b>{html.escape(str(v))}</div>' for k, v in stats)}</div>
<h2>Risultato</h2>
{'<img src="data:image/jpeg;base64,' + img_b64 + '">' if img_b64 else ''}
<h2>Nitidezza per frame (FWHM px)</h2>{fwhm_svg}
<h2>Punteggio di qualità per frame</h2>{score_svg}
<h2>Dettaglio dei frame</h2>
<table><tr><th>File</th><th>Stato</th><th>Stelle</th><th>FWHM</th><th>Ecc.</th><th>Sat.</th><th>Trasparenza</th><th>Qualità</th><th>Peso</th>
<th>Spostamento</th><th>Rotazione</th><th>RMS</th><th>Scie</th><th>Note</th></tr>{''.join(rows)}</table>
{('<h2>Regolazioni di sviluppo</h2><table><tr><th>Parametro</th><th>Valore</th></tr>' + dev_rows + '</table>') if dev_rows else ''}
<div class="foot">Generato da AstroStack — stacking, sviluppo e composizione per l'astrofotografia</div>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path
