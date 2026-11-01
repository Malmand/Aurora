# Reference values transcribed from documents

Templates, not data. Each CSV is filled by hand from the named document, with the
table or page in the last column. Empty cells mean "not yet transcribed". The
validation report skips them and says so. Sources: see `../SOURCES.md`
(PAGASA_BASCO, TSAI2020, CASTRO2022). Status on 2026-11-02:

- `pagasa_basco_normals_1991_2020.csv`: **filled** from the PAGASA PDF (text read via web fetch). The PDF content is headed **2001-2020** normals although its URL says 1991-2020; the file name is kept so the code does not change. Station: Basco, 20.428 N, 121.971 E, 167 m.
- `tsai2020_solar.csv`: **left empty on purpose.** Tsai et al. give the monthly GHI only as a chart (Figure 4), so it cannot be transcribed without digitising. The text gives annual GHI 1,876 kWh/m2/yr (about 5.14 kWh/m2/day), monthly range 3.31 (Dec) to 6.41 (Apr) kWh/m2/day. Their site is **Batan Island (Basco)**, not Itbayat, about 45 km away.
- `castro2022_itbayat.csv`: still empty. The Mendeley file list could not be downloaded.
