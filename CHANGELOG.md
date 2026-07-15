# O'zgarishlar tarixi (Changelog)

Barcha muhim o'zgarishlar shu faylda qayd etiladi.
Format [Keep a Changelog](https://keepachangelog.com/) ga, versiyalash
[SemVer](https://semver.org/) ga asoslanadi.

Ilova ichidagi **Yangilanishlar** oynasi GitHub Releases'dan avtomatik
o'qiydi — release yaratganda uning izohlari (notes) shu yerdagi yozuvga
mos bo'lsin.

## [Chiqarilmagan]
### Qo'shildi
- (keyingi o'zgarishlar shu yerga)

## [1.0.0] — 2026-07-15
### Qo'shildi
- 7 modulli PySide6 desktop ilovasi: Sekvensiya, Populyatsiya, Genomika
  (GWAS), Assotsiativ xaritalash, ANOVA/RPC, Claude tushuntirish, Hisobot.
- SSR marker–trait assotsiatsiya: QC (MAF/PIC/He), kinship, single-marker
  MTA (GLM + kinship-korreksiyali MLM), FDR/Bonferroni, dala↔lab mosligi.
- RIL bir tomonlama ANOVA: LSD, ahamiyat harflari (CLD), tolerantlik tasnifi,
  Excel + Word ("Results & Discussion") eksporti.
- Grafiklarni boshqarish: kattalashtirish (zoom/pan), PNG saqlash, nusxalash.
- Avto-update tekshiruvi va Yangilanishlar oynasi.
- Cross-platform PyInstaller build (macOS/Windows/Linux), GitHub Actions,
  issue shablonlari (bug / feedback).

### Ishlash
- Barcha og'ir amallar (fayl o'qish, hisoblash, grafik) worker oqimlarida —
  interfeys qotmaydi.
- Thread-xavfsiz matplotlib (OO Figure); MTA scan numpy bilan ~17× tezlashdi.

### Tuzatildi
- `.gitignore` naqshi asosiy `aida_anova.py` modulini chiqarib yuborayotgan edi.
- `aida_genomics.py` da noto'g'ri Claude model ID (`claude-sonnet-4-6`).

[1.0.0]: https://github.com/MrErkinjon/aida_genomik/releases/tag/v1.0.0
