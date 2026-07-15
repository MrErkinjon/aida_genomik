"""
AIDA - Bioilm moduli
====================
Besh yo'nalish: bioinformatika, genetika, molekulyar biologiya,
populyatsiya statistikasi, genomik tahlillar.

O'rnatish:
    pip install biopython numpy scipy requests

MUHIM: Bu modul hisob-kitob va ma'lumot beradi. TASHXIS QO'YMAYDI.
Klinik qaror har doim shifokor yoki genetik maslahatchi bilan.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
from Bio.Align import PairwiseAligner
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction, molecular_weight
from Bio.SeqUtils.ProtParam import ProteinAnalysis
from scipy import stats

# =====================================================================
# 1. BIOINFORMATIKA — sekvensiya solishtirish va qidiruv
# =====================================================================


def align_sequences(seq1: str, seq2: str, mode: str = "global") -> dict:
    """Ikki sekvensiyani solishtirish (alignment).

    mode: 'global' (Needleman-Wunsch) yoki 'local' (Smith-Waterman)
    """
    aligner = PairwiseAligner()
    aligner.mode = mode
    aligner.match_score = 2
    aligner.mismatch_score = -1
    aligner.open_gap_score = -2
    aligner.extend_gap_score = -0.5

    alignments = aligner.align(seq1.upper(), seq2.upper())
    best = alignments[0]

    a, b = str(best[0]), str(best[1])
    matches = sum(1 for x, y in zip(a, b) if x == y and x != "-")
    aligned_len = sum(1 for x, y in zip(a, b) if x != "-" and y != "-")

    return {
        "score": best.score,
        "identity_percent": 100 * matches / aligned_len if aligned_len else 0,
        "aligned_length": aligned_len,
        "gaps": a.count("-") + b.count("-"),
        "alignment": str(best),
    }


def hamming_distance(seq1: str, seq2: str) -> int:
    """Bir xil uzunlikdagi sekvensiyalar orasidagi farqlar soni."""
    if len(seq1) != len(seq2):
        raise ValueError("Sekvensiyalar uzunligi teng bo'lishi kerak.")
    return sum(1 for a, b in zip(seq1.upper(), seq2.upper()) if a != b)


def k_mer_profile(seq: str, k: int = 3) -> dict:
    """k-mer chastotalari — sekvensiya 'barmoq izi'."""
    s = seq.upper()
    return dict(Counter(s[i : i + k] for i in range(len(s) - k + 1)))


def find_motif(seq: str, motif: str) -> list[int]:
    """Motiv (naqsh) pozitsiyalarini topish. IUPAC kodlarini qo'llab-quvvatlaydi."""
    import re

    iupac = {
        "A": "A", "T": "T", "G": "G", "C": "C",
        "R": "[AG]", "Y": "[CT]", "S": "[GC]", "W": "[AT]",
        "K": "[GT]", "M": "[AC]", "B": "[CGT]", "D": "[AGT]",
        "H": "[ACT]", "V": "[ACG]", "N": "[ATGC]",
    }
    pattern = "".join(iupac.get(c, c) for c in motif.upper())
    return [m.start() for m in re.finditer(f"(?={pattern})", seq.upper())]


# =====================================================================
# 2. MOLEKULYAR BIOLOGIYA — PCR, primer, restriksiya
# =====================================================================


def melting_temperature(primer: str) -> dict:
    """Primer erish harorati (Tm) — PCR uchun kritik.

    Ikki usul: Wallace qoidasi (qisqa) va nearest-neighbor (aniqroq).
    """
    from Bio.SeqUtils import MeltingTemp as mt

    s = Seq(primer.upper())
    return {
        "primer": str(s),
        "length": len(s),
        "gc_percent": gc_fraction(s) * 100,
        "tm_wallace": mt.Tm_Wallace(s),
        "tm_nearest_neighbor": mt.Tm_NN(s),
        "tm_gc": mt.Tm_GC(s),
    }


