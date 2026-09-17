"""Allineamento (registrazione) dei frame.

Metodo principale: matching di triangoli di stelle tramite invarianti geometrici
(rapporti tra i lati, invarianti per rotazione, scala e traslazione) con voto
delle corrispondenze e stima RANSAC di una trasformazione di similarità.
È lo stesso principio usato da astroalign / DeepSkyStacker.

Metodo di riserva: correlazione di fase (sola traslazione) quando le stelle
non bastano.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Optional

import cv2
import numpy as np
from scipy.spatial import cKDTree

NEIGHBOURS = 6   # vicini usati per costruire i triangoli locali


@dataclass
class Transform:
    M: np.ndarray            # 2x3 affine oppure 3x3 omografia (sorgente -> riferimento)
    n_inliers: int
    rms: float               # residuo RMS in pixel
    method: str              # "stelle" | "fase" | "identità"
    n_stars: int = 0

    @property
    def is_homography(self) -> bool:
        return self.M.shape[0] == 3

    @property
    def rotation_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.M[1, 0], self.M[0, 0])))

    @property
    def scale(self) -> float:
        return float(np.hypot(self.M[0, 0], self.M[1, 0]))

    @property
    def shift(self) -> tuple[float, float]:
        return float(self.M[0, 2]), float(self.M[1, 2])


def identity() -> Transform:
    return Transform(np.array([[1, 0, 0], [0, 1, 0]], np.float64), 0, 0.0, "identità")


# ----------------------------------------------------------------------------
# invarianti dei triangoli
# ----------------------------------------------------------------------------
def _triangles(xy: np.ndarray, max_points: int, min_side: float = 8.0, max_ratio: float = 8.0):
    pts = xy[:max_points].astype(np.float64)
    n = len(pts)
    if n < 3:
        return np.zeros((0, 2)), np.zeros((0, 3), int)
    # triangoli "locali": ogni stella con i suoi vicini più prossimi (molto più
    # distintivi e molto meno numerosi di tutte le combinazioni possibili)
    k = min(NEIGHBOURS + 1, n)
    _, nn = cKDTree(pts).query(pts, k=k)
    tri_set = set()
    for i in range(n):
        group = sorted(set(int(j) for j in np.atleast_1d(nn[i]) if j < n))
        for c in combinations(group, 3):
            tri_set.add(c)
    tri = np.asarray(sorted(tri_set), dtype=int)
    p0, p1, p2 = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    d01 = np.linalg.norm(p0 - p1, axis=1)   # lato opposto al vertice 2
    d12 = np.linalg.norm(p1 - p2, axis=1)   # opposto a 0
    d20 = np.linalg.norm(p2 - p0, axis=1)   # opposto a 1
    sides = np.stack([d12, d20, d01], axis=1)          # sides[:, k] = lato opposto al vertice k
    order = np.argsort(sides, axis=1)                  # dal lato più corto al più lungo
    s_sorted = np.take_along_axis(sides, order, axis=1)
    a, b, c = s_sorted[:, 0], s_sorted[:, 1], s_sorted[:, 2]
    ok = (a > min_side) & (c / np.maximum(a, 1e-9) < max_ratio)
    inv = np.stack([c / np.maximum(b, 1e-9), b / np.maximum(a, 1e-9)], axis=1)
    # vertici riordinati coerentemente con i lati (vertice opposto al lato più corto per primo)
    verts = np.take_along_axis(tri, order, axis=1)
    return inv[ok], verts[ok]


def find_transform(src_xy: np.ndarray, dst_xy: np.ndarray, max_points: int = 70,
                   tol: float = 0.01, min_votes: int = 3, reproj: float = 2.0,
                   model: str = "similarita") -> Optional[Transform]:
    """Trova la similarità che porta le stelle `src` sulle stelle `dst` (riferimento)."""
    if len(src_xy) < 5 or len(dst_xy) < 5:
        return None
    inv_s, ver_s = _triangles(src_xy, max_points)
    inv_d, ver_d = _triangles(dst_xy, max_points)
    if len(inv_s) < 3 or len(inv_d) < 3:
        return None
    tree = cKDTree(inv_d)
    radii = tol * (1.0 + np.linalg.norm(inv_s, axis=1))   # tolleranza proporzionale ai rapporti
    matches = tree.query_ball_point(inv_s, r=radii)
    ns, nd = min(len(src_xy), max_points), min(len(dst_xy), max_points)
    votes = np.zeros((ns, nd), np.int32)
    for i, lst in enumerate(matches):
        if not lst or len(lst) > 12:  # triangoli troppo ambigui: ignora
            continue
        vs = ver_s[i]
        for j in lst:
            vd = ver_d[j]
            votes[vs[0], vd[0]] += 1
            votes[vs[1], vd[1]] += 1
            votes[vs[2], vd[2]] += 1
    if votes.max() < min_votes:
        return None
    # corrispondenze mutue (massimo di riga e di colonna)
    best_col = votes.argmax(axis=1)
    best_row = votes.argmax(axis=0)
    pairs = []
    for i in range(ns):
        j = best_col[i]
        if votes[i, j] >= min_votes and best_row[j] == i:
            pairs.append((i, j))
    if len(pairs) < 4:
        return None
    pairs = np.asarray(pairs)
    s = src_xy[pairs[:, 0]].astype(np.float32)
    d = dst_xy[pairs[:, 1]].astype(np.float32)
    M, inl = cv2.estimateAffinePartial2D(s, d, method=cv2.RANSAC, ransacReprojThreshold=reproj,
                                         maxIters=3000, confidence=0.995, refineIters=10)
    if M is None or inl is None or int(inl.sum()) < 4:
        return None
    # raffinamento: proietta tutte le stelle e usa tutte le coppie entro 2 px
    M2 = refine_transform(M, src_xy, dst_xy, radius=max(reproj, 1.5), model=model)
    if M2 is not None:
        M = M2
    res = _residuals(M, src_xy, dst_xy, radius=max(reproj, 1.5))
    name = {"affine": "stelle (affine)", "omografia": "stelle (omografia)"}.get(model, "stelle")
    return Transform(M.astype(np.float64), int(res.size), float(np.sqrt(np.mean(res ** 2))) if res.size else 0.0,
                     name, n_stars=int(len(src_xy)))


def _apply(M: np.ndarray, xy: np.ndarray) -> np.ndarray:
    xy = np.asarray(xy, np.float64)
    if M.shape[0] == 3:                       # omografia
        pts = np.hstack([xy, np.ones((len(xy), 1))]) @ M.T
        return pts[:, :2] / np.maximum(pts[:, 2:3], 1e-9)
    return xy @ M[:, :2].T + M[:, 2]


def _residuals(M: np.ndarray, src_xy: np.ndarray, dst_xy: np.ndarray, radius: float) -> np.ndarray:
    proj = _apply(M, src_xy)
    tree = cKDTree(np.asarray(dst_xy, np.float64))
    dist, _ = tree.query(proj, distance_upper_bound=radius)
    return dist[np.isfinite(dist)]


def refine_transform(M: np.ndarray, src_xy: np.ndarray, dst_xy: np.ndarray, radius: float = 2.0,
                    model: str = "similarita"):
    """Raffina usando tutte le stelle accoppiate. `model`: similarita | affine | omografia."""
    proj = _apply(M, src_xy)
    tree = cKDTree(np.asarray(dst_xy, np.float64))
    dist, idx = tree.query(proj, distance_upper_bound=radius)
    ok = np.isfinite(dist)
    if ok.sum() < 4:
        return None
    s = np.asarray(src_xy, np.float32)[ok]
    d = np.asarray(dst_xy, np.float32)[idx[ok]]
    n = int(ok.sum())
    if model == "omografia" and n >= 20:
        M2, inl = cv2.findHomography(s, d, method=cv2.RANSAC, ransacReprojThreshold=radius, maxIters=4000,
                                     confidence=0.995)
        if M2 is not None and inl is not None and int(inl.sum()) >= 15:
            return M2
    if model in ("affine", "omografia") and n >= 10:
        M2, inl = cv2.estimateAffine2D(s, d, method=cv2.RANSAC, ransacReprojThreshold=radius,
                                       maxIters=3000, confidence=0.995, refineIters=20)
        if M2 is not None and inl is not None and int(inl.sum()) >= 8:
            return M2
    M2, inl = cv2.estimateAffinePartial2D(s, d, method=cv2.RANSAC, ransacReprojThreshold=radius,
                                          maxIters=2000, confidence=0.995, refineIters=20)
    if M2 is None or inl is None or int(inl.sum()) < 4:
        return None
    return M2


# ----------------------------------------------------------------------------
# correlazione di fase (riserva)
# ----------------------------------------------------------------------------
def phase_transform(ref_lum: np.ndarray, lum: np.ndarray, factor: int = 1) -> Optional[Transform]:
    """Traslazione tra due luminanze (stesse dimensioni, già ridotte di `factor`)."""
    if ref_lum.shape != lum.shape:
        return None
    a = np.ascontiguousarray(ref_lum, np.float32)
    b = np.ascontiguousarray(lum, np.float32)
    a = a - float(np.median(a))
    b = b - float(np.median(b))
    win = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), resp = cv2.phaseCorrelate(a, b, win)
    if not np.isfinite(dx) or not np.isfinite(dy) or resp < 0.05:
        return None
    # b è a traslata di (dx, dy): per riportare b su a serve -(dx, dy)
    M = np.array([[1.0, 0.0, -dx * factor], [0.0, 1.0, -dy * factor]], np.float64)
    return Transform(M, 0, float(resp), "fase")


# ----------------------------------------------------------------------------
# warping
# ----------------------------------------------------------------------------
_INTERP = {"cubica": cv2.INTER_CUBIC, "lanczos": cv2.INTER_LANCZOS4, "lineare": cv2.INTER_LINEAR}


def _as_h(M: np.ndarray) -> np.ndarray:
    if M.shape[0] == 3:
        return M.astype(np.float64)
    return np.vstack([M[:2].astype(np.float64), [0.0, 0.0, 1.0]])


def warp_full(img: np.ndarray, M: np.ndarray, interp: str = "cubica") -> tuple[np.ndarray, np.ndarray]:
    """Applica M all'intera immagine. Restituisce (immagine, maschera di copertura bool)."""
    h, w = img.shape[:2]
    flags = _INTERP.get(interp, cv2.INTER_CUBIC)
    if M.shape[0] == 3:
        out = cv2.warpPerspective(img, _as_h(M), (w, h), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        cov = cv2.warpPerspective(np.full((h, w), 255, np.uint8), _as_h(M), (w, h), flags=cv2.INTER_NEAREST,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    else:
        out = cv2.warpAffine(img, M[:2].astype(np.float64), (w, h), flags=flags,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        cov = cv2.warpAffine(np.full((h, w), 255, np.uint8), M[:2].astype(np.float64), (w, h),
                             flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    cov = cv2.erode(cov, np.ones((5, 5), np.uint8)) > 0
    return out, cov


def source_rows_for_band(M: np.ndarray, y0: int, y1: int, width: int, height: int, margin: int = 6):
    """Intervallo di righe sorgente necessario per calcolare le righe [y0, y1) di destinazione."""
    Ai = np.linalg.inv(_as_h(M))
    corners = np.array([[0, y0, 1], [width, y0, 1], [0, y1, 1], [width, y1, 1]], np.float64)
    src = corners @ Ai.T
    src = src[:, :2] / np.maximum(src[:, 2:3], 1e-9)
    ys0 = int(np.floor(src[:, 1].min())) - margin
    ys1 = int(np.ceil(src[:, 1].max())) + margin
    return max(0, ys0), min(height, ys1)


def warp_band(src_rows: np.ndarray, ys0: int, M: np.ndarray, y0: int, y1: int, width: int,
              interp: str = "cubica") -> tuple[np.ndarray, np.ndarray]:
    """Calcola le righe [y0, y1) dell'immagine registrata usando solo le righe sorgente da ys0."""
    flags = _INTERP.get(interp, cv2.INTER_CUBIC)
    T_src = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, float(ys0)], [0.0, 0.0, 1.0]])     # ritaglio -> immagine piena
    T_dst = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, -float(y0)], [0.0, 0.0, 1.0]])     # destinazione -> banda
    Hm = T_dst @ _as_h(M) @ T_src
    if M.shape[0] == 3:
        out = cv2.warpPerspective(src_rows, Hm, (width, y1 - y0), flags=flags,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        cov = cv2.warpPerspective(np.full(src_rows.shape[:2], 255, np.uint8), Hm, (width, y1 - y0),
                                  flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    else:
        A = Hm[:2]
        out = cv2.warpAffine(src_rows, A, (width, y1 - y0), flags=flags,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        cov = cv2.warpAffine(np.full(src_rows.shape[:2], 255, np.uint8), A, (width, y1 - y0),
                             flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    cov = cv2.erode(cov, np.ones((5, 5), np.uint8)) > 0
    return out, cov


def scale_transform(M: np.ndarray, factor: float) -> np.ndarray:
    """Adatta una trasformazione a un'immagine ridotta di `factor` (es. anteprima a 1/4)."""
    if M.shape[0] == 3:
        S = np.diag([1.0 / factor, 1.0 / factor, 1.0])
        return S @ M.astype(np.float64) @ np.diag([factor, factor, 1.0])
    S = M[:2].astype(np.float64).copy()
    S[:, 2] /= factor
    return S
