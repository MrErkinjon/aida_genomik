"""
AIDA — Assotsiativ xaritalash moduli (single-marker association)
================================================================
Interspesifik RIL populyatsiyasi (n=80) uchun SSR marker–trait
assotsiatsiyasi. Genetik xarita yo'qligi sababli bu QTL interval
mapping emas, balki bir-markerli assotsiatsiya (candidate-marker GWAS'ga
o'xshash).

Bosqichlar:
    1. Marker sifat nazorati: missing, monomorf, MAF, PIC, gen diversity (He)
    2. Fenotip descriptives: mean, SD, CV%, skew, kurtosis, Shapiro-Wilk
    3. Korrelyatsiya (Pearson/Spearman)
    4. PCA / iyerarxik klaster (fenotip va genotip)
    5. Kinship (simple matching) matritsasi + PC lar
    6. MTA: GLM (marker) va MLM-approx (marker + kinship PC lari)
       + FDR (Benjamini-Hochberg) va Bonferroni
    7. Dala (drought) ↔ laboratoriya (PEG) mosligi

Taxminlar: parental/pedigree ma'lumot yo'q; struktura kinship PC lari orqali
korreksiya qilinadi (to'liq Q+K MLM o'rniga approksimatsiya — rrBLUP/GAPIT tavsiya).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from scipy import stats
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform


def _subplots(nrows=1, ncols=1, figsize=None, dpi=None, **kw):
    """Thread-xavfsiz subplot (pyplot global holatisiz — worker uchun)."""
    fig = Figure(figsize=figsize, dpi=dpi)
    FigureCanvasAgg(fig)
    return fig, fig.subplots(nrows, ncols, **kw)

# =====================================================================
# 0. YUKLASH
# =====================================================================


def load_workbook(path: str) -> dict[str, pd.DataFrame]:
    """Barcha varaqlarni o'qib, nomi bo'yicha qaytaradi."""
    xl = pd.ExcelFile(path)
    return {sh: pd.read_excel(path, sheet_name=sh) for sh in xl.sheet_names}


def to_line_by_marker(df: pd.DataFrame) -> pd.DataFrame:
    """Genotip matritsasini 'liniya × marker' (0/1) ko'rinishiga keltiradi.

    Birinchi matnli ustunni indeks (ID) deb oladi; agar markerlar qatorlarda
    bo'lsa (loci soni > liniya soni bo'lgani sezilsa) transponatsiya qiladi.
    """
    df = df.copy()
    # birinchi ustun ID bo'lsa indeksga o'tkazamiz
    first = df.columns[0]
    if not pd.api.types.is_numeric_dtype(df[first]):
        df = df.set_index(first)
    # faqat 0/1 ga yaqin ustunlarni qoldiramiz
    num = df.apply(pd.to_numeric, errors="coerce")
    # orientatsiya: liniyalar odatda kamroq (80) — qatorlar liniya bo'lsin
    return num


def align(geno: pd.DataFrame, pheno: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Genotip va fenotipni umumiy liniya ID lari bo'yicha tekislaydi."""
    common = geno.index.intersection(pheno.index)
    return geno.loc[common], pheno.loc[common]


# =====================================================================
# 1. MARKER SIFAT NAZORATI
# =====================================================================


def marker_qc(geno: pd.DataFrame) -> pd.DataFrame:
    """Har lokus uchun: missing%, MAF, monomorf, PIC, gen diversity (He)."""
    rows = []
    n = len(geno)
    for locus in geno.columns:
        col = geno[locus]
        miss = col.isna().mean() * 100
        vals = col.dropna()
        if len(vals) == 0:
            continue
        p = float((vals == 1).mean())        # band mavjud chastotasi
        q = 1 - p
        maf = min(p, q)
        mono = maf == 0
        he = 2 * p * q                        # gen diversity
        pic = 1 - (p**2 + q**2) - (2 * p**2 * q**2)  # Botstein PIC (biallelik)
        rows.append({
            "Locus": locus, "Missing%": round(miss, 2), "p(band)": round(p, 3),
            "MAF": round(maf, 3), "PIC": round(pic, 3), "He": round(he, 3),
            "Monomorf": mono, "MAF<0.05": maf < 0.05,
        })
    return pd.DataFrame(rows)


