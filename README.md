# AIDA — Genomika studiyasi 🧬

O'zbek tilidagi genetika/bioinformatika desktop ilovasi. Sekvensiya tahlili,
populyatsiya genetikasi, GWAS, Claude orqali tushuntirish va professional
hisobot eksporti — bitta native macOS ilovada.

> ⚠️ Faqat ma'lumot uchun. Tashxis qo'ymaydi. Klinik qaror shifokor yoki
> genetik maslahatchi bilan.

---

## Tez ishga tushirish (dasturchi rejimi)

```bash
./run.sh
```

Birinchi ishga tushirishda `.venv` yaratiladi va kutubxonalar o'rnatiladi.
Keyin `app/main.py` ochiladi.

Qo'lda:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.main
```

## Native `.app` qurish

```bash
.venv/bin/python packaging/make_icon.py     # ikona (bir marta)
.venv/bin/pyinstaller AIDA.spec --noconfirm  # -> dist/AIDA.app
```

Natijani `/Applications` ga ko'chiring va ikki marta bosib oching.
Bundle ID: `uz.erkinjon.medical`.

---

## Tuzilma

| Yo'l | Vazifa |
|------|--------|
| `aida_bioscience.py` | Hisob yadrosi: alignment, primer, Hardy-Weinberg, GWAS, PRS |
| `aida_genomics.py` | DNK tahlili, fayl o'qish (VCF/23andMe/FASTA), Claude izohi |
| `aida_export.py` | 11 grafik + Excel/PDF/Word eksport |
| `aida_assoc.py` | SSR marker-trait assotsiatsiya: QC/PIC, kinship, MTA (GLM+MLM), FDR |
| `aida_anova.py` | RIL bir tomonlama ANOVA, LSD, CLD harflari, tasnif, Excel/Word |
| `app/theme.py` | Dizayn tizimi (dark tema, QSS) |
| `app/widgets.py` | Card, StatTile, ChartView va boshqalar |
| `app/workers.py` | Fon oqimlari (UI muzlamaydi) |
| `app/main.py` | Asosiy oyna + sidebar navigatsiya |
| `app/pages/` | 5 modul sahifasi |

## Klaviatura yorliqlari

| Yorliq | Amal |
|--------|------|
| ⌘1 … ⌘5 | Sahifalar orasida almashish |
| ⌘W | Oynani yopish |

## Sahifalar

1. **Sekvensiya** — DNK/RNK tahlili, oqsil, ORF, restriksiya, primer sifati
2. **Populyatsiya** — Hardy-Weinberg, geterozigotlik, Punnett, irsiyat, Fst/LD
3. **Genomika** — GWAS assotsiatsiya, Manhattan/QQ, Bonferroni, PRS
4. **Assotsiatsiya** — SSR marker-trait xaritalash: marker QC (MAF/PIC/He),
   fenotip descriptives + korrelyatsiya, PCA/dendrogramma/kinship, single-marker
   MTA (GLM + kinship-korreksiyali MLM, FDR/Bonferroni), dala↔lab mosligi
5. **ANOVA / RPC** — 80 RIL uchun har trait bo'yicha bir tomonlama ANOVA, LSD,
   ahamiyat harflari (a/b/c), tolerantlik tasnifi, Excel + Word eksport
6. **Tushuntirish** — Claude izohi, fayl yuklash, variant qidirish
7. **Hisobot** — Excel/PDF/Word eksport

Modul 4–5 ni terminalsiz sinash uchun har sahifada **"Namuna ma'lumot"** tugmasi
bor (RIL tuzilmasiga o'xshash sun'iy ma'lumot yaratadi).

## Sozlash

- **Claude tushuntirish** uchun: `export ANTHROPIC_API_KEY=...`
- **Variant qidirish** internet talab qiladi (myvariant.info).
