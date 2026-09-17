from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "source" / "app"
TARGET = APP / "astrostack" / "core" / "develop.py"
TEST = APP / "tests" / "test_assisted_140.py"

NEW_ASSISTED = 'def assisted_develop(image: np.ndarray, p: DevelopParams, is_linear: bool = True) -> tuple[DevelopParams, dict]:\n    """Costruisce una ricetta Assistita prudente e completamente modificabile.\n\n    La 1.4 tratta i gradienti estremi come potenziale paesaggio/orizzonte:\n    in quel caso non forza l\'estrazione del fondo. Dopo l\'auto-tone misura\n    anche quanto nero è stato introdotto e riapre le ombre se necessario.\n    """\n    q = DevelopParams.from_json(p.to_json())\n    report: dict[str, float | int | str | bool] = {}\n\n    # Stretch protetto sulle immagini lineari. Un valore negativo apre il\n    # taglio ombre invece di avvicinare il punto nero al fondo cielo.\n    if is_linear:\n        q.stretch_type = "masked"\n        q.stretch_bg = 22.0\n        q.stretch_shadows = -8.0\n\n    src = image.astype(np.float32, copy=False)\n\n    # Analisi del gradiente. Un valore enorme è spesso causato da orizzonte,\n    # alberi, tetti o primo piano: in quel caso NON aumentiamo la correzione.\n    try:\n        from .gradient import fit_background\n\n        _model, gi = fit_background(src, degree=2, grid=(10, 14))\n        strength = float(gi.strength)\n        report["gradient_strength"] = strength\n        report["gradient_detected"] = bool(gi.detected)\n\n        if gi.detected and strength > 1.25:\n            report["gradient_reliable"] = False\n            report["scene_hint"] = "paesaggio/orizzonte probabile"\n            q.gradient_correction = 0.0\n            q.sky_neutralization = min(float(q.sky_neutralization), 15.0)\n\n        elif gi.detected:\n            report["gradient_reliable"] = True\n            q.gradient_correction = float(\n                np.clip(35.0 + strength * 45.0, 35.0, 70.0)\n            )\n            q.sky_neutralization = 45.0\n\n    except Exception:\n        report["gradient_reliable"] = False\n\n    base = base_image(src, q, is_linear)\n\n    if base.ndim == 2:\n        base = np.repeat(base[:, :, None], 3, axis=2)\n\n    L = np.clip(_lum(base), 0.0, 1.0)\n    sub = L[::4, ::4]\n\n    hp = sub - cv2.GaussianBlur(\n        np.ascontiguousarray(sub, np.float32),\n        (0, 0),\n        1.2,\n    )\n\n    noise = (\n        1.4826\n        * float(np.median(np.abs(hp - np.median(hp))))\n        + 1e-9\n    )\n\n    lo, med, hi = [\n        float(v)\n        for v in np.percentile(\n            sub,\n            [1.0, 50.0, 99.5],\n        )\n    ]\n\n    dyn = max(hi - lo, 1e-6)\n\n    baseline_black = float(np.mean(sub < 0.015))\n    baseline_deep = float(np.mean(sub < 0.035))\n\n    report.update(\n        {\n            "noise": noise,\n            "median": med,\n            "dynamic_range": dyn,\n            "baseline_black_fraction": baseline_black,\n            "baseline_deep_shadow_fraction": baseline_deep,\n        }\n    )\n\n    # Denoise moderato, mantenendo le stelle protette.\n    q.nr_luminance = float(\n        np.clip(6.0 + noise * 1050.0, 6.0, 38.0)\n    )\n    q.nr_color = float(\n        np.clip(q.nr_luminance * 0.68, 5.0, 30.0)\n    )\n    q.star_protect = 78.0\n\n    # Contrasto locale/dettaglio conservativo.\n    snr_like = dyn / max(noise, 1e-6)\n\n    q.clarity = float(\n        np.clip(\n            7.0\n            + np.log10(max(snr_like, 1.0))\n            * 4.0,\n            7.0,\n            18.0,\n        )\n    )\n\n    q.dehaze = 5.0 if med < 0.45 else 3.0\n    q.wavelet_small = 3.0 if noise < 0.02 else 0.0\n    q.wavelet_medium = 6.0\n    q.wavelet_large = 2.0\n\n    # Colore prudente: vividezza più che saturazione globale.\n    mx = base.max(axis=2)\n    mn = base.min(axis=2)\n    sat = (mx - mn) / np.maximum(mx, 1e-4)\n    sat_med = float(np.median(sat[::4, ::4]))\n\n    report["median_saturation"] = sat_med\n\n    q.vibrance = float(\n        np.clip(\n            24.0 - 38.0 * sat_med,\n            6.0,\n            20.0,\n        )\n    )\n    q.saturation = 2.0 if sat_med < 0.22 else 0.0\n\n    # Stelle: stima FWHM e densità per sharpening/riduzione stelle.\n    try:\n        from .stars import detect_stars\n\n        sf = detect_stars(\n            src if is_linear else base,\n            max_stars=300,\n            sigma=4.5,\n        )\n\n        report["stars"] = int(sf.n_detected)\n        report["fwhm"] = float(sf.fwhm)\n\n        if sf.fwhm > 0:\n            q.sharpen_radius = float(\n                np.clip(\n                    sf.fwhm / 2.8,\n                    0.8,\n                    2.4,\n                )\n            )\n            q.sharpen = float(\n                np.clip(\n                    17.0 - noise * 190.0,\n                    7.0,\n                    17.0,\n                )\n            )\n\n        density = sf.n_detected / max(\n            base.shape[0]\n            * base.shape[1]\n            / 1_000_000.0,\n            0.1,\n        )\n\n        q.star_reduce = float(\n            np.clip(\n                (density - 90.0) / 22.0,\n                0.0,\n                18.0,\n            )\n        )\n\n    except Exception:\n        pass\n\n    # Auto-tone come rifinitura, non come strumento che può chiudere\n    # liberamente il punto nero.\n    q = auto_tone(\n        image,\n        q,\n        is_linear=is_linear,\n    )\n\n    # Protezione ombre 1.4:\n    # il risultato Assistito non deve introdurre molta più area quasi nera\n    # rispetto allo stretch di base. Il primo piano realmente nero resta nero,\n    # ma evitiamo di trasformare il cielo debole in nero puro.\n    try:\n        max_dim = 1200\n        ph, pw = image.shape[:2]\n\n        if max(ph, pw) > max_dim:\n            scale = max_dim / float(max(ph, pw))\n            preview_src = cv2.resize(\n                image,\n                (\n                    max(8, int(round(pw * scale))),\n                    max(8, int(round(ph * scale))),\n                ),\n                interpolation=cv2.INTER_AREA,\n            )\n        else:\n            preview_src = image\n\n        preview = develop(\n            preview_src,\n            q,\n            is_linear=is_linear,\n            scale=1.0,\n        )\n\n        if preview.ndim == 2:\n            preview = np.repeat(\n                preview[:, :, None],\n                3,\n                axis=2,\n            )\n\n        pL = np.clip(_lum(preview), 0.0, 1.0)\n\n        black_fraction = float(\n            np.mean(pL < 0.015)\n        )\n        deep_fraction = float(\n            np.mean(pL < 0.035)\n        )\n\n        allowed_black = min(\n            0.40,\n            max(\n                0.06,\n                baseline_black + 0.05,\n            ),\n        )\n\n        allowed_deep = min(\n            0.55,\n            max(\n                0.14,\n                baseline_deep + 0.08,\n            ),\n        )\n\n        report["assisted_black_fraction_before_guard"] = black_fraction\n        report["assisted_deep_shadow_fraction_before_guard"] = deep_fraction\n        report["allowed_black_fraction"] = allowed_black\n\n        if (\n            black_fraction > allowed_black\n            or deep_fraction > allowed_deep\n        ):\n            # Auto-tone non può più spingere i neri in modo aggressivo.\n            q.blacks = max(float(q.blacks), -2.0)\n            q.shadows = max(float(q.shadows), 18.0)\n\n            if is_linear:\n                q.stretch_shadows = min(\n                    float(q.stretch_shadows),\n                    -12.0,\n                )\n\n            preview = develop(\n                preview_src,\n                q,\n                is_linear=is_linear,\n                scale=1.0,\n            )\n\n            if preview.ndim == 2:\n                preview = np.repeat(\n                    preview[:, :, None],\n                    3,\n                    axis=2,\n                )\n\n            pL = np.clip(\n                _lum(preview),\n                0.0,\n                1.0,\n            )\n\n            black_fraction = float(\n                np.mean(pL < 0.015)\n            )\n\n            if black_fraction > allowed_black + 0.03:\n                q.blacks = max(\n                    float(q.blacks),\n                    0.0,\n                )\n                q.shadows = max(\n                    float(q.shadows),\n                    28.0,\n                )\n\n                if is_linear:\n                    q.stretch_shadows = min(\n                        float(q.stretch_shadows),\n                        -18.0,\n                    )\n\n                if med < 0.20:\n                    q.exposure = max(\n                        float(q.exposure),\n                        0.08,\n                    )\n\n            report["shadow_guard_applied"] = True\n\n        else:\n            report["shadow_guard_applied"] = False\n\n    except Exception:\n        report["shadow_guard_applied"] = False\n\n    return q, report\n'
TEST_CONTENT = '"""Regressione Assistito 1.4: paesaggio + gradiente forte."""\nfrom __future__ import annotations\n\nimport os\nimport sys\n\nimport numpy as np\n\nsys.path.insert(\n    0,\n    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),\n)\n\nfrom astrostack.core import gradient\nfrom astrostack.core.develop import (\n    DevelopParams,\n    _lum,\n    assisted_develop,\n    develop,\n)\n\n\ndef _synthetic_scene() -> np.ndarray:\n    h, w = 260, 420\n\n    yy, xx = np.mgrid[0:h, 0:w]\n\n    # Cielo lineare con gradiente molto forte.\n    sky = (\n        0.018\n        + 0.055 * (xx / max(w - 1, 1))\n        + 0.020 * (yy / max(h - 1, 1))\n    ).astype(np.float32)\n\n    img = np.dstack(\n        (\n            sky * 1.04,\n            sky,\n            sky * 0.96,\n        )\n    )\n\n    # Stelle.\n    rng = np.random.default_rng(42)\n    for _ in range(140):\n        x = int(rng.integers(5, w - 5))\n        y = int(rng.integers(5, int(h * 0.68)))\n        value = float(rng.uniform(0.12, 0.55))\n        img[y - 1:y + 2, x - 1:x + 2] += value\n\n    # Primo piano scuro: deve restare scuro senza far chiudere anche il cielo.\n    horizon = int(h * 0.72)\n    img[horizon:, :, :] *= 0.08\n\n    # Sagoma nera limitata.\n    img[int(h * 0.80):, :int(w * 0.24), :] = 0.001\n\n    return np.clip(img, 0.0, 1.0).astype(np.float32)\n\n\ndef main() -> int:\n    scene = _synthetic_scene()\n\n    original_fit = gradient.fit_background\n\n    try:\n        def fake_fit_background(img, degree=2, grid=(16, 24)):\n            info = gradient.GradientInfo(\n                detected=True,\n                strength=2.30,\n                snr=50.0,\n                degree=degree,\n                n_samples=100,\n            )\n            model = np.zeros_like(img, dtype=np.float32)\n            return model, info\n\n        gradient.fit_background = fake_fit_background\n\n        params, report = assisted_develop(\n            scene,\n            DevelopParams(),\n            is_linear=True,\n        )\n\n    finally:\n        gradient.fit_background = original_fit\n\n    assert report.get("gradient_reliable") is False\n    assert params.gradient_correction <= 5.0\n    assert params.sky_neutralization <= 20.0\n    assert params.stretch_shadows < 0.0\n    assert params.blacks >= -2.01\n\n    result = develop(\n        scene,\n        params,\n        is_linear=True,\n        scale=1.0,\n    )\n\n    lum = _lum(result)\n\n    # Il primo piano può essere una silhouette; ciò che non deve accadere\n    # è trasformare gran parte del cielo in nero puro.\n    sky_lum = lum[: int(lum.shape[0] * 0.70)]\n\n    assert float(np.mean(sky_lum < 0.015)) < 0.10\n    assert float(np.median(sky_lum)) > 0.08\n\n    print("ASTROSTACK_140_ASSISTED_SHADOW_GUARD_OK")\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'