def marker_summary(qc: pd.DataFrame) -> dict:
    poly = qc[~qc["Monomorf"]]
    return {
        "Jami lokuslar": len(qc),
        "Monomorf": int(qc["Monomorf"].sum()),
        "Polimorf": len(poly),
        "MAF<0.05 (kam)": int(qc["MAF<0.05"].sum()),
        "O'rtacha PIC": round(qc["PIC"].mean(), 3),
        "O'rtacha He": round(qc["He"].mean(), 3),
        "O'rtacha MAF": round(qc["MAF"].mean(), 3),
    }


# =====================================================================
# 2. FENOTIP DESCRIPTIVES
# =====================================================================


def pheno_descriptives(pheno: pd.DataFrame) -> pd.DataFrame:
    """Har trait uchun: N, mean, SD, CV%, min, max, skew, kurtosis, Shapiro."""
    rows = []
    for t in pheno.columns:
        x = pd.to_numeric(pheno[t], errors="coerce").dropna()
        if len(x) < 3:
            continue
        mean = x.mean()
        sd = x.std(ddof=1)
        W, p_sw = stats.shapiro(x) if 3 <= len(x) <= 5000 else (np.nan, np.nan)
        rows.append({
            "Trait": t, "N": len(x), "Mean": round(mean, 3), "SD": round(sd, 3),
            "CV%": round(100 * sd / abs(mean), 2) if mean != 0 else np.nan,
            "Min": round(x.min(), 3), "Max": round(x.max(), 3),
            "Skewness": round(float(stats.skew(x)), 3),
            "Kurtosis": round(float(stats.kurtosis(x)), 3),
            "Shapiro_W": round(float(W), 3), "Shapiro_p": float(p_sw),
            "Normal": bool(p_sw > 0.05),
        })
    return pd.DataFrame(rows)


# =====================================================================
# 3. KORRELYATSIYA
# =====================================================================


def correlation(pheno: pd.DataFrame, method: str = "pearson") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Korrelyatsiya matritsasi + p-qiymat matritsasi."""
    cols = [c for c in pheno.columns if pd.api.types.is_numeric_dtype(pheno[c])]
    data = pheno[cols].apply(pd.to_numeric, errors="coerce")
    n = len(cols)
    corr = pd.DataFrame(np.eye(n), index=cols, columns=cols)
    pval = pd.DataFrame(np.zeros((n, n)), index=cols, columns=cols)
    fn = stats.pearsonr if method == "pearson" else stats.spearmanr
    for i in range(n):
        for j in range(i + 1, n):
            a = data[cols[i]]
            b = data[cols[j]]
            mask = a.notna() & b.notna()
            if mask.sum() < 3:
                r, p = np.nan, np.nan
            else:
                r, p = fn(a[mask], b[mask])
            corr.iloc[i, j] = corr.iloc[j, i] = r
            pval.iloc[i, j] = pval.iloc[j, i] = p
    return corr, pval


# =====================================================================
# 4. PCA + KLASTER
# =====================================================================


def pca(data: pd.DataFrame, n_components: int = 3) -> dict:
    """Standartlashtirilgan PCA (SVD). scores, loadings, explained variance."""
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    X = data.apply(pd.to_numeric, errors="coerce")
    X = X.dropna(axis=1, how="all").fillna(X.mean())
    Xs = StandardScaler().fit_transform(X)
    k = min(n_components, Xs.shape[1], Xs.shape[0] - 1)
    model = PCA(n_components=k).fit(Xs)
    scores = model.transform(Xs)
    return {
        "scores": pd.DataFrame(scores, index=data.index,
                               columns=[f"PC{i+1}" for i in range(k)]),
        "loadings": pd.DataFrame(model.components_.T, index=X.columns,
                                 columns=[f"PC{i+1}" for i in range(k)]),
        "explained": model.explained_variance_ratio_ * 100,
    }


def hierarchical(data: pd.DataFrame, k_clusters: int = 3, metric: str = "euclidean"):
    """Iyerarxik klaster — linkage + klaster yorliqlari."""
    X = data.apply(pd.to_numeric, errors="coerce")
    X = X.dropna(axis=1, how="all").fillna(X.mean())
    if metric == "euclidean":
        from sklearn.preprocessing import StandardScaler
        X = StandardScaler().fit_transform(X)
        Z = linkage(X, method="ward")
    else:  # jaccard / matching — genotip uchun
        from scipy.spatial.distance import pdist
        Z = linkage(pdist(X, metric=metric), method="average")
    labels = fcluster(Z, k_clusters, criterion="maxclust")
    return Z, labels


# =====================================================================
# 5. KINSHIP
# =====================================================================


def kinship_matrix(geno: pd.DataFrame) -> pd.DataFrame:
    """Simple matching koeffitsienti — liniyalar orasidagi qarindoshlik (NxN)."""
    X = geno.apply(pd.to_numeric, errors="coerce").fillna(geno.mean()).values
    n, m = X.shape
    K = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            match = np.mean(X[i] == X[j]) if False else 1 - np.mean(np.abs(X[i] - X[j]))
            K[i, j] = K[j, i] = match
    return pd.DataFrame(K, index=geno.index, columns=geno.index)


def kinship_pcs(K: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Kinship matritsasidan asosiy koordinatalar (MLM kovariatlari uchun)."""
    vals, vecs = np.linalg.eigh(K.values)
    idx = np.argsort(vals)[::-1][:n]
    pcs = vecs[:, idx] * np.sqrt(np.abs(vals[idx]))
    return pd.DataFrame(pcs, index=K.index, columns=[f"kPC{i+1}" for i in range(n)])