def check_primer_quality(primer: str) -> dict:
    """Primer sifatini baholash — PCR muvaffaqiyati uchun."""
    s = primer.upper()
    gc = gc_fraction(Seq(s)) * 100
    tm = melting_temperature(s)["tm_nearest_neighbor"]

    issues = []
    if not 18 <= len(s) <= 30:
        issues.append(f"Uzunlik {len(s)} — ideal 18-25 nukleotid")
    if not 40 <= gc <= 60:
        issues.append(f"GC {gc:.0f}% — ideal 40-60%")
    if not 55 <= tm <= 65:
        issues.append(f"Tm {tm:.1f}°C — ideal 55-65°C")
    if s[-1] not in "GC":
        issues.append("Oxiri G yoki C emas — GC-clamp yo'q")
    for base in "ATGC":
        if base * 4 in s:
            issues.append(f"{base} 4 marta ketma-ket takrorlanadi")

    # Self-dimer tekshiruvi (soddalashtirilgan)
    rc = str(Seq(s).reverse_complement())
    for i in range(len(s) - 4):
        if s[i : i + 5] in rc:
            issues.append("Self-dimer xavfi bor")
            break

    return {
        "primer": s,
        "length": len(s),
        "gc_percent": round(gc, 1),
        "tm": round(tm, 1),
        "quality": "yaxshi" if not issues else "muammoli",
        "issues": issues,
    }


RESTRICTION_SITES = {
    "EcoRI": "GAATTC", "BamHI": "GGATCC", "HindIII": "AAGCTT",
    "NotI": "GCGGCCGC", "XhoI": "CTCGAG", "PstI": "CTGCAG",
    "SmaI": "CCCGGG", "KpnI": "GGTACC", "SacI": "GAGCTC",
    "SalI": "GTCGAC", "XbaI": "TCTAGA", "SpeI": "ACTAGT",
}


def find_restriction_sites(seq: str) -> dict:
    """Restriksiya fermentlari kesish joylarini topish — klonlash uchun."""
    s = seq.upper()
    found = {}
    for enzyme, site in RESTRICTION_SITES.items():
        positions = find_motif(s, site)
        if positions:
            found[enzyme] = {"site": site, "positions": positions, "count": len(positions)}
    return found


def analyze_protein(protein_seq: str) -> dict:
    """Oqsil xossalari: molekulyar og'irlik, pI, gidrofoblik, barqarorlik."""
    s = protein_seq.upper().replace("*", "")
    pa = ProteinAnalysis(s)
    return {
        "length_aa": len(s),
        "molecular_weight_kda": round(pa.molecular_weight() / 1000, 2),
        "isoelectric_point": round(pa.isoelectric_point(), 2),
        "gravy": round(pa.gravy(), 3),  # gidrofoblik indeksi
        "instability_index": round(pa.instability_index(), 2),
        "stable": pa.instability_index() < 40,
        "aromaticity": round(pa.aromaticity(), 3),
        "secondary_structure": dict(
            zip(("helix", "turn", "sheet"), [round(x, 3) for x in pa.secondary_structure_fraction()])
        ),
    }


def codon_usage(seq: str) -> dict:
    """Kodon ishlatilishi — ekspressiya optimizatsiyasi uchun."""
    s = seq.upper().replace("U", "T")
    codons = [s[i : i + 3] for i in range(0, len(s) - 2, 3)]
    counts = Counter(codons)
    total = sum(counts.values())
    return {
        "total_codons": total,
        "unique_codons": len(counts),
        "frequencies": {c: round(n / total, 4) for c, n in counts.most_common()},
    }


# =====================================================================
# 3. POPULYATSIYA GENETIKASI
# =====================================================================


@dataclass
class HardyWeinbergResult:
    """Hardy-Weinberg muvozanati testi natijasi."""

    p: float  # allel A chastotasi
    q: float  # allel a chastotasi
    observed: dict
    expected: dict
    chi_square: float
    p_value: float
    in_equilibrium: bool

    def to_speech(self) -> str:
        verdict = (
            "populyatsiya Hardy-Weinberg muvozanatida"
            if self.in_equilibrium
            else "populyatsiya muvozanatdan chetlashgan"
        )
        return (
            f"Allel chastotalari: p {self.p:.3f}, q {self.q:.3f}. "
            f"Xi-kvadrat {self.chi_square:.2f}, p-qiymat {self.p_value:.4f}. "
            f"Demak {verdict}."
        )


