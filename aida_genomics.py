"""
AIDA - Genomika moduli
======================
DNK/RNK tahlili: sekvensiya vositalari, genetik test fayllarini o'qish,
va natijalarni sodda tilda tushuntirish.

O'rnatish:
    pip install biopython anthropic requests

MUHIM: Bu modul TASHXIS QO'YMAYDI. U faqat ma'lumot beradi va
tushuntiradi. Har qanday klinik qaror shifokor yoki genetik
maslahatchi (genetic counselor) bilan qabul qilinadi.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterator

import requests
from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction, molecular_weight

# =====================================================================
# 1-QISM: SEKVENSIYA VOSITALARI (lokal, internetsiz ishlaydi)
# =====================================================================

DNA_ALPHABET = set("ATGCN")
RNA_ALPHABET = set("AUGCN")


def clean_sequence(raw: str) -> str:
    """Sekvensiyani tozalash: probel, raqam, yangi qatorni olib tashlash."""
    return re.sub(r"[^A-Za-z]", "", raw).upper()


def detect_type(seq: str) -> str:
    """DNK, RNK yoki oqsil ekanini aniqlash."""
    s = set(clean_sequence(seq))
    if not s:
        return "bo'sh"
    if s <= DNA_ALPHABET:
        return "DNK"
    if s <= RNA_ALPHABET:
        return "RNK"
    return "oqsil (yoki noma'lum)"


@dataclass
class SequenceReport:
    """Sekvensiya tahlili natijasi."""

    seq_type: str
    length: int
    gc_percent: float
    base_counts: dict
    reverse_complement: str
    rna: str
    protein: str
    mol_weight_kda: float | None

    def to_speech(self) -> str:
        """Ovozda aytish uchun qisqa xulosa (markdown yo'q)."""
        return (
            f"Bu {self.seq_type} sekvensiyasi, uzunligi {self.length} nukleotid. "
            f"GC tarkibi {self.gc_percent:.1f} foiz. "
            f"Translyatsiya natijasida {len(self.protein)} aminokislotali oqsil hosil bo'ladi."
        )


def analyze_sequence(raw: str) -> SequenceReport:
    """DNK yoki RNK sekvensiyasini to'liq tahlil qilish."""
    s = clean_sequence(raw)
    if not s:
        raise ValueError("Sekvensiya bo'sh.")

    seq_type = detect_type(s)
    if seq_type not in ("DNK", "RNK"):
        raise ValueError(f"Bu DNK yoki RNK emas: {seq_type}")

    bio = Seq(s)
    # RNK bo'lsa, ichki hisoblar uchun DNK'ga qaytaramiz
    dna = Seq(s.replace("U", "T")) if seq_type == "RNK" else bio

    protein = str(dna.translate(to_stop=False))

    try:
        mw = molecular_weight(dna, seq_type="DNA") / 1000
    except Exception:
        mw = None

    return SequenceReport(
        seq_type=seq_type,
        length=len(s),
        gc_percent=gc_fraction(dna) * 100,
        base_counts=dict(Counter(s)),
        reverse_complement=str(dna.reverse_complement()),
        rna=str(dna.transcribe()),
        protein=protein,
        mol_weight_kda=mw,
    )


def find_orfs(raw: str, min_length_aa: int = 30) -> list[dict]:
    """Ochiq o'qish ramkalarini (ORF) topish — potensial genlar.

    Har 6 ramkada (3 to'g'ri + 3 teskari) ATG'dan stop-kodongacha qidiradi.
    """
    dna = Seq(clean_sequence(raw).replace("U", "T"))
    orfs = []

    for strand, nuc in [(1, dna), (-1, dna.reverse_complement())]:
        for frame in range(3):
            trimmed = nuc[frame : len(nuc) - ((len(nuc) - frame) % 3)]
            protein = str(trimmed.translate())
            for match in re.finditer(r"M[^*]*\*?", protein):
                peptide = match.group().rstrip("*")
                if len(peptide) >= min_length_aa:
                    start_nt = frame + match.start() * 3
                    orfs.append(
                        {
                            "strand": "+" if strand == 1 else "-",
                            "frame": frame + 1,
                            "start": start_nt,
                            "length_aa": len(peptide),
                            "protein": peptide,
                        }
                    )

    return sorted(orfs, key=lambda o: o["length_aa"], reverse=True)


def read_fasta(path: str) -> Iterator[tuple[str, str]]:
    """FASTA faylini o'qish. Har bir yozuv uchun (sarlavha, sekvensiya)."""
    header, chunks = None, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(chunks)
                header, chunks = line[1:], []
            elif line:
                chunks.append(line)
    if header is not None:
        yield header, "".join(chunks)


# =====================================================================
# 2-QISM: GENETIK TEST FAYLLARINI O'QISH
# =====================================================================


@dataclass
class Variant:
    """Bitta genetik variant (SNP)."""

    rsid: str
    chromosome: str
    position: int
    genotype: str


def read_23andme(path: str) -> list[Variant]:
    """23andMe / AncestryDNA raw data faylini o'qish.

    Format: rsid <tab> chromosome <tab> position <tab> genotype
    """
    variants = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            rsid, chrom, pos, genotype = parts[0], parts[1], parts[2], parts[3]
            if genotype in ("--", "__"):  # o'qilmagan
                continue
            try:
                variants.append(Variant(rsid, chrom, int(pos), genotype))
            except ValueError:
                continue
    return variants


def read_vcf(path: str) -> list[Variant]:
    """VCF (Variant Call Format) faylini o'qish — klinik panellar shu formatda."""
    variants = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            chrom, pos, vid, ref, alt = cols[0], cols[1], cols[2], cols[3], cols[4]
            genotype = f"{ref}>{alt}"
            if len(cols) >= 10:  # namuna ustuni bor
                gt = cols[9].split(":")[0]
                genotype = f"{ref}>{alt} ({gt})"
            try:
                variants.append(Variant(vid, chrom, int(pos), genotype))
            except ValueError:
                continue
    return variants


def lookup_variant(rsid: str) -> dict | None:
    """myvariant.info orqali variant haqida ma'lumot olish.

    Qaytaradi: gen nomi, klinik ahamiyati (ClinVar), populyatsiyadagi chastota.
    Internet talab qiladi.
    """
    if not rsid.startswith("rs"):
        return None
    try:
        r = requests.get(
            f"https://myvariant.info/v1/query",
            params={"q": rsid, "fields": "dbsnp.gene,clinvar,gnomad_genome.af"},
            timeout=10,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        if not hits:
            return None
        hit = hits[0]
        clinvar = hit.get("clinvar", {})
        rcv = clinvar.get("rcv")
        if isinstance(rcv, list):
            rcv = rcv[0] if rcv else {}
        return {
            "rsid": rsid,
            "gene": (hit.get("dbsnp", {}).get("gene", {}) or {}).get("symbol"),
            "significance": (rcv or {}).get("clinical_significance"),
            "condition": (rcv or {}).get("conditions", {}).get("name"),
            "frequency": (hit.get("gnomad_genome", {}) or {}).get("af", {}),
        }
    except Exception as e:
        print(f"Variant qidiruvida xato: {e}")
        return None


# =====================================================================
# 3-QISM: CLAUDE ORQALI TUSHUNTIRISH
# =====================================================================

GENOMICS_SYSTEM_PROMPT = """Sen AIDA'san — foydalanuvchining shaxsiy yordamchisi.
Hozir sen genetik ma'lumotni tushuntirish rejimidasan.

QOIDALAR (qattiq, buzilmaydi):
1. Sen TASHXIS QO'YMAYSAN. "Sizda X kasalligi bor" yoki "sizda X kasalligi
   rivojlanadi" deb hech qachon aytma.
2. Genetika ehtimollik haqida, aniqlik haqida emas. Variant xavfni oshirsa,
   buni "xavf biroz yuqori" deb ayt, "kasal bo'lasiz" deb emas. Ko'p genlar,
   turmush tarzi va atrof-muhit birgalikda ta'sir qilishini eslat.
3. Genetik natijalar bo'yicha har doim genetik maslahatchiga (genetic
   counselor) yoki shifokorga murojaat qilishni tavsiya et. Buni tabiiy
   qilib ayt, robotik takrorlamasdan.
4. Iste'molchi testlari (23andMe va shunga o'xshash) klinik tashxis uchun
   yaroqli emas — ular skrining vositasi. Muhim natija chiqsa, u klinik
   laboratoriyada tasdiqlanishi kerakligini ayt.
5. Bilmasang, bilmasligingni ayt. Genetik variant haqida taxmin qilib
   ishonchli ohangda gapirma.
6. Foydalanuvchi qo'rqib ketgan bo'lsa, avval xotirjamlantir, keyin
   ma'lumot ber.

USLUB:
- O'zbek tilida, sodda tilda gapir. Termin ishlatsang, darhol izohla.
- Javobing ovozga aylantiriladi: markdown, yulduzcha, ro'yxat ishlatma.
  Faqat oddiy gaplashish matni. 2-5 jumla.
- Foydalanuvchi batafsil so'rasa, uzunroq tushuntir."""


def explain_with_claude(question: str, data_context: str = "") -> str:
    """Genetik ma'lumotni Claude orqali tushuntirish."""
    try:
        import anthropic
    except ImportError:
        return "Anthropic kutubxonasi o'rnatilmagan. pip install anthropic"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "ANTHROPIC_API_KEY o'rnatilmagan."

    client = anthropic.Anthropic(api_key=api_key)

    content = question
    if data_context:
        content = f"Quyidagi genetik ma'lumot berilgan:\n\n{data_context}\n\nSavol: {question}"

    try:
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1000,
            system=GENOMICS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")
    except Exception as e:
        return f"Claude bilan bog'lanishda xato: {e}"


def explain_pdf_report(pdf_path: str, question: str = "Bu hisobotni tushuntirib bering.") -> str:
    """Genetik test PDF hisobotini Claude'ga yuborib tushuntirish."""
    import base64

    try:
        import anthropic
    except ImportError:
        return "Anthropic kutubxonasi o'rnatilmagan."

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "ANTHROPIC_API_KEY o'rnatilmagan."

    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.standard_b64encode(f.read()).decode()

    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1500,
            system=GENOMICS_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {"type": "text", "text": question},
                    ],
                }
            ],
        )
        return "".join(b.text for b in msg.content if b.type == "text")
    except Exception as e:
        return f"Xato: {e}"