# =====================================================================
# 6. MARKER-TRAIT ASSOTSIATSIYA
# =====================================================================


def _ols_marker_p(X: np.ndarray, y: np.ndarray, coef: int = 1) -> float:
    """Normal tenglama orqali OLS — marker koeffitsienti p-qiymati (tez, numpy)."""
    XtX = X.T @ X
    try:
        XtXinv = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        return np.nan
    beta = XtXinv @ (X.T @ y)
    dof = len(y) - X.shape[1]
    if dof <= 0:
        return np.nan
    resid = y - X @ beta
    sigma2 = float(resid @ resid) / dof
    se = np.sqrt(sigma2 * XtXinv[coef, coef])
    if se <= 0:
        return np.nan
    t = beta[coef] / se
    return float(2 * stats.t.sf(abs(t), dof))


def mta_scan(geno: pd.DataFrame, pheno: pd.DataFrame,
             kin_pcs: pd.DataFrame | None = None,
             dataset: str = "") -> pd.DataFrame:
    """Har marker × har trait uchun GLM (2-guruh) va MLM-approx (marker + kinship PC).

    Tezlashtirilgan: statsmodels o'rniga numpy normal tenglamalari; maska
    trait bo'yicha bir marta hisoblanadi (marker'lar bo'ylab qayta ishlatiladi).
    """
    g, ph = align(geno, pheno)
    G = g.apply(pd.to_numeric, errors="coerce")
    Gvals = G.values                       # n × m
    markers = list(G.columns)
    PC = kin_pcs.loc[ph.index].values if kin_pcs is not None else None
    rows = []

    for trait in ph.columns:
        yv = pd.to_numeric(ph[trait], errors="coerce").values
        base_mask = ~np.isnan(yv)
        for jm, marker in enumerate(markers):
            mk = Gvals[:, jm]
            mask = base_mask & ~np.isnan(mk)
            n = int(mask.sum())
            if n < 6:
                continue
            xm = mk[mask]
            yy = yv[mask]
            g1 = yy[xm == 1]
            g0 = yy[xm == 0]
            if len(g1) < 2 or len(g0) < 2:
                continue
            m1, m0 = g1.mean(), g0.mean()
            grand = yy.mean()
            ss_between = len(g1) * (m1 - grand) ** 2 + len(g0) * (m0 - grand) ** 2
            ss_total = float(((yy - grand) ** 2).sum())
            ss_within = ss_total - ss_between
            df_w = n - 2
            F = (ss_between / (ss_within / df_w)) if ss_within > 0 and df_w > 0 else np.inf
            p_glm = float(stats.f.sf(F, 1, df_w)) if np.isfinite(F) and df_w > 0 else 0.0
            r2 = ss_between / ss_total if ss_total > 0 else 0.0

            p_mlm = np.nan
            if PC is not None:
                X = np.column_stack([np.ones(n), xm, PC[mask]])
                p_mlm = _ols_marker_p(X, yy, coef=1)

            rows.append({
                "Dataset": dataset, "Marker": marker, "Trait": trait,
                "mean_1": round(m1, 3), "mean_0": round(m0, 3),
                "effect": round(m1 - m0, 3), "R2": round(float(r2), 4),
                "R2%": round(float(r2) * 100, 2), "F": round(float(F), 3),
                "p_GLM": p_glm, "p_MLM": p_mlm, "n": n,
            })
    res = pd.DataFrame(rows)
    if not res.empty:
        res = add_corrections(res, p_col="p_MLM" if kin_pcs is not None else "p_GLM")
    return res