def hardy_weinberg(aa: int, ab: int, bb: int) -> HardyWeinbergResult:
    """Hardy-Weinberg muvozanati testi.

    aa, ab, bb — homozigot, geterozigot, homozigot individlar soni.
    """
    n = aa + ab + bb
    if n == 0:
        raise ValueError("Populyatsiya bo'sh.")

    p = (2 * aa + ab) / (2 * n)
    q = 1 - p

    exp = {"AA": n * p**2, "Ab": n * 2 * p * q, "bb": n * q**2}
    obs = {"AA": aa, "Ab": ab, "bb": bb}

    chi2 = sum((obs[k] - exp[k]) ** 2 / exp[k] for k in obs if exp[k] > 0)
    p_val = 1 - stats.chi2.cdf(chi2, df=1)

    return HardyWeinbergResult(
        p=p, q=q, observed=obs,
        expected={k: round(v, 2) for k, v in exp.items()},
        chi_square=chi2, p_value=p_val,
        in_equilibrium=p_val > 0.05,
    )


def allele_frequency(genotypes: list[str]) -> dict:
    """Genotiplar ro'yxatidan allel chastotalarini hisoblash.

    Masalan: ['AA', 'AG', 'GG', 'AG'] -> {'A': 0.5, 'G': 0.5}
    """
    alleles = Counter()
    for gt in genotypes:
        for allele in gt.upper():
            if allele not in ("-", "_"):
                alleles[allele] += 1
    total = sum(alleles.values())
    return {a: round(n / total, 4) for a, n in alleles.most_common()} if total else {}


def heterozygosity(genotypes: list[str]) -> dict:
    """Kuzatilgan va kutilgan geterozigotlik — genetik xilma-xillik o'lchovi."""
    valid = [g.upper() for g in genotypes if len(g) == 2 and "-" not in g]
    if not valid:
        return {}

    ho = sum(1 for g in valid if g[0] != g[1]) / len(valid)
    freqs = allele_frequency(valid)
    he = 1 - sum(f**2 for f in freqs.values())

    return {
        "observed_het": round(ho, 4),
        "expected_het": round(he, 4),
        "inbreeding_coefficient_F": round((he - ho) / he, 4) if he > 0 else 0,
    }


def fst(pop1_freqs: list[float], pop2_freqs: list[float]) -> float:
    """Fst — ikki populyatsiya orasidagi genetik farqlanish (0 dan 1 gacha).

    0 = bir xil, 0.05 dan past = kam farq, 0.15 dan yuqori = katta farq.
    """
    fst_values = []
    for p1, p2 in zip(pop1_freqs, pop2_freqs):
        p_bar = (p1 + p2) / 2
        hs = (2 * p1 * (1 - p1) + 2 * p2 * (1 - p2)) / 2
        ht = 2 * p_bar * (1 - p_bar)
        if ht > 0:
            fst_values.append((ht - hs) / ht)
    return round(float(np.mean(fst_values)), 4) if fst_values else 0.0


def linkage_disequilibrium(haplotypes: list[str]) -> dict:
    """Ikki lokus orasidagi bog'lanish nomuvozanati (LD).

    haplotypes: ['AB', 'Ab', 'aB', 'ab', ...] ko'rinishida.
    """
    n = len(haplotypes)
    if n == 0:
        return {}

    counts = Counter(haplotypes)
    p_a = sum(c for h, c in counts.items() if h[0].isupper()) / n
    p_b = sum(c for h, c in counts.items() if h[1].isupper()) / n
    p_ab = sum(c for h, c in counts.items() if h[0].isupper() and h[1].isupper()) / n

    d = p_ab - p_a * p_b
    d_max = min(p_a * (1 - p_b), (1 - p_a) * p_b) if d > 0 else min(p_a * p_b, (1 - p_a) * (1 - p_b))
    denom = p_a * (1 - p_a) * p_b * (1 - p_b)

    return {
        "D": round(d, 4),
        "D_prime": round(d / d_max, 4) if d_max > 0 else 0,
        "r_squared": round(d**2 / denom, 4) if denom > 0 else 0,
    }