# =====================================================================
# 4-QISM: AIDA UCHUN YUQORI DARAJALI FUNKSIYALAR
# =====================================================================


def handle_sequence_command(raw_seq: str) -> str:
    """Ovozli buyruq uchun: sekvensiyani tahlil qilib, ovozli xulosa qaytarish."""
    try:
        report = analyze_sequence(raw_seq)
        return report.to_speech()
    except ValueError as e:
        return f"Sekvensiyani o'qiy olmadim. {e}"


def handle_genetic_file(path: str) -> str:
    """Genetik fayl yuklanganda umumiy xulosa berish."""
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        return explain_pdf_report(path)

    if ext == ".vcf":
        variants = read_vcf(path)
    elif ext in (".txt", ".csv", ".tsv"):
        variants = read_23andme(path)
    elif ext in (".fasta", ".fa", ".fna"):
        records = list(read_fasta(path))
        if not records:
            return "Faylda sekvensiya topilmadi."
        header, seq = records[0]
        report = analyze_sequence(seq)
        return f"Faylda {len(records)} ta sekvensiya bor. Birinchisi: {report.to_speech()}"
    else:
        return "Bu fayl formatini bilmayman. FASTA, VCF, 23andMe raw data yoki PDF yuboring."

    if not variants:
        return "Faylda variant topilmadi."

    chroms = len({v.chromosome for v in variants})
    return (
        f"Faylda {len(variants):,} ta genetik variant bor, {chroms} ta xromosomada. "
        f"Qaysi variant yoki gen haqida bilmoqchisiz?"
    )


# =====================================================================
# NAMUNA ISHLATISH
# =====================================================================

if __name__ == "__main__":
    # Namuna: insulin genining bir qismi
    demo = "ATGGCCCTGTGGATGCGCCTCCTGCCCCTGCTGGCGCTGCTGGCCCTCTGGGGACCTGACCCAGCC"

    print("=== SEKVENSIYA TAHLILI ===")
    rep = analyze_sequence(demo)
    print(f"Turi:            {rep.seq_type}")
    print(f"Uzunlik:         {rep.length} nt")
    print(f"GC tarkibi:      {rep.gc_percent:.1f}%")
    print(f"Nukleotidlar:    {rep.base_counts}")
    print(f"RNK:             {rep.rna}")
    print(f"Oqsil:           {rep.protein}")
    print(f"Teskari komp.:   {rep.reverse_complement}")
    print(f"\nOvozli xulosa:  {rep.to_speech()}")

    print("\n=== ORF QIDIRUV ===")
    for orf in find_orfs(demo, min_length_aa=5)[:3]:
        print(f"  {orf['strand']} ramka {orf['frame']}, {orf['length_aa']} aa: {orf['protein']}")