def branch_name() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> int:
    if not (ROOT / ".git").exists():
        print("ERRORE: esegui dalla root del repository AstroStack.")
        return 2

    branch = branch_name()
    if branch and branch != "astrostack-1.4-ui":
        print("ERRORE: branch attuale =", branch)
        print("Passa prima ad astrostack-1.4-ui.")
        return 3

    if not TARGET.is_file():
        print("ERRORE: file non trovato:", TARGET)
        return 4

    text = TARGET.read_text(encoding="utf-8-sig")

    start = "def assisted_develop("
    end = (
        "# ----------------------------------------------------------------------------\n"
        "# esportazione\n"
    )

    a = text.find(start)
    b = text.find(end, a)

    if a < 0 or b < 0:
        print("ERRORE: non trovo la funzione assisted_develop.")
        return 5

    backup = TARGET.with_name(
        TARGET.name + ".before_assisted_140.bak"
    )

    if not backup.exists():
        backup.write_text(
            text,
            encoding="utf-8",
        )

    updated = text[:a] + NEW_ASSISTED.rstrip() + "\n\n\n" + text[b:]
    TARGET.write_text(
        updated,
        encoding="utf-8",
    )

    TEST.write_text(
        TEST_CONTENT,
        encoding="utf-8",
    )

    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "py_compile",
                str(TARGET),
                str(TEST),
            ],
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        print("ERRORE: compilazione fallita. Ripristino backup.")
        TARGET.write_text(
            text,
            encoding="utf-8",
        )
        return 6

    print("ASTROSTACK_140_ASSISTED_FIX_FILES_OK")
    print("Backup:", backup)
    print()
    print("Ora esegui:")
    print(r"  cd source\app")
    print(r"  python tests\test_assisted_140.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