# =====================================================================
# 4. GENETIKA — irsiyat va xavf hisobi
# =====================================================================


def punnett_square(parent1: str, parent2: str) -> dict:
    """Punnett kvadrati — nasl genotiplari ehtimoli.

    parent1, parent2: 'Aa', 'AA', 'aa' ko'rinishida.
    """
    offspring = Counter()
    for a1 in parent1:
        for a2 in parent2:
            gt = "".join(sorted([a1, a2], key=lambda x: (x.lower(), x.islower())))
            offspring[gt] += 1

    total = sum(offspring.values())
    return {
        "cross": f"{parent1} x {parent2}",
        "genotypes": {gt: f"{100*n/total:.0f}%" for gt, n in offspring.most_common()},
    }


def inheritance_risk(pattern: str, parent_status: str) -> dict:
    """Irsiyat modeli bo'yicha nasl xavfi.

    pattern: 'autosomal_recessive', 'autosomal_dominant', 'x_linked_recessive'
    parent_status: 'both_carriers', 'one_affected', 'one_carrier'
    """
    table = {
        ("autosomal_recessive", "both_carriers"): {
            "affected": "25%", "carrier": "50%", "unaffected": "25%",
            "note": "Ikkala ota-ona tashuvchi bo'lsa, har homiladorlikda 25% xavf. Bu har safar qaytadan hisoblanadi.",
        },
        ("autosomal_dominant", "one_affected"): {
            "affected": "50%", "unaffected": "50%",
            "note": "Bitta ota-ona kasal bo'lsa, har bolada 50% xavf. Penetrantlik to'liq bo'lmasligi mumkin.",
        },
        ("x_linked_recessive", "one_carrier"): {
            "affected_sons": "50%", "carrier_daughters": "50%",
            "note": "Ona tashuvchi bo'lsa: o'g'illarning 50% kasal, qizlarning 50% tashuvchi.",
        },
    }
    result = table.get((pattern, parent_status))
    if not result:
        return {"error": "Bu kombinatsiya uchun ma'lumot yo'q."}
    result["disclaimer"] = (
        "Bu nazariy ehtimol. Aniq xavf oilaviy tarix va variantning aniq turiga bog'liq. "
        "Genetik maslahatchi bilan maslahatlashing."
    )
    return result


# =====================================================================
# 5. GENOMIK TAHLIL — GWAS va statistika
# =====================================================================


def gwas_association(
    cases_genotypes: list[str], controls_genotypes: list[str]
) -> dict:
    """Kasallik-variant bog'liqligini tekshirish (assotsiatsiya testi).

    Fisher aniq testi va odds ratio hisoblaydi.
    """
    def count_alleles(gts):
        c = Counter()
        for g in gts:
            for a in g.upper():
                if a not in ("-", "_"):
                    c[a] += 1
        return c

    case_a = count_alleles(cases_genotypes)
    ctrl_a = count_alleles(controls_genotypes)

    alleles = sorted(set(case_a) | set(ctrl_a))
    if len(alleles) != 2:
        return {"error": "Ikki allelli variant kerak."}

    a1, a2 = alleles
    table = [[case_a[a1], case_a[a2]], [ctrl_a[a1], ctrl_a[a2]]]

    odds_ratio, p_value = stats.fisher_exact(table)

    # 95% ishonch oralig'i (Woolf usuli)
    try:
        se = math.sqrt(sum(1 / max(x, 0.5) for row in table for x in row))
        ci = (
            round(math.exp(math.log(odds_ratio) - 1.96 * se), 3),
            round(math.exp(math.log(odds_ratio) + 1.96 * se), 3),
        )
    except (ValueError, ZeroDivisionError):
        ci = (None, None)

    return {
        "allele_1": a1, "allele_2": a2,
        "case_freq": round(case_a[a1] / sum(case_a.values()), 4),
        "control_freq": round(ctrl_a[a1] / sum(ctrl_a.values()), 4),
        "odds_ratio": round(odds_ratio, 3),
        "ci_95": ci,
        "p_value": p_value,
        "significant": p_value < 5e-8,  # GWAS standarti
        "note": "GWAS'da ahamiyatlilik chegarasi 5×10⁻⁸ (ko'p taqqoslash tuzatishi bilan).",
    }