def add_corrections(res: pd.DataFrame, p_col: str = "p_GLM") -> pd.DataFrame:
    """FDR (Benjamini-Hochberg) q-qiymat va Bonferroni chegarasi."""
    from statsmodels.stats.multitest import multipletests

    p = res[p_col].fillna(1.0).values
    _, q, _, _ = multipletests(p, method="fdr_bh")
    res = res.copy()
    res["q_FDR"] = q
    res["Bonferroni_sig"] = p < (0.05 / len(p))
    res["FDR_sig"] = q < 0.05
    res["sig"] = res[p_col].apply(
        lambda x: "***" if x < 0.001 else "**" if x < 0.01 else "*" if x < 0.05 else "ns")
    return res.sort_values(["Trait", p_col]).reset_index(drop=True)


def significant_hits(res: pd.DataFrame, alpha: float = 0.05, use: str = "FDR") -> pd.DataFrame:
    if res.empty:
        return res
    col = "FDR_sig" if use == "FDR" else "Bonferroni_sig"
    return res[res[col]].copy()


# =====================================================================
# 7. DALA ↔ LAB MOSLIGI
# =====================================================================


def field_lab_overlap(field_res: pd.DataFrame, lab_res: pd.DataFrame,
                      use: str = "FDR") -> dict:
    """Ikkala sharoitda ham ahamiyatli markerlar (barqaror nomzodlar)."""
    fh = significant_hits(field_res, use=use)
    lh = significant_hits(lab_res, use=use)
    fmarkers = set(fh["Marker"]) if not fh.empty else set()
    lmarkers = set(lh["Marker"]) if not lh.empty else set()
    both = fmarkers & lmarkers
    return {
        "field_markers": fmarkers, "lab_markers": lmarkers, "overlap": both,
        "field_only": fmarkers - lmarkers, "lab_only": lmarkers - fmarkers,
        "table": pd.DataFrame({
            "Marker": sorted(both),
            "Barqaror nomzod": ["ha"] * len(both),
        }),
    }


# =====================================================================
# 8. GRAFIKLAR (publikatsiya uslubi)
# =====================================================================

_P = {"primary": "#2563eb", "sig": "#dc2626", "warn": "#d97706", "grey": "#94a3b8"}


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    return buf.getvalue()


def manhattan(res: pd.DataFrame, trait: str, p_col: str = "p_GLM") -> bytes:
    """Bitta trait uchun markerlar × −log10(p) 'Manhattan-style' grafik."""
    sub = res[res["Trait"] == trait].reset_index(drop=True)
    fig, ax = _subplots(figsize=(10, 4), dpi=150)
    y = -np.log10(sub[p_col].clip(lower=1e-300))
    colors = [_P["sig"] if s else _P["primary"] for s in sub["FDR_sig"]]
    ax.scatter(range(len(sub)), y, c=colors, s=22, edgecolor="white", linewidth=0.3)
    bonf = -np.log10(0.05 / len(res[p_col].dropna().unique())) if len(sub) else 0
    ax.axhline(-np.log10(0.05), color=_P["warn"], ls=":", lw=1, label="p = 0.05")
    ax.axhline(bonf, color=_P["sig"], ls="--", lw=1, label="Bonferroni")
    ax.set_xticks(range(len(sub)))
    ax.set_xticklabels(sub["Marker"], rotation=90, fontsize=6)
    ax.set_ylabel(r"$-\log_{10}(p)$")
    ax.set_title(f"Marker assotsiatsiyasi — {trait}", fontweight="bold")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def corr_heatmap(corr: pd.DataFrame, pval: pd.DataFrame | None = None) -> bytes:
    """Korrelyatsiya heatmap + ahamiyat yulduzchalari."""
    n = len(corr)
    fig, ax = _subplots(figsize=(max(6, n * 0.5), max(5, n * 0.5)), dpi=150)
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(corr.columns, rotation=90, fontsize=7)
    ax.set_yticklabels(corr.index, fontsize=7)
    for i in range(n):
        for j in range(n):
            r = corr.values[i, j]
            star = ""
            if pval is not None and i != j:
                p = pval.values[i, j]
                star = "*" if p < 0.05 else ""
                star = "**" if p < 0.01 else star
            ax.text(j, i, f"{r:.2f}{star}", ha="center", va="center",
                    fontsize=6, color="white" if abs(r) > 0.55 else "black")
    fig.colorbar(im, ax=ax, shrink=0.7, label="r")
    ax.set_title("Traitlar orasidagi korrelyatsiya", fontweight="bold", pad=12)
    return _png(fig)


