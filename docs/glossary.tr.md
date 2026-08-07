---
title: Sözlük ve dış kaynaklar
eyebrow: Başvuru
subtitle: Çok alanlı ve çok dilli sözlük kayıt defteri nasıl çalışır. Dosya yerleşimi, proje düzeyinde değiştirmeler, ayrım, çözümleme algoritması.
date: 2026-05-18
order: 30
summary: Çok alanlı sözlük mimarisi ve nasıl genişletileceği.
---

> [!TLDR]
> Sözlük ve dış kaynak kayıtları _oku/glossary/ ve _oku/extrefs/ altında alan başına ayrı dosyalarda durur. Her projenin kit.json dosyası bu alanların bir alt kümesini öncelik sırasıyla etkinleştirir ve yerel değiştirmeler ekleyebilir. Çözümleme etkin alanları sırayla gezer, yeğlenen diller boyunca geriye düşer, bilinmeyenleri ileri uyumluluk uyarı göstergesiyle görünür kılar.
>
> - Bir sayfa, kaydı markdown bağlantısıyla anar — sözlük terimi için [ACID](#g/ACID), dış kaynak için [Pagefind](#x/Pagefind).
> - Alan başına dosya — veri platformlarındaki ACID ile kimyadaki ACID ayrı, adhd alanındaki RSD ile telsizdeki RSD ayrı.
> - Kayıt başına çok dilli değişkeler — { "en": {...}, "tr": {...} }. Asıl bağlantı dile göre değişebilir.
> - Projenin kit.json dosyası etkin alanları, yeğlenen dili ve projeye özgü kayıtları bildirir. Çakışmada yerel kayıt her zaman kazanır.
> - Bilinmeyen terimler ileri uyumluluk uyarı göstergesinde belirir; kaydı projenin kit.json dosyasına ekleyin ya da merkezî dosyaya gönderin.

## Dosya yerleşimi {#layout}

Merkezî sözlükler kitle birlikte gelir; projeler bunları kit.json üzerinden ya da kendi alan dosyalarını ekleyerek genişletir.

```text
oku/                          # the kit repo
├── glossary/
│   ├── data-platforms.json
│   ├── web.json
│   ├── ai-llm.json
│   ├── adhd.json          (structural stub — populate as needed)
│   ├── doc-tooling.json   (structural stub)
│   ├── hadith.json        (structural stub)
│   └── voice.json         (structural stub)
├── extrefs/
│   ├── data-platforms.json
│   ├── doc-tooling.json
│   ├── web.json           (structural stub)
│   └── ai-llm.json        (structural stub)
└── ...

your-project/
└── docs/
    ├── _oku -> /path/to/oku   # symlink
    ├── kit.json                    # active domains + overrides
    ├── page-a.html / page-a.md
    └── ...

```

## Kayıt biçimi {#entry-shape}

Her kayıt, dil → { def, link } eşlemesidir. def alanı satır içi HTML'i (strong, em, br, code) destekler, çünkü balonun gövdesi olarak işlenir. Güven sınırı chrome.js içinde belgelenmiştir — yalnızca kitin denetimindeki dosyalar.

```json
// _oku/glossary/data-platforms.json
{
  "$schema": "https://raw.githubusercontent.com/mmdemirbas/html-doc/main/kit/schema/glossary.schema.json",
  "domain": "data-platforms",
  "version": 1,
  "entries": {
    "ACID": {
      "en": {
        "def": "<strong>Atomicity, consistency, isolation, durability.</strong> Transaction guarantees.",
        "link": "https://en.wikipedia.org/wiki/ACID"
      },
      "tr": {
        "def": "Veritabanı işlemlerinde atomiklik, tutarlılık, izolasyon, dayanıklılık garantileri."
      }
    }
  }
}
```

> [!NEUTRAL] Dış kaynaklar aynı biçimi kullanır
> _oku/extrefs/<domain>.json aynı yapıdadır — her kaydın name, summary ve link taşıyan dil değişkeleri vardır. Aynı çözümleme algoritması, ayrı kayıt defteri.

## Proje yapılandırması — kit.json {#project-config}

Her projenin docs/kit.json dosyası hangi alanların hangi öncelik sırasıyla etkin olduğunu, yeğlenen dili ve geri düşme zincirini, ayrıca yerel eklemeleri ya da değiştirmeleri bildirir.

```json
// docs/kit.json — Iceberg-team project
{
  "name": "Spark+Iceberg notes",
  "domains": ["data-platforms", "web", "ai-llm"],
  "lang": "en",
  "lang_fallback": ["en"],
  "glossary": {
    "data-platforms": {
      "OurInternalTerm": {
        "en": { "def": "Defined in this project only." }
      }
    }
  }
}
```

```json
// docs/kit.json — personal-notes project in Turkish
{
  "name": "Notlar",
  "domains": ["adhd", "hadith", "voice"],
  "lang": "tr",
  "lang_fallback": ["en"]
}
```

> [!TIP] Çakışmada yerel kayıt her zaman kazanır
> Aynı terim hem `kit.json` içindeki `glossary["data-platforms"]` altında hem de merkezî `_oku/glossary/data-platforms.json` dosyasında geçtiğinde projedeki sürüm kullanılır. Birleştirme merkezî dosya yüklendikten sonra yapıldığından, sonradan gelen bir kayıt defteri isteği proje değiştirmesini sessizce silmez.

## Bir kaydı sayfadan anmak {#usage}

Markdown sayfası, kayıt defterindeki bir girdiyi, href'i kit önekiyle başlayan sıradan bir bağlantıyla anar: sözlük için `#g/`, dış kaynaklar için `#x/`. Etiket görünen metindir, önekten sonraki kimlik ise kayıt anahtarıdır.

```text
Tanım kartı için [ACID](#g/ACID) üzerine gelin.
[Pagefind](#x/Pagefind) ile çalışır — kaynağı açmak için karta tıklayın.
```

`renderLink` bunları `<glossary-term term="ACID">` ve `<ext-ref name="Pagefind">` ögelerine çevirir. Sonrasındaki her şey — çözümleme, ipucu balonu, bilinmeyen girdi uyarısı — ortaktır; iki önek yalnızca hangi kayıt defterinde arandığıyla ayrışır.

JSON sayfaları aynı anmayı, bir paragrafın `content` dizisi içinde satır içi nesne olarak taşır:

```json
{ "kind": "paragraph", "content": [
  "Tanım kartı için ",
  { "kind": "glossary-term", "term": "ACID", "text": "ACID" },
  " üzerine gelin."
] }
```

v1 uyarlayıcısı bu nesneyi, renderer sayfayı gezmeden önce `[ACID](#g/ACID)` hâline getirir; böylece iki biçim de aynı ögeye varır. Dış kaynak karşılığı `{ "kind": "ext-ref", "name": "Pagefind" }` şeklindedir.

## Ayrım — aynı terim, farklı alanlar {#disambiguation}

İki etkin alan aynı terimi tanımladığında varsayılan davranış "eşleşen ilk alan kazanır"dır ve bağlantı biçimiyle yapılan anma da bunu ister. Tek bir anmayı nitelemek için öge üzerinde iki öznitelik vardır: `in` aramayı tek bir alanla sınırlar, `lang` ise o örnek için projenin yeğlediği dili geçersiz kılar — varsayılanı Türkçe olan bir projede tek bir terimin İngilizce kaynağa dayanması gerektiğinde işe yarar.

Bağlantı biçimi yalnızca kimliği taşır; bu yüzden nitelenmiş bir anma, ögenin kendisini bir HTML adacığında yazar:

```text
<p>Aynı sözcüğün iki anlamı:
<glossary-term term="ACID" in="data-platforms">ACID</glossary-term> ve
<glossary-term term="ACID" in="chemistry">ACID</glossary-term>.</p>
```

`in` özniteliği alan sırasını yener — projenin domains listesinde ilk sırada olmayan bir alana da ulaşır.

## Çözümleme algoritması {#resolution}

chrome.js içinde __okuKit.resolveGlossary ve resolveExtRef olarak gerçeklenmiştir.

```oku-step-flow
{"steps":[{"t":"Alan seçimi","b":"in özniteliği verilmişse arama yalnızca o alanla sınırlanır. Verilmemişse projenin domains dizisi bildirilen sırayla gezilir."},{"t":"Alan içi arama","b":"Her aday alan için önce projeye özgü değiştirmelere, sonra merkezî _oku/glossary/<domain>.json dosyasına bakılır. İlk eşleşme kazanır."},{"t":"Dil seçimi","b":"Önce yeğlenen dil denenir (lang özniteliğinden ya da kit.json'daki lang alanından). Yoksa kit.json'daki lang_fallback listesi gezilir. Yine yoksa mevcut ilk dil kullanılır ve data-lang-shown imi konur; böylece balon gerçekte hangi dili gösterdiğini bildirir."},{"t":"Bilinmeyen — uyarı çıkar","b":"Hiçbir yerde kayıt bulunamazsa unknown-glossary-term (ya da unknown-ext-ref) uyarı olayı yayılır. İleri uyumluluk göstergesi bunu sayar; öğe, kehribar noktalı biçimlendirmeyle .unknown sınıfını alır."}]}
```

## Yeni kayıt ekleme {#extending}

İki yol var — hızlı ilerlemek için projeye özgü kayıt, terim genelleştiğinde merkezî bir katkı.

```oku-compare-grid
{"cards":[{"t":"Önce projeye özgü","b":"Projenizin docs/kit.json dosyasında glossary[<domain>][<term>] altına ekleyin. Anında etkili olur. Kite hiçbir katkı göndermeniz gerekmez. Projeye özgü terimler ve hızlı denemeler için uygundur.","verdict":"good"},{"t":"Merkeze taşıyın","b":"Bir terim genelleştiğinde (iki üç projede kullanıldığında ya da açıkça o alana ait olduğunda) _oku/glossary/<domain>.json dosyasına ekleyin. Merkezî kayıt yerine oturunca projedeki kopyayı silin.","verdict":"neutral"}]}
```

> [!SUCCESS] İleri uyumluluk uyarısı bilinmeyenleri görünür kılar
> Yapay zekâ, etkin alanların hiçbirinde bulunmayan bir terim ürettiğinde uyarı göstergesi "unknown-glossary-term" koduyla yanar. Eksik kaydın adını görmek için tıklayın. Bir eklemenin geciktiğini söyleyen hızlı bir geri bildirim.

## Kitle gelen başlangıç içeriği {#starter}

Kitle birlikte yedi sözlük alanı gelir. Üçü onar kayıtla dolu gelir; dördü doldurulmayı bekleyen boş yapı taslaklarıdır.

```oku-compare-grid
{"cards":[{"t":"Dolu — her birinde 10 kayıt","b":"- data-platforms — ACID, MVCC, Iceberg, Spark, Flink, Paimon, Catalog, Snapshot, Compaction, Time travel (en sık kullanılanlarda Türkçe karşılıklarıyla)\n- web — Custom Elements, Shadow DOM, FOUC, Viewport, Visual Viewport, prefers-color-scheme, localStorage, History API, IntersectionObserver, CSS değişkeni\n- ai-llm — RAG, Tokenization, Prompt cache, Context window, Embedding, Vector DB, Function calling, Hallucination, Few-shot, Top-k / Top-p","verdict":"in"},{"t":"Yapı taslakları — henüz kayıt yok","b":"- adhd — RSD, aşırı odaklanma, yürütücü işlev bozukluğu gibi kayıtlarla doldurun.\n- doc-tooling — kitin kendi söz dağarcığıyla doldurun.\n- hadith — isnad, metin, sahih, zayıf gibi kayıtlarla doldurun.\n- voice — sesbirim, bürün, formant gibi kayıtlarla doldurun.\n- Yeni alan eklemek için glossary/ dizinine bir <domain>.json dosyası bırakın ve projenizin kit.json dosyasında listeleyin","verdict":"out"}]}
```

Dış kaynaklar aynı biçimle dört alan getirir: `data-platforms` (7 kayıt) ve `doc-tooling` (5 kayıt) içerik taşır; `web` ve `ai-llm` boş taslaktır.
