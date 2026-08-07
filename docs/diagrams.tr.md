---
title: Şemalar
eyebrow: Başvuru · Mermaid
order: 23
summary: diagram bileşeni + kitin birlikte geldiği Mermaid v10 tür kataloğu.
parent: reference
---

## Şema + Mermaid {#diagrams}

### diagram {#diagram}

Mermaid ile çizilir. Sayfada karşılaşılan ilk `<diagram>` öğesinde Mermaid 10'u CDN'den geç yükler. `source` alanı herhangi bir Mermaid sözdizimi olabilir (flowchart, sequence, gantt, state, class). Tema değiştiğinde yeniden çizilir, böylece renkler açık/koyu temayı izler.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"diagram\",\n  \"caption\": \"Optional caption below the diagram.\",\n  \"source\": \"flowchart LR\\n  A[JSON page] --> B(renderer)\\n  B --> C[DOM]\"\n}","lang":"json"},"output":{"k":"diagram","src":"flowchart LR\n    JSON[*.json sayfaları] --> RJ[renderer.js]\n    RJ --> DOM[Custom Element DOM]\n    KIT[kit.json + sözlük] --> CJ[chrome.js]\n    CJ --> DOM","caption":"Derleme hattı tek bakışta."}}
```

### Desteklenen Mermaid türleri {#mermaid-supported}

diagram bileşeni kaynağı Mermaid v10'a theme:'base' ile iletir; hiçbir şema türü kapalı değildir. Bu kitte denenmiş olanlar: flowchart, sequence, class, state, ER, journey, gantt, pie, requirement, gitGraph, c4, mindmap, timeline, quadrantChart, sankey-beta, xychart-beta, block-beta, packet-beta, architecture-beta. Her biri sayfanın vurgu / yüzey / metin değişkenlerini kitin themeVariables eşlemesi üzerinden devralır, dolayısıyla açık/koyu tema kendiliğinden izlenir.

### sequence {#mermaid-sequence}

Aktörler / yaşam çizgileri / sinyaller — protokol ya da çağrı akışları için en uygunu.

```oku-example
{"code":{"k":"code","src":"sequenceDiagram\n  participant Reader as Okuyucu\n  participant Renderer\n  Reader->>Renderer: sayfayı aç\n  Renderer-->>Reader: doldurulmuş DOM","lang":"mermaid"},"output":{"k":"diagram","src":"sequenceDiagram\n  participant Reader as Okuyucu\n  participant Renderer\n  Reader->>Renderer: sayfayı aç\n  Renderer-->>Reader: doldurulmuş DOM"}}
```

### state {#mermaid-state}

Sonlu durum makinesi — geçişler olaylarla tetiklenir; taslak / inceleme / yayım akışları için çok uygundur.

```oku-example
{"code":{"k":"code","src":"stateDiagram-v2\n  [*] --> Draft\n  Draft --> Review : gönder\n  Review --> Draft : reddet\n  Review --> Published : onayla\n  Published --> [*]","lang":"mermaid"},"output":{"k":"diagram","src":"stateDiagram-v2\n  [*] --> Draft\n  Draft --> Review : gönder\n  Review --> Draft : reddet\n  Review --> Published : onayla\n  Published --> [*]"}}
```

### ER (varlık-ilişki) {#mermaid-er}

Birincil anahtarlar / çokluk. schema-design becerisinin ürettiği biçimi yansıtır.

```oku-example
{"code":{"k":"code","src":"erDiagram\n  PAGE ||--o{ BLOCK : \"içerir\"\n  BLOCK ||--o{ INLINE : \"taşır\"","lang":"mermaid"},"output":{"k":"diagram","src":"erDiagram\n  PAGE ||--o{ BLOCK : \"içerir\"\n  BLOCK ||--o{ INLINE : \"taşır\""}}
```

### class {#mermaid-class}

Öznitelikleri, yöntemleri ve kalıtım oklarıyla UML biçiminde sınıf gösterimi.

```oku-example
{"code":{"k":"code","src":"classDiagram\n  class OkuRenderer {\n    +render(json)\n    -_renderBlock(b)\n  }\n  class OkuChart\n  OkuRenderer --> OkuChart","lang":"mermaid"},"output":{"k":"diagram","src":"classDiagram\n  class OkuRenderer {\n    +render(json)\n    -_renderBlock(b)\n  }\n  class OkuChart\n  OkuRenderer --> OkuChart"}}
```

### gantt {#mermaid-gantt}

Zamana yayılan işler; bağımlılıklar ve kritik yol ile birlikte.

```oku-example
{"code":{"k":"code","src":"gantt\n  title Q3 lansmanı — içerik + yayım\n  dateFormat YYYY-MM-DD\n  axisFormat %b %d\n  excludes weekends\n\n  section Keşif\n  Mevcut sayfaların denetimi   :done,    a1, 2026-05-04, 5d\n  Müşteri görüşmeleri          :done,    a2, after a1, 6d\n  İçerik eksenlerinin tanımı   :done,    a3, after a2, 3d\n\n  section Yazım\n  Taslak plan ve onay          :active,  w1, after a3, 4d\n  Eksen sayfalarının taslağı   :         w2, after w1, 8d\n  Editör incelemesi            :         w3, after w2, 4d\n\n  section Tasarım ve yapım\n  Sayfa şablonları             :crit,    d1, after a3, 6d\n  Kapak görselleri             :         d2, after d1, 5d\n  Sayfaların yapımı            :         d3, after w3, 7d\n\n  section Yayım\n  Kırılma noktalarında test    :crit,    s1, after d3, 3d\n  Sessiz açılış                :milestone, s2, after s1, 0d\n  Kamuya duyuru                :milestone, s3, after s2, 1d","lang":"mermaid"},"output":{"k":"diagram","src":"gantt\n  title Q3 lansmanı — içerik + yayım\n  dateFormat YYYY-MM-DD\n  axisFormat %b %d\n  excludes weekends\n\n  section Keşif\n  Mevcut sayfaların denetimi   :done,    a1, 2026-05-04, 5d\n  Müşteri görüşmeleri          :done,    a2, after a1, 6d\n  İçerik eksenlerinin tanımı   :done,    a3, after a2, 3d\n\n  section Yazım\n  Taslak plan ve onay          :active,  w1, after a3, 4d\n  Eksen sayfalarının taslağı   :         w2, after w1, 8d\n  Editör incelemesi            :         w3, after w2, 4d\n\n  section Tasarım ve yapım\n  Sayfa şablonları             :crit,    d1, after a3, 6d\n  Kapak görselleri             :         d2, after d1, 5d\n  Sayfaların yapımı            :         d3, after w3, 7d\n\n  section Yayım\n  Kırılma noktalarında test    :crit,    s1, after d3, 3d\n  Sessiz açılış                :milestone, s2, after s1, 0d\n  Kamuya duyuru                :milestone, s3, after s2, 1d"}}
```

### pie {#mermaid-pie}

Basit dağılım — okunabilirlik için dilim sayısını 6 ile sınırlayın.

```oku-example
{"code":{"k":"code","src":"pie title Zaman nereye gidiyor\n  \"chrome.js\" : 40\n  \"chrome.css\" : 25\n  \"renderer.js\" : 15\n  \"cli.py\" : 12\n  \"docs\" : 8","lang":"mermaid"},"output":{"k":"diagram","src":"pie title Zaman nereye gidiyor\n  \"chrome.js\" : 40\n  \"chrome.css\" : 25\n  \"renderer.js\" : 15\n  \"cli.py\" : 12\n  \"docs\" : 8"}}
```

### journey {#mermaid-journey}

Aşamalar boyunca kullanıcı yolculuğunun puanlanması — sürtünme noktalarını hızlıca ayıklar.

```oku-example
{"code":{"k":"code","src":"journey\n  title Kiti benimseme\n  section Kurulum\n    Depoyu keşfet : 4 : Yazar\n    init çalıştır : 5 : Yazar\n  section Yazım\n    Sayfa ekle    : 4 : Yazar\n    Siteyi kur    : 5 : Yazar","lang":"mermaid"},"output":{"k":"diagram","src":"journey\n  title Kiti benimseme\n  section Kurulum\n    Depoyu keşfet : 4 : Yazar\n    init çalıştır : 5 : Yazar\n  section Yazım\n    Sayfa ekle    : 4 : Yazar\n    Siteyi kur    : 5 : Yazar"}}
```

### mindmap {#mermaid-mindmap}

Merkezî bir düğümden dallanan, birbiriyle ilişkili fikirler ağacı.

```oku-example
{"code":{"k":"code","src":"mindmap\n  root((oku))\n    Yazım\n      JSON\n      Markdown\n    Çalışma zamanı\n      chrome.js\n      renderer.js\n    Derleme\n      site\n      standalone\n      markdown","lang":"mermaid"},"output":{"k":"diagram","src":"mindmap\n  root((oku))\n    Yazım\n      JSON\n      Markdown\n    Çalışma zamanı\n      chrome.js\n      renderer.js\n    Derleme\n      site\n      standalone\n      markdown"}}
```

### timeline {#mermaid-timeline}

Bölümlere ayrılmış, doğrusal olay dizisi.

```oku-example
{"code":{"k":"code","src":"timeline\n  title oku yol haritası\n  section Temeller\n    2026-05-24 : P0 temizlik\n    2026-05-24 : P1 bileşenler\n  section Grafikler\n    2026-05-24 : P2 etkileşim\n  section İçerik\n    2026-05-24 : P3 başvuru\n    2026-05-24 : P4 markdown eşitliği","lang":"mermaid"},"output":{"k":"diagram","src":"timeline\n  title oku yol haritası\n  section Temeller\n    2026-05-24 : P0 temizlik\n    2026-05-24 : P1 bileşenler\n  section Grafikler\n    2026-05-24 : P2 etkileşim\n  section İçerik\n    2026-05-24 : P3 başvuru\n    2026-05-24 : P4 markdown eşitliği"}}
```

### sankey-beta {#mermaid-sankey}

Aşamalar arasında akış / pay. Huniler, enerji, trafik için kullanın.

```oku-example
{"code":{"k":"code","src":"sankey-beta\n\nGelenler,Abone olanlar,40\nGelenler,Terk edenler,60\nAbone olanlar,Kullananlar,25\nAbone olanlar,Elenenler,15","lang":"mermaid"},"output":{"k":"diagram","src":"sankey-beta\n\nGelenler,Abone olanlar,40\nGelenler,Terk edenler,60\nAbone olanlar,Kullananlar,25\nAbone olanlar,Elenenler,15"}}
```

## Kendi şemanızı çizmek {#hand-drawn}

Mermaid topolojiyi karşılar. Şeklin gerçek bir eksene, önce / sonra
ayrımına ya da Mermaid'in dilbilgisinde karşılığı olmayan bir biçime
ihtiyacı olduğunda SVG'yi bir HTML adasında kendiniz çizin — adanın hiçbir
kısıtı yoktur.

Yapmamanız gereken tek şey, doğrudan bir onaltılık renk yazmaktır. Sabit
kodlanmış bir renk, figürün kimsenin bakmadığı temada görünmez kalmasının
yoludur: koyu yüzeyde koyu mürekkep, açık yüzeyde soluk bir kutu.
`oku check` bunu `island-hand-styled` olarak bildirir. Aşağıdaki sınıflar
tam olarak onun kullanmanızı söylediği sınıflardır — her biri sayfanın
geri kalanıyla aynı değişkenlerden beslenir, dolayısıyla figür sayfanın
vurgu rengini ve iki temayı bedavaya izler.

<figure class="okt-figure">
<svg viewBox="0 0 640 250" role="img" aria-label="Elle çizilen bir SVG için sınıf sözlüğü: düğüm dolguları, bir grup bölgesi ve üç kenar kalınlığı.">
<defs>
<marker id="oku-vocab-head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="okt-diag-arrow" d="M 0 0 L 10 5 L 0 10 z"/></marker>
<marker id="oku-vocab-head-strong" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="okt-diag-arrow strong" d="M 0 0 L 10 5 L 0 10 z"/></marker>
</defs>
<rect class="okt-diag-node" x="20" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node accent" x="144" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node ok" x="268" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node warn" x="392" y="24" width="104" height="40" rx="9"/>
<rect class="okt-diag-node fail" x="516" y="24" width="104" height="40" rx="9"/>
<text class="okt-diag-label" x="72" y="49" text-anchor="middle">node</text>
<text class="okt-diag-label accent" x="196" y="49" text-anchor="middle">accent</text>
<text class="okt-diag-label ok" x="320" y="49" text-anchor="middle">ok</text>
<text class="okt-diag-label warn" x="444" y="49" text-anchor="middle">warn</text>
<text class="okt-diag-label fail" x="568" y="49" text-anchor="middle">fail</text>
<text class="okt-diag-label mono" x="72" y="82" text-anchor="middle">.okt-diag-node</text>
<text class="okt-diag-label mono" x="196" y="82" text-anchor="middle">.accent</text>
<text class="okt-diag-label mono" x="320" y="82" text-anchor="middle">.ok</text>
<text class="okt-diag-label mono" x="444" y="82" text-anchor="middle">.warn</text>
<text class="okt-diag-label mono" x="568" y="82" text-anchor="middle">.fail</text>
<rect class="okt-diag-group" x="20" y="112" width="280" height="88" rx="12"/>
<rect class="okt-diag-node plain" x="40" y="140" width="110" height="34" rx="8"/>
<rect class="okt-diag-node plain" x="170" y="140" width="110" height="34" rx="8"/>
<text class="okt-diag-label soft" x="95" y="161" text-anchor="middle">okuyucu</text>
<text class="okt-diag-label soft" x="225" y="161" text-anchor="middle">yazar</text>
<text class="okt-diag-label mono" x="160" y="236" text-anchor="middle">.okt-diag-group</text>
<line class="okt-diag-edge" x1="345" y1="128" x2="465" y2="128" marker-end="url(#oku-vocab-head)"/>
<line class="okt-diag-edge dashed" x1="345" y1="160" x2="465" y2="160"/>
<line class="okt-diag-edge strong" x1="345" y1="192" x2="465" y2="192" marker-end="url(#oku-vocab-head-strong)"/>
<text class="okt-diag-label mono" x="478" y="132">.okt-diag-edge</text>
<text class="okt-diag-label mono" x="478" y="164">.dashed</text>
<text class="okt-diag-label mono" x="478" y="196">.strong</text>
</svg>
<figcaption>Beş düğüm dolgusu, bir grup bölgesi, üç kenar kalınlığı. Yukarıdaki her dolgu, çizgi ve metin rengi bir CSS değişkenidir; aynı işaretleme her iki temada da doğru çizilir ve ağaca hangi vurgu rengi verilmişse onu izler.</figcaption>
</figure>

`.okt-diag-label` sınıfı ayrıca `.strong`, `.soft`, `.faint` ve `.mono`
niteleyicilerini alır; `.okt-diag-arrow` ise kenarla aynı durum
niteleyicilerini alır, çünkü bir `<marker>` kendi dolgusuyla boyanır ve
çizginin çizgi rengi ona hiç ulaşmaz. Her biçime bir kategori kodlayan bir
figür için `.okt-diag-fill-1` ile `-10` arası sınıflar grafik renk
rampasıdır; böylece elle çizilen bir figür, çevresindeki her grafikle aynı
palette durur.