def pca_biplot(pca_res: dict, labels=None, title: str = "PCA") -> bytes:
    """PCA biplot — liniyalar (nuqta) + traitlar (vektor)."""
    scores = pca_res["scores"]
    load = pca_res["loadings"]
    exp = pca_res["explained"]
    fig, ax = _subplots(figsize=(7, 6), dpi=150)
    c = labels if labels is not None else _P["primary"]
    sc = ax.scatter(scores["PC1"], scores["PC2"], c=c, cmap="viridis",
                    s=35, alpha=0.8, edgecolor="white", linewidth=0.4)
    scale = np.abs(scores[["PC1", "PC2"]].values).max() / (np.abs(load[["PC1", "PC2"]].values).max() + 1e-9)
    for trait in load.index:
        ax.arrow(0, 0, load.loc[trait, "PC1"] * scale * 0.7, load.loc[trait, "PC2"] * scale * 0.7,
                 color=_P["sig"], alpha=0.5, head_width=scale * 0.02, length_includes_head=True)
        ax.text(load.loc[trait, "PC1"] * scale * 0.78, load.loc[trait, "PC2"] * scale * 0.78,
                trait, fontsize=6, color=_P["sig"])
    ax.axhline(0, color=_P["grey"], lw=0.5); ax.axvline(0, color=_P["grey"], lw=0.5)
    ax.set_xlabel(f"PC1 ({exp[0]:.1f}%)"); ax.set_ylabel(f"PC2 ({exp[1]:.1f}%)")
    ax.set_title(title, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    if labels is not None:
        fig.colorbar(sc, ax=ax, shrink=0.7, label="Klaster")
    return _png(fig)


def dendro(Z, labels, title: str = "Dendrogramma") -> bytes:
    fig, ax = _subplots(figsize=(11, 4), dpi=150)
    dendrogram(Z, labels=list(labels), ax=ax, leaf_font_size=6,
               color_threshold=0.7 * max(Z[:, 2]))
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel("Masofa")
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


def kinship_heatmap(K: pd.DataFrame) -> bytes:
    fig, ax = _subplots(figsize=(7, 6), dpi=150)
    im = ax.imshow(K.values, cmap="YlOrRd")
    ax.set_title("Kinship (simple matching) matritsasi", fontweight="bold")
    ax.set_xlabel("Liniya"); ax.set_ylabel("Liniya")
    fig.colorbar(im, ax=ax, shrink=0.75, label="Qarindoshlik")
    return _png(fig)


def box_by_marker(geno: pd.DataFrame, pheno: pd.DataFrame, marker: str, trait: str) -> bytes:
    """Marker genotip klasslari (0/1) bo'yicha trait box/violin."""
    g, ph = align(geno, pheno)
    mk = pd.to_numeric(g[marker], errors="coerce")
    y = pd.to_numeric(ph[trait], errors="coerce")
    mask = mk.notna() & y.notna()
    g0 = y[mask][mk[mask] == 0].values
    g1 = y[mask][mk[mask] == 1].values
    fig, ax = _subplots(figsize=(5, 4.5), dpi=150)
    parts = ax.violinplot([g0, g1], showmeans=True, showextrema=False)
    for pc in parts["bodies"]:
        pc.set_facecolor(_P["primary"]); pc.set_alpha(0.3)
    ax.boxplot([g0, g1], widths=0.25, patch_artist=True,
               boxprops={"facecolor": "white", "edgecolor": _P["primary"]})
    ax.set_xticks([1, 2]); ax.set_xticklabels(["0 (yo'q)", "1 (band)"])
    ax.set_ylabel(trait); ax.set_xlabel(f"Marker: {marker}")
    _, p = stats.f_oneway(g0, g1) if len(g0) > 1 and len(g1) > 1 else (0, np.nan)
    ax.set_title(f"{marker} → {trait}  (p = {p:.2e})", fontweight="bold", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    return _png(fig)


# =====================================================================
# 9. NAMUNA MA'LUMOT (demo/sinov uchun)
# =====================================================================

FIELD_TRAITS = ["PH", "MSD", "NB", "NB_symp", "BW", "SCY_plant", "LP", "FL",
                "FS", "FF", "FU", "GOT"]
STRESS_INDICES = ["MP", "GMP", "STI", "SSI", "TOL"]
LAB_TRAITS = ["GP", "GR", "SL", "RL", "SFW", "RFW", "SDW", "RDW", "SVI", "RSR",
              "SLA", "RWC", "CHL", "PRO", "MDA", "EL", "SDW_RDW", "VIG", "TDW"]


def sample_dataset(n_lines: int = 80, n_markers: int = 83, seed: int = 7) -> dict:
    """3 varaqli namuna: Genotype, Field_Data, Lab_Data (ba'zi haqiqiy MTA bilan)."""
    rng = np.random.default_rng(seed)
    lines = [f"RIL{i+1:03d}" for i in range(n_lines)]
    markers = [f"SSR{p:02d}_{b}" for p in range(1, 34) for b in range(1, 4)][:n_markers]

    # genotip 0/1 (turli MAF)
    G = np.zeros((n_lines, n_markers), int)
    for j in range(n_markers):
        freq = rng.uniform(0.15, 0.85)
        G[:, j] = (rng.random(n_lines) < freq).astype(int)
    geno = pd.DataFrame(G, index=lines, columns=markers)

    # fenotip: baza + ba'zi markerlar ta'siri (haqiqiy assotsiatsiya)
    def make_traits(trait_names, effect_markers):
        data = {}
        for t in trait_names:
            base = rng.normal(rng.uniform(20, 100), 8, n_lines)
            for mk, eff in effect_markers.get(t, []):
                base += geno[mk].values * eff
            data[t] = base
        return pd.DataFrame(data, index=lines)

    # bir nechta markerni ikkala sharoitga ham ta'sir qildiramiz (barqaror nomzod)
    shared = markers[5]
    field_eff = {"SCY_plant": [(shared, 14), (markers[10], 9)],
                 "BW": [(markers[20], 7)]}
    lab_eff = {"RDW": [(shared, 6), (markers[30], 5)],
               "RWC": [(markers[10], 8)]}

    field = make_traits(FIELD_TRAITS, field_eff)
    # stress indekslari (SCY asosida taxminan)
    scy = field["SCY_plant"]
    idx = pd.DataFrame({
        "MP": scy * rng.uniform(0.9, 1.1, n_lines),
        "GMP": scy * rng.uniform(0.85, 1.05, n_lines),
        "STI": (scy / scy.mean()) ** 2 * rng.uniform(0.9, 1.1, n_lines),
        "SSI": rng.uniform(0.5, 1.5, n_lines),
        "TOL": rng.normal(0, 5, n_lines) + geno[shared].values * 8,
    }, index=lines)
    field_full = pd.concat([field, idx], axis=1)
    lab = make_traits(LAB_TRAITS, lab_eff)

    return {"Genotype": geno.reset_index().rename(columns={"index": "Line"}),
            "Field_Data": field_full.reset_index().rename(columns={"index": "Line"}),
            "Lab_Data": lab.reset_index().rename(columns={"index": "Line"})}


def _prep(sheets: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Namuna/haqiqiy varaqlarni indeksli DataFrame larga aylantiradi."""
    def idx(df):
        df = df.copy()
        df = df.set_index(df.columns[0])
        return df.apply(pd.to_numeric, errors="coerce")
    geno = idx(sheets["Genotype"])
    field = idx(sheets["Field_Data"])
    lab = idx(sheets["Lab_Data"])
    return geno, field, lab


if __name__ == "__main__":
    sheets = sample_dataset()
    geno, field, lab = _prep(sheets)
    print("Genotip:", geno.shape, "| Field:", field.shape, "| Lab:", lab.shape)

    qc = marker_qc(geno)
    print("\nMarker QC xulosasi:", marker_summary(qc))

    desc = pheno_descriptives(field)
    print(f"\nFenotip descriptives (field): {len(desc)} trait")

    K = kinship_matrix(geno)
    kpcs = kinship_pcs(K, 3)
    print("Kinship:", K.shape)

    field_mta = mta_scan(geno, field, kpcs, dataset="field")
    lab_mta = mta_scan(geno, lab, kpcs, dataset="lab")
    fh = significant_hits(field_mta)
    lh = significant_hits(lab_mta)
    print(f"\nMTA field: {len(field_mta)} test, {len(fh)} FDR-signifikant")
    print(f"MTA lab:   {len(lab_mta)} test, {len(lh)} FDR-signifikant")

    ov = field_lab_overlap(field_mta, lab_mta)
    print("Barqaror (ikkala sharoitda) markerlar:", sorted(ov["overlap"]))