def bonferroni_correction(p_values: list[float]) -> dict:
    """Ko'p taqqoslash tuzatishi — yolg'on ijobiy natijalarni kamaytirish."""
    n = len(p_values)
    threshold = 0.05 / n
    return {
        "tests": n,
        "corrected_threshold": threshold,
        "significant_count": sum(1 for p in p_values if p < threshold),
        "adjusted_p": [min(p * n, 1.0) for p in p_values],
    }


def polygenic_risk_score(variants: dict[str, tuple[int, float]]) -> dict:
    """Poligenik xavf ballari (PRS).

    variants: {'rs123': (dozа 0/1/2, effekt og'irligi), ...}
    """
    score = sum(dosage * weight for dosage, weight in variants.values())
    return {
        "prs": round(score, 4),
        "variants_used": len(variants),
        "interpretation": (
            "PRS — populyatsiyaga nisbatan qiyosiy ko'rsatkich, mutlaq xavf emas. "
            "U faqat o'sha populyatsiya uchun ishlab chiqilgan bo'lsa to'g'ri ishlaydi. "
            "Klinik qaror uchun yolg'iz ishlatilmaydi."
        ),
    }


# =====================================================================
# NAMUNA
# =====================================================================

if __name__ == "__main__":
    print("=== 1. BIOINFORMATIKA: alignment ===")
    r = align_sequences("ATGGCCATTGTAATGGGCCGC", "ATGGCCATTGTTATGGGCCGC")
    print(f"  O'xshashlik: {r['identity_percent']:.1f}%, ball: {r['score']}")

    print("\n=== 2. MOLEKULYAR BIOLOGIYA: primer ===")
    p = check_primer_quality("ATGGCCCTGTGGATGCGCC")
    print(f"  Tm: {p['tm']}°C, GC: {p['gc_percent']}%, sifat: {p['quality']}")
    for issue in p["issues"]:
        print(f"    - {issue}")

    print("\n=== Restriksiya joylari ===")
    sites = find_restriction_sites("GGATCCATGGCCGAATTCTAAGCTTGCG")
    for enz, info in sites.items():
        print(f"  {enz} ({info['site']}): {info['positions']}")

    print("\n=== 3. POPULYATSIYA: Hardy-Weinberg ===")
    hw = hardy_weinberg(aa=320, ab=480, bb=200)
    print(f"  {hw.to_speech()}")

    print("\n=== Geterozigotlik ===")
    h = heterozygosity(["AA", "AG", "GG", "AG", "AA", "AG", "GG", "AG"])
    print(f"  Ho: {h['observed_het']}, He: {h['expected_het']}, F: {h['inbreeding_coefficient_F']}")

    print("\n=== Fst ===")
    print(f"  Fst = {fst([0.3, 0.5, 0.7], [0.35, 0.45, 0.72])}")

    print("\n=== 4. GENETIKA: Punnett ===")
    print(f"  {punnett_square('Aa', 'Aa')['genotypes']}")

    print("\n=== 5. GENOMIK: GWAS ===")
    g = gwas_association(
        cases_genotypes=["AA"] * 60 + ["AG"] * 30 + ["GG"] * 10,
        controls_genotypes=["AA"] * 30 + ["AG"] * 40 + ["GG"] * 30,
    )
    print(f"  OR: {g['odds_ratio']} (95% CI {g['ci_95']}), p = {g['p_value']:.2e}")
    print(f"  GWAS chegarasidan o'tdimi: {g['significant']}")
