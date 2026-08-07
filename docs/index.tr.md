---
title: oku
eyebrow: Belgeleme kiti · oku
subtitle: Markdown sayfalarını tarayıcıda işler. Tek kaynaklı içerik, yazım için derleme adımı yok, istediğinizde tam metin aramalı çok sayfalı bir site.
order: 1
summary: Kitin ne olduğu, nasıl düzenlendiği, belgelerin nerede durduğu.
---

> [!TLDR]
> Sayfalar Markdown ile yazılır. Tarayıcı bunları Custom Elements üzerinden işler; okumak için derleme adımı gerekmez. oku build komutu ya Pagefind aramalı çok sayfalı bir site ya da çevrimdışı okuma için tek dosyalık bağımsız bir çıktı üretir.
>
> - Kaynak: <name>.md — GitHub lehçesi markdown, kitin denetleyicisinin reddettiği kısa bir yapı listesi dışında. Sayfa-JSON kaynakları bu biçimden eskidir ve işlenmeye devam eder.
> - Çalışma zamanı: chrome.js + renderer.js bir _oku sembolik bağından yüklenir. Kopya yok, sürüm kayması yok.
> - Yapı taşları: callout, kpi-grid, table, compare-grid, step-flow, chart, diagram, live-snippet, annotated-code, sözlük balonları, kaynak kartları.
> - Çıktı: dist/site/ (çok sayfalı + Pagefind) ve dist/standalone/ (e-posta ya da arşiv için sayfa JSON'u gömülü tek dosya).

## Belgeler {#docs}

Bunun yanında dokuz sayfa daha var. Kartlar doğrudan her birine bağlanır — Başvuru temel yapı taşlarını anlatır; Grafikler / Tablolar / Şemalar ağır olanları ayrı ayrı ele alır; Sözlük / Mimari / CLI / Biçim karşılaştırması daha derine iner.

```oku-step-flow
{"ordered":false,"steps":[{"t":"Başvuru","b":"Proje kurulumu, sayfa anatomisi, Markdown kaynakları, metin / vurgu / yapılandırılmış yerleşim taşları, sayfa başına üstveri, derleme çıktıları.","meta":"buradan başlayın · metin, yerleşim, satır içi","href":"reference.html"},{"t":"Tablolar","b":"table yapı taşı — düz satırlar, gruplanmış satırlar, etiket süzgeçleri, pano / kanban görünümü, yapışkan başlıklar, sürükleyerek genişletilen sütunlar, öntanımlı olarak sözcük kaydırma.","meta":"düz · gruplu · etiketli · pano","href":"tables.html"},{"t":"Grafikler","b":"Her grafik türü, küçük ve canlı bir örnekle, ne göstermek istediğinize göre gruplanmış (karşılaştırma · eğilim · dağılım · bileşim · ilişki · hiyerarşi · akış · konum); üstüne zengin imleç bilgisi, tıklayarak sabitleme, tam ekranda kaydırma ve yakınlaştırma, canlı ayar penceresi.","meta":"53 tür · 8 işlev grubu","href":"charts.html"},{"t":"Şemalar","b":"diagram yapı taşı ve kitin ilettiği bütün Mermaid v10 türleri (flowchart, sequence, state, ER, class, gantt, pie, journey, mindmap, timeline, sankey-beta, ...). Tema değişkenleri şemanın içine kadar akar.","meta":"Mermaid kataloğu","href":"diagrams.html"},{"t":"Sözlük ve dış kaynaklar","b":"Dosya yerleşimi, çok dilli kayıtlar, proje düzeyinde değiştirmeler, ayrım söz dizimi, çözümleme algoritması.","meta":"çok alanlı kayıt defteri","href":"glossary.html"},{"t":"Mimari","b":"Kitin çalışma anında nasıl bir araya geldiği — işleme akışı, balon denetleyicisi, kit yükleyicisi, derleme hattı, bağımsız paket. Kitin kendisini genişletirken ya da ayıklarken bunu okuyun.","meta":"iç yapı · geliştirici okuru","href":"architecture.html"},{"t":"CLI başvurusu","b":"Altı komut. Her birinin ne yaptığı, nasıl bir çıktı beklemeniz gerektiği, belge ağacı denetleyicisinin önem derecesi tablosu ve iki bağımlılık — jsonschema zorunlu, pagefind isteğe bağlı.","meta":"init · build · clean · migrate · check · serve","href":"cli.html"},{"t":"Neden markdown","b":"Beş kaynak biçimi belirteç sayısı, dönüştürücü yükü ve ekosisteme uyum üzerinden ölçüldü. Ölçümün söylediği şey, karar bir daha hafızadan tartışılmasın diye burada duruyor.","meta":"kaynak biçimi kararı","href":"format-comparison.html"},{"t":"Yol haritası","b":"Açık ve sürmekte olan işler, grafik türü başına etkileşim durumu, yakın zamanda tamamlananlar, kilitlenmiş kararlar ve her değişikliğin uyduğu ilkeler.","meta":"sırada ne var · oku 1.0","href":"roadmap.html"}]}
```

## Bir sayfa neye benzer {#shape}

Yazarın yazdığı şey Markdown, teslim edilen şey HTML. Sayfa-JSON, araçların hâlâ kabul ettiği ikinci biçim — markdown kaynağından eskidir ve işlenmeye devam eder. Solda kod, sağda gerçek çıktı.

### JSON kaynağı {#shape-json}

Elle ya da yapay zekâ ile yazılır. Her blok türünü açıkça bildirir; hiçbir şeyin tahmin edilmesi gerekmez. Teslim edilmeden önce kit şemasına göre doğrulanır.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"info\",\n  \"title\": \"Dikkat\",\n  \"content\": \"Bilgi kutuları dokuz tondan birini taşır: info, note, tip, warn, caution, danger, success, neutral, important.\"\n}","lang":"json"},"output":"> [!INFO] Dikkat\n> Bilgi kutuları dokuz tondan birini taşır: info, note, tip, warn, caution, danger, success, neutral, important."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"kpi-grid\",\n  \"tiles\": [\n    { \"num\": \"53\",   \"label\": \"grafik türü\" },\n    { \"num\": \"JSON\", \"label\": \"tek kaynak\" },\n    { \"num\": \"0\",    \"label\": \"içerik için derleme adımı\" }\n  ]\n}","lang":"json"},"output":{"k":"kpi-grid","tiles":[{"num":"53","label":"grafik türü"},{"num":"JSON","label":"tek kaynak"},{"num":"0","label":"içerik için derleme adımı"}]}}
```

### Markdown kaynağı {#shape-md}

Elinizdeki .md dosyalarını belge köküne bırakın. ATX başlıkları, kod çitleri (mermaid dahil), listeler, tablolar, alıntı blokları ve satır içi biçimlendirmenin tamamı dönüşür. Göreli .md bağlantıları .html adresine yönlendirilir. README / CHANGELOG ve benzerleri de birer sayfa olarak görünür.

Alt küme katıdır ve `oku check` bunun dışında kalan her şeyi tek tek adlandırır. Setext (`===` alt çizgili) başlık hatadır. Boş satırdan sonra gelen dört boşluk girintili blok, `>` işareti olmadan sürdürülen alıntı satırı ve bir metin satırının hemen altına konmuş `---` ise uyarıdır — bunların her biri CommonMark ile kitin farklı okuduğu bir yapıdır, bu yüzden denetleyici tahmin yürütmek yerine belirsizliği gidermenizi ister.

```oku-example
{"code":{"k":"code","src":"> Alıntı blokları nötr bilgi kutusuna dönüşür.\n>\n> Birden çok satır aynı kutunun gövdesinde bir arada kalır.","lang":"markdown"},"output":"> [!NEUTRAL]\n> Alıntı blokları nötr bilgi kutusuna dönüşür.\n> \n> Birden çok satır aynı kutunun gövdesinde bir arada kalır."}
```

```oku-example
{"code":{"k":"code","src":"- *eğik* ve **kalın** satır içinde çalışır\n- `satır içi kod` kitin eşaralıklı yazı tipiyle işlenir\n- madde imli ve numaralı listeler doğrudan yerleşir","lang":"markdown"},"output":"- *eğik* ve **kalın** satır içinde çalışır\n- `satır içi kod` kitin eşaralıklı yazı tipiyle işlenir\n- madde imli ve numaralı listeler doğrudan yerleşir"}
```

```oku-example
{"code":{"k":"code","src":"```mermaid\nflowchart LR\n  A[\"Markdown\"] --> B[\"oku\"]\n  B --> C[\"İşlenmiş şema\"]\n```","lang":"markdown"},"output":{"k":"diagram","src":"flowchart LR\n  A[\"Markdown\"] --> B[\"oku\"]\n  B --> C[\"İşlenmiş şema\"]\n"}}
```

## Hızlı başlangıç {#quickstart}

İki komut. Var olan bir docs/ dizinini hiçbir şeyi yeniden yazmadan kite taşıyın.

```bash
cd path/to/your-project/docs
oku init     # creates _oku symlink + index.html
oku serve    # http://localhost:9876 with live reload
```

`init` sonrasında belge ağacındaki her `.md` ya da `.json` dosyası bir sayfadır. Kenar çubuğu bunları listeler; sayfa içi içindekiler H2 / H3 başlıklarından kurulur; tam metin arama, pagefind erişilebilir olduğunda `oku build` ile kurulur — `oku[search]` ek paketiyle yükleyin ya da `pagefind` komutunu PATH üzerinde bulundurun.
