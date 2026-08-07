---
title: Grafikler
eyebrow: Başvuru · grafikler
order: 21
summary: 53 grafik türü, 50'si yük tanımı + canlı örnekle — kartezyen, kategorik, parça-bütün, dağılım, eğilim, akış, ağ, çok değişkenli, hedef, coğrafi.
parent: reference
---

## Grafik türleri {#charts}

`chart` bileşeni `type` alanı için 53 değer kabul eder. Bunların ellisi bu sayfada işlenmiş bir bölüm alır — yük tanımı ve canlı çizim. Bölümü olmayan üçü şunlardır: `plot` ve `arc`, öğenin yazardan almak yerine kendi kendine ayarladığı temel kipler; bir de karo harita bölümünün kapsadığı takma ad olan `geo`. Türü amacınıza göre seçin — aşağıdaki aileler aynı biçimdeki sorunu çözen türleri bir araya toplar. Her kart küçük bir canlı önizleme taşır; tam yük tanımı ve canlı çizim için türe tıklayıp geçin.

### chart {#chart}

Tek bileşen, `type` alanı üzerinden pek çok çizim kipi. Kartezyen ailesi (`scatter`, `line`, `area`, `bubble`, `quadrant`) kaydırma / yakınlaştırma / logaritmik eksen / PNG dışa aktarma özellikli ortak bir etkileşimli SVG çizim alanı kullanır. Bar ailesi (`bar`, `stacked-bar`, `grouped-bar`) yatay CSS çubukları çizer. `donut` bir dağılım yayı çizer. Renderer `type` alanına göre dallanır — her kipin kendi yük biçimi vardır; kullanılmayan alanlar göz ardı edilir.

> [!INFO] Altta yatan kütüphane
> Bütün kipler kitin kendisine aittir — üçüncü taraf grafik kütüphanesi yok. Kartezyen ve donut kipleri, oku-chart Custom Element'inin çizdiği satır içi SVG olarak üretilir. Bar ailesi düz HTML + CSS olarak çizilir; ilk boyamadan sonra JavaScript çalışmaz.

### İşleve göre seçin {#chart-families}

Türlerin 43'ü, söylemek istediğinize göre gruplanmış. Herhangi bir karta tıklayarak o türün tam örneğine atlayın — küçük canlı çizim biçimin nasıl göründüğünü gösterir. Aşağıdaki aileler 50 türün tamamını taşır.

#### Karşılaştır {#chart-fn-compare}

Çubuklar, hedefe karşı noktalar, ışınsal kollar — değerleri yan yana dizip okuyucunun büyüklükleri karşılaştırmasını sağlayan her şey.

```oku-compare-grid
{"cards":[{"t":"bar","b":"","href":"#chart-bar"},{"t":"stacked-bar","b":"","href":"#chart-stacked"},{"t":"grouped-bar","b":"","href":"#chart-grouped"},{"t":"bullet","b":"","href":"#chart-bullet"},{"t":"gauge","b":"","href":"#chart-gauge"},{"t":"radar","b":"","href":"#chart-radar"},{"t":"slope","b":"","href":"#chart-slope"},{"t":"parallel-coordinates","b":"","href":"#chart-parallel-coordinates"},{"t":"dot-plot","b":"","href":"#chart-dot-plot"},{"t":"waterfall","b":"","href":"#chart-waterfall"},{"t":"lollipop","b":"","href":"#chart-lollipop"},{"t":"dumbbell","b":"","href":"#chart-dumbbell"}]}
```

#### Eğilim {#chart-fn-trend}

X ekseninin zaman olduğu sürekli eğilimler ya da döngüsel örüntüler.

```oku-compare-grid
{"cards":[{"t":"line","b":"","href":"#chart-line"},{"t":"area","b":"","href":"#chart-area"},{"t":"sparkline","b":"","href":"#chart-sparkline"},{"t":"calendar-heatmap","b":"","href":"#chart-calendar-heatmap"},{"t":"candlestick","b":"","href":"#chart-candlestick"},{"t":"stream","b":"","href":"#chart-stream"},{"t":"bump","b":"","href":"#chart-bump"}]}
```

#### Dağılım {#chart-fn-distribution}

Değerlerin nerede kümelendiği, yayılımın nasıl göründüğü, tepe noktalarının kategoriler arasında nasıl karşılaştırıldığı.

```oku-compare-grid
{"cards":[{"t":"histogram","b":"","href":"#chart-histogram"},{"t":"box-plot","b":"","href":"#chart-box-plot"},{"t":"ridgeline","b":"","href":"#chart-ridgeline"},{"t":"density","b":"","href":"#chart-density"},{"t":"violin","b":"","href":"#chart-violin"},{"t":"beeswarm","b":"","href":"#chart-beeswarm"}]}
```

#### Bileşim {#chart-fn-composition}

Adlandırılmış dilimlere bölünen ve o dilimlerin toplamı olan tek bir bütün. Biçimi, kaç parçanız olduğuna ve merkezin önemli olup olmadığına göre seçin.

```oku-compare-grid
{"cards":[{"t":"pie","b":"","href":"#chart-pie"},{"t":"donut","b":"","href":"#chart-donut"},{"t":"waffle","b":"","href":"#chart-waffle"},{"t":"marimekko","b":"","href":"#chart-marimekko"},{"t":"polar-area","b":"","href":"#chart-polar-area"}]}
```

#### İlişki {#chart-fn-relationship}

Bir değişkenin bir başkasına nasıl bağlı olduğu — çiftler, matrisler, varlıklar arası bağlar.

```oku-compare-grid
{"cards":[{"t":"scatter","b":"","href":"#chart-scatter"},{"t":"bubble","b":"","href":"#chart-bubble"},{"t":"quadrant","b":"","href":"#chart-quadrant"},{"t":"heatmap","b":"","href":"#chart-heatmap"},{"t":"chord","b":"","href":"#chart-chord"},{"t":"network","b":"","href":"#chart-network"},{"t":"scatter-matrix","b":"","href":"#chart-scatter-matrix"}]}
```

#### Sıradüzen {#chart-fn-hierarchy}

İç içe kapsama — bir şeyin içindeki bir şeyin içindeki bir şey.

```oku-compare-grid
{"cards":[{"t":"treemap","b":"","href":"#chart-treemap"},{"t":"sunburst","b":"","href":"#chart-sunburst"}]}
```

#### Akış {#chart-fn-flow}

Bir yerden bir yere hareket eden miktar — huni aşamaları, ağırlıklı kaynak→hedef bağları.

```oku-compare-grid
{"cards":[{"t":"funnel","b":"","href":"#chart-funnel"},{"t":"sankey","b":"","href":"#chart-sankey"},{"t":"gantt","b":"","href":"#chart-gantt"}]}
```

#### Konum {#chart-fn-location}

Dünyayı bölgelere göre kabaca yaklaşıklayan bir karo ızgarasına yerleştirilmiş değerler. Gerçek bir koroplet DEĞİLDİR — her bölge, ISO koduyla etiketlenmiş sabit boyutlu bir karodur. Okuyucunun bölgesel farkları tek bakışta taraması gerektiğinde, gerçek bir haritanın görsel bütçesini (ya da topojson bağımlılığını) ödemeden kullanın.

```oku-compare-grid
{"cards":[{"t":"geo","b":"","href":"#chart-geo"}]}
```

## Kartezyen — eksenli x/y noktaları {#family-cartesian}

X ekseni sürekli bir nicelik (ya da sıralı bir dizi) olduğunda ve konumu, eğimi veya iki sayısal boyut arasındaki ilişkiyi göstermek istediğinizde kullanın.

### type: scatter {#chart-scatter}

Bir ya da daha çok {x, y} nokta serisi — bağlayıcı çizgi yok, yalnızca noktalar. Nokta başına etiket isteğe bağlıdır (imleç üzerine gelince görünür). Seri başına renk, accent / warn / danger / success / muted sözlüğünden gelir. Eksenler kendiliğinden ölçeklenir; logaritmik eksen için öğeye x-scale=log / y-scale=log geçirin.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"scatter\",\n  \"title\": \"Cost vs. impact\",\n  \"x_label\": \"Engineering cost\",\n  \"y_label\": \"User impact\",\n  \"series\": [\n    { \"label\": \"Sample series\", \"color\": \"accent\", \"data\": [\n      { \"x\": 4, \"y\": 9, \"label\": \"H3\" },\n      { \"x\": 6, \"y\": 8, \"label\": \"S2-inline\" }\n    ]}\n  ]\n}","lang":"json"},"output":{"type":"scatter","title":"Grafik örneği — maliyet ve etki","x_label":"Mühendislik maliyeti","y_label":"Kullanıcı etkisi","series":[{"label":"Engelleyiciler + Yüksek","color":"accent","data":[{"x":4,"y":9,"label":"H3"},{"x":6,"y":8,"label":"S2-inline"},{"x":2,"y":5,"label":"schema-validate"}]},{"label":"Cilalama","color":"warn","data":[{"x":1,"y":2,"label":"L1"},{"x":1,"y":3,"label":"L3"},{"x":1,"y":2,"label":"isTouch"}]}],"k":"chart"}}
```

### type: line {#chart-line}

Nokta serisi sözleşmesi scatter ile aynıdır — fark, renderer'ın ardışık noktaları bir çoklu çizgiyle birleştirmesidir. X ekseni sıralı olduğunda (zaman, derleme numarası, sıra) ve okuyucunun yalnızca konumu değil eğimi de görmesi gerektiğinde kullanın. İki ya da daha çok seri aynı eksenlerde üst üste gelir; sağ üstteki gösterge çipleri görünürlüğü açıp kapatır. Noktalardan geçen Catmull-Rom eğrisi için `"curve": "smooth"` ekleyin (varsayılan `linear`); `type: area` için de geçerlidir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"line\",\n  \"title\": \"P50 latency over 7 days\",\n  \"x_label\": \"Day\",\n  \"y_label\": \"ms\",\n  \"series\": [\n    { \"label\": \"api-gateway\", \"color\": \"accent\", \"data\": [\n      { \"x\": 1, \"y\": 142 }, { \"x\": 2, \"y\": 155 }, { \"x\": 3, \"y\": 138 },\n      { \"x\": 4, \"y\": 161 }, { \"x\": 5, \"y\": 149 }, { \"x\": 6, \"y\": 144 }, { \"x\": 7, \"y\": 152 }\n    ]},\n    { \"label\": \"auth-svc\", \"color\": \"warn\", \"data\": [\n      { \"x\": 1, \"y\": 88 }, { \"x\": 2, \"y\": 92 }, { \"x\": 3, \"y\": 110 },\n      { \"x\": 4, \"y\": 132 }, { \"x\": 5, \"y\": 121 }, { \"x\": 6, \"y\": 98 }, { \"x\": 7, \"y\": 90 }\n    ]}\n  ]\n}","lang":"json"},"output":{"type":"line","title":"7 gün boyunca P50 gecikmesi","x_label":"Gün","y_label":"ms","series":[{"label":"api-gateway","color":"accent","data":[{"x":1,"y":142},{"x":2,"y":155},{"x":3,"y":138},{"x":4,"y":161},{"x":5,"y":149},{"x":6,"y":144},{"x":7,"y":152}]},{"label":"auth-svc","color":"warn","data":[{"x":1,"y":88},{"x":2,"y":92},{"x":3,"y":110},{"x":4,"y":132},{"x":5,"y":121},{"x":6,"y":98},{"x":7,"y":90}]},{"label":"search-svc","color":"success","data":[{"x":1,"y":64},{"x":2,"y":71},{"x":3,"y":68},{"x":4,"y":79},{"x":5,"y":73},{"x":6,"y":70},{"x":7,"y":66}]}],"k":"chart"}}
```

### type: area {#chart-area}

Line ile aynı biçim — {x, y} nokta serisi — ama eğri taban çizgisine kadar doldurulur. Yönü kadar büyüklüğü de önemli olan, zamana yayılmış birikimli ölçümler için elverişlidir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"area\",\n  \"x_label\": \"Day\",\n  \"y_label\": \"Active users\",\n  \"series\": [\n    { \"label\": \"Daily\", \"color\": \"accent\", \"data\": [\n      { \"x\": 1, \"y\": 40 }, { \"x\": 2, \"y\": 65 },\n      { \"x\": 3, \"y\": 55 }, { \"x\": 4, \"y\": 80 },\n      { \"x\": 5, \"y\": 95 }, { \"x\": 6, \"y\": 110 },\n      { \"x\": 7, \"y\": 130 }\n    ]}\n  ]\n}","lang":"json"},"output":{"type":"area","title":"Etkin kullanıcılar — ilk hafta","x_label":"Gün","y_label":"Etkin kullanıcı","series":[{"label":"Günlük","color":"accent","data":[{"x":1,"y":40},{"x":2,"y":65},{"x":3,"y":55},{"x":4,"y":80},{"x":5,"y":95},{"x":6,"y":110},{"x":7,"y":130}]}],"k":"chart"}}
```

### type: bubble {#chart-bubble}

Üçüncü boyutu nokta boyutuna kodlayan saçılım grafiği. Her nokta isteğe bağlı bir `size` alanı alır; renderer bunun karekökünü aldığı için noktanın ALANI boyutla orantılı olur (göz yarıçapı değil alanı okur). Maliyet, etki ve güven gibi eksenler taşıyan karar matrisleri için elverişlidir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"bubble\",\n  \"x_label\": \"Cost\",\n  \"y_label\": \"Impact\",\n  \"series\": [\n    { \"label\": \"Initiatives\", \"color\": \"accent\", \"data\": [\n      { \"x\": 2, \"y\": 8, \"size\": 40,  \"label\": \"Search\" },\n      { \"x\": 6, \"y\": 9, \"size\": 120, \"label\": \"Auth\" },\n      { \"x\": 4, \"y\": 4, \"size\": 80,  \"label\": \"Logging\" },\n      { \"x\": 7, \"y\": 2, \"size\": 25,  \"label\": \"Theme\" }\n    ]}\n  ]\n}","lang":"json"},"output":{"type":"bubble","title":"Girişimler — maliyet, etki ve ekip boyutu","x_label":"Maliyet","y_label":"Etki","series":[{"label":"Girişimler","color":"accent","data":[{"x":2,"y":8,"size":40,"label":"Arama"},{"x":6,"y":9,"size":120,"label":"Kimlik doğrulama"},{"x":4,"y":4,"size":80,"label":"Günlükleme"},{"x":7,"y":2,"size":25,"label":"Tema"}]}],"k":"chart"}}
```

### type: quadrant {#chart-quadrant}

İki referans çizgisiyle dört bölgeye ayrılmış saçılım grafiği. Yazar, `x` (dikey ayrım) ve `y` (yatay ayrım) ile isteğe bağlı dört köşe etiketi (`[sol üst, sağ üst, sol alt, sağ alt]`) içeren bir `quadrants` bloğu verir. Tek bakışta 2×2 karar matrisi olarak okunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"quadrant\",\n  \"x_label\": \"Effort\",\n  \"y_label\": \"Value\",\n  \"quadrants\": {\n    \"x\": 5, \"y\": 5,\n    \"labels\": [\"Quick wins\", \"Big bets\", \"Skip\", \"Re-evaluate\"]\n  },\n  \"series\": [\n    { \"label\": \"Items\", \"color\": \"accent\", \"data\": [\n      { \"x\": 2, \"y\": 8, \"label\": \"A\" },\n      { \"x\": 7, \"y\": 8, \"label\": \"B\" },\n      { \"x\": 2, \"y\": 3, \"label\": \"C\" },\n      { \"x\": 8, \"y\": 2, \"label\": \"D\" }\n    ]}\n  ]\n}","lang":"json"},"output":{"type":"quadrant","title":"Emek × değer — karar matrisi","x_label":"Emek","y_label":"Değer","quadrants":{"x":5,"y":5,"labels":["Hızlı kazanımlar","Büyük bahisler","Atla","Yeniden değerlendir"]},"series":[{"label":"Maddeler","color":"accent","data":[{"x":2,"y":8,"label":"A"},{"x":7,"y":8,"label":"B"},{"x":2,"y":3,"label":"C"},{"x":8,"y":2,"label":"D"}]}],"k":"chart"}}
```

### type: connected-scatter {#chart-connected-scatter}

Ardışık noktaların seri sırasına göre bir çizgiyle birleştirildiği saçılım — iki boyutlu uzayda bir yörünge. `series` biçimi scatter ile aynıdır; sıra, seri içindeki veri sırasıdır. Başlangıç noktası içi boş bir halka, bitiş noktası dolu bir kare olarak çizilir, böylece yön tek bakışta okunur. İki ölçümün zaman içinde birlikte hareket ettiği durumlarda kullanın (yıllara göre yaşam beklentisi × gelir, sürümlere göre MAU × ARPU).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"connected-scatter\",\n  \"title\": \"MAU × ARPU across releases\",\n  \"x_label\": \"MAU (k)\",\n  \"y_label\": \"ARPU ($)\",\n  \"series\": [\n    {\n      \"label\": \"product\",\n      \"data\": [\n        {\"x\":  20, \"y\": 1.2, \"label\": \"v1\"},\n        {\"x\":  35, \"y\": 1.6, \"label\": \"v2\"},\n        {\"x\":  68, \"y\": 1.4, \"label\": \"v3\"},\n        {\"x\":  92, \"y\": 2.1, \"label\": \"v4\"},\n        {\"x\": 140, \"y\": 2.8, \"label\": \"v5\"}\n      ]\n    }\n  ]\n}","lang":"json"},"output":{"type":"connected-scatter","title":"Sürümler boyunca MAU × ARPU","x_label":"MAU (bin)","y_label":"ARPU ($)","series":[{"label":"ürün","data":[{"x":20,"y":1.2,"label":"v1"},{"x":35,"y":1.6,"label":"v2"},{"x":68,"y":1.4,"label":"v3"},{"x":92,"y":2.1,"label":"v4"},{"x":140,"y":2.8,"label":"v5"}]}],"k":"chart"}}
```

## Kategorik — kategori başına değer {#family-categorical}

Öğe başına bir çubuk, istenirse yığınlara ya da alt gruplara bölünmüş. Her satırda tek bir etiket ve değer varsa kullanın; her satır birden çok karşılaştırılabilir değer taşıyorsa yığın ya da grup biçimine geçin.

### type: bar {#chart-bar}

Öğe başına bir satır, yatay çubuklar. Her satır `label`, `value`, isteğe bağlı `display` (sağdaki okumayı geçersiz kılar) ve isteğe bağlı `color` (accent / warn / danger / success) taşır. `max`, çubuğun tam genişliğe karşılık gelen değerini belirler; verilmezse en büyük satırın değeri ölçeği kurar. Eksen çerçevesi olmadan etiket/değer karşılaştırması istediğinizde kullanın.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"bar\",\n  \"rows\": [\n    { \"label\": \"Spark\",  \"value\": 95, \"display\": \"95 / 100\" },\n    { \"label\": \"Flink\",  \"value\": 80 },\n    { \"label\": \"Trino\",  \"value\": 75 }\n  ]\n}","lang":"json"},"output":{"type":"bar","rows":[{"label":"Spark","value":95,"display":"95 / 100"},{"label":"Flink","value":80,"display":"80 / 100"},{"label":"Trino","value":75,"display":"75 / 100"}],"k":"chart"}}
```

### type: stacked-bar {#chart-stacked}

Her satırın serilerinin tek bir çubukta yığıldığı çok serili yatay çubuklar. Yazar `categories` (satır başına bir tane) ve `{label, color, values}` biçiminde `series` verir; `values[i]` ile `categories[i]` hizalanır. Sağdaki okuma satır toplamıdır. Bir bütünün dökümünü göstermek için kullanın.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"stacked-bar\",\n  \"title\": \"Build time by phase\",\n  \"categories\": [\"v1.0\", \"v1.1\", \"v1.2\"],\n  \"series\": [\n    { \"label\": \"compile\", \"color\": \"accent\",  \"values\": [12, 14, 11] },\n    { \"label\": \"test\",    \"color\": \"success\", \"values\": [8,  10, 12] },\n    { \"label\": \"package\", \"color\": \"warn\",    \"values\": [3,  4,  3] }\n  ]\n}","lang":"json"},"output":{"type":"stacked-bar","title":"Aşamaya göre derleme süresi","categories":["v1.0","v1.1","v1.2"],"series":[{"label":"derleme","color":"accent","values":[12,14,11]},{"label":"test","color":"success","values":[8,10,12]},{"label":"paketleme","color":"warn","values":[3,4,3]}],"k":"chart"}}
```

### type: grouped-bar {#chart-grouped}

stacked-bar ile aynı yük, ama her seri yığılmak yerine satır içinde kendi ince alt çubuğu olarak çizilir. Aynı kategori içindeki seriler arasında doğrudan karşılaştırma için kullanın.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"grouped-bar\",\n  \"title\": \"Latency by region\",\n  \"categories\": [\"p50\", \"p95\", \"p99\"],\n  \"series\": [\n    { \"label\": \"EU\", \"color\": \"accent\",  \"values\": [40, 110, 220] },\n    { \"label\": \"US\", \"color\": \"success\", \"values\": [55, 130, 260] },\n    { \"label\": \"AP\", \"color\": \"warn\",    \"values\": [70, 180, 340] }\n  ]\n}","lang":"json"},"output":{"type":"grouped-bar","title":"Bölgeye göre gecikme (ms)","categories":["p50","p95","p99"],"series":[{"label":"EU","color":"accent","values":[40,110,220]},{"label":"US","color":"success","values":[55,130,260]},{"label":"AP","color":"warn","values":[70,180,340]}],"k":"chart"}}
```

### type: dot-plot {#chart-dot-plot}

Kategori başına bir satır, değerin bulunduğu yerde tek bir nokta. Derli toplu bir karşılaştırma biçimi — yatay çubuğun yalnızca uç noktasına indirgenmiş hâli. Çubuk uzunluğunun kendisi görsel gürültü kattığında kullanın (birbirine yakın oranlar, sıralı listeler).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"dot-plot\",\n  \"title\": \"Adoption by team\",\n  \"rows\": [\n    {\n      \"label\": \"infra\",\n      \"value\": 84,\n      \"color\": \"accent\"\n    },\n    {\n      \"label\": \"platform\",\n      \"value\": 72,\n      \"color\": \"accent\"\n    },\n    {\n      \"label\": \"growth\",\n      \"value\": 58,\n      \"color\": \"warn\"\n    },\n    {\n      \"label\": \"ops\",\n      \"value\": 49,\n      \"color\": \"warn\"\n    },\n    {\n      \"label\": \"billing\",\n      \"value\": 31,\n      \"color\": \"danger\"\n    }\n  ]\n}","lang":"json"},"output":{"type":"dot-plot","title":"Ekibe göre benimseme","rows":[{"label":"altyapı","value":84,"color":"accent"},{"label":"platform","value":72,"color":"accent"},{"label":"büyüme","value":58,"color":"warn"},{"label":"operasyon","value":49,"color":"warn"},{"label":"faturalama","value":31,"color":"danger"}],"k":"chart"}}
```

### type: marimekko {#chart-marimekko}

Değişken genişlikli yığılmış çubuk — her sütunun GENİŞLİĞİ o sütunun toplamıyla orantılıdır, dolayısıyla grafik hem sütun içi oranları hem de sütunlar arası büyüklükleri tek görünümde verir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"marimekko\",\n  \"title\": \"Revenue mix by quarter\",\n  \"categories\": [\n    \"Q1\",\n    \"Q2\",\n    \"Q3\",\n    \"Q4\"\n  ],\n  \"series\": [\n    {\n      \"label\": \"new\",\n      \"values\": [\n        120,\n        180,\n        240,\n        290\n      ]\n    },\n    {\n      \"label\": \"renewal\",\n      \"values\": [\n        260,\n        280,\n        320,\n        360\n      ]\n    },\n    {\n      \"label\": \"upsell\",\n      \"values\": [\n        60,\n        90,\n        140,\n        180\n      ]\n    }\n  ]\n}","lang":"json"},"output":{"type":"marimekko","title":"Çeyreğe göre gelir dağılımı","categories":["Q1","Q2","Q3","Q4"],"series":[{"label":"yeni","values":[120,180,240,290]},{"label":"yenileme","values":[260,280,320,360]},{"label":"üst satış","values":[60,90,140,180]}],"k":"chart"}}
```

### type: waterfall {#chart-waterfall}

İki toplamı birbirine bağlayan artışlar ve azalışlar. Başlangıç çubuğu + artı/eksi adımlar + bitiş çubuğu; kesikli köprüler birikimli tepe noktalarını birleştirir. 'Bu iki sayı arasında ne değişti' sorusunun klasik grafiği — finansal köprü, elde tutma kaybının açıklaması, başarım dökümü.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"waterfall\",\n  \"title\": \"Q1 \\u2192 Q2 revenue\",\n  \"steps\": [\n    {\n      \"label\": \"Q1 start\",\n      \"value\": 100,\n      \"kind\": \"start\"\n    },\n    {\n      \"label\": \"+ new\",\n      \"value\": 35,\n      \"kind\": \"plus\"\n    },\n    {\n      \"label\": \"\\u2212 churn\",\n      \"value\": -18,\n      \"kind\": \"minus\"\n    },\n    {\n      \"label\": \"+ upsell\",\n      \"value\": 22,\n      \"kind\": \"plus\"\n    },\n    {\n      \"label\": \"\\u2212 refund\",\n      \"value\": -7,\n      \"kind\": \"minus\"\n    },\n    {\n      \"label\": \"Q2 end\",\n      \"value\": 132,\n      \"kind\": \"end\"\n    }\n  ]\n}","lang":"json"},"output":{"type":"waterfall","title":"Q1 → Q2 geliri","steps":[{"label":"Q1 başı","value":100,"kind":"start"},{"label":"+ yeni","value":35,"kind":"plus"},{"label":"− kayıp","value":-18,"kind":"minus"},{"label":"+ üst satış","value":22,"kind":"plus"},{"label":"− iade","value":-7,"kind":"minus"},{"label":"Q2 sonu","value":132,"kind":"end"}],"k":"chart"}}
```

### type: lollipop {#chart-lollipop}

dot-plot'un bir türevi — aynı veri biçimi, eksenden noktaya uzanan ince bir sapla. Asıl mesele değer karşılaştırmasıysa, daha az gürültülü bir çubuk grafiği gibi okunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"lollipop\",\n  \"title\": \"Endpoints by p95 latency (ms)\",\n  \"rows\": [\n    {\n      \"label\": \"/v1/auth\",\n      \"value\": 24,\n      \"color\": \"success\"\n    },\n    {\n      \"label\": \"/v1/search\",\n      \"value\": 78,\n      \"color\": \"accent\"\n    },\n    {\n      \"label\": \"/v1/recommend\",\n      \"value\": 142,\n      \"color\": \"warn\"\n    },\n    {\n      \"label\": \"/v1/checkout\",\n      \"value\": 240,\n      \"color\": \"danger\"\n    },\n    {\n      \"label\": \"/v1/report\",\n      \"value\": 510,\n      \"color\": \"danger\"\n    }\n  ]\n}","lang":"json"},"output":{"type":"lollipop","title":"p95 gecikmesine göre uç noktalar (ms)","rows":[{"label":"/v1/auth","value":24,"color":"success"},{"label":"/v1/search","value":78,"color":"accent"},{"label":"/v1/recommend","value":142,"color":"warn"},{"label":"/v1/checkout","value":240,"color":"danger"},{"label":"/v1/report","value":510,"color":"danger"}],"k":"chart"}}
```

### type: dumbbell {#chart-dumbbell}

Kategori başına bir çizgiyle birleştirilmiş iki nokta — önce/sonra, kadın/erkek, 2010/2020. Kategori sayısı eğim grafiğine sığmadığında onun derli toplu alternatifidir. Bağlayıcının rengi yönü belirtir (yukarı için success, aşağı için danger).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"dumbbell\",\n  \"title\": \"Q1 \\u2192 Q2 adoption\",\n  \"from_label\": \"Q1\",\n  \"to_label\": \"Q2\",\n  \"from_color\": \"muted\",\n  \"to_color\": \"accent\",\n  \"rows\": [\n    {\n      \"label\": \"infra\",\n      \"from\": 64,\n      \"to\": 88\n    },\n    {\n      \"label\": \"platform\",\n      \"from\": 52,\n      \"to\": 72\n    },\n    {\n      \"label\": \"growth\",\n      \"from\": 58,\n      \"to\": 45\n    },\n    {\n      \"label\": \"ops\",\n      \"from\": 41,\n      \"to\": 60\n    },\n    {\n      \"label\": \"billing\",\n      \"from\": 22,\n      \"to\": 38\n    }\n  ]\n}","lang":"json"},"output":{"type":"dumbbell","title":"Q1 → Q2 benimseme","from_label":"Q1","to_label":"Q2","from_color":"muted","to_color":"accent","rows":[{"label":"altyapı","from":64,"to":88},{"label":"platform","from":52,"to":72},{"label":"büyüme","from":58,"to":45},{"label":"operasyon","from":41,"to":60},{"label":"faturalama","from":22,"to":38}],"k":"chart"}}
```

### type: population-pyramid {#chart-population-pyramid}

Ortak bir kategori sütununun iki yanına açılan, birbirinden uzaklaşan iki yatay çubuk kümesi. `left.values[]` sola, `right.values[]` sağa doğru büyür; ikisi de `categories` ile hizalıdır. Nüfus piramitleri (yaş dilimi başına kadın ve erkek) ya da satır eksenini paylaşan başka herhangi bir iki yönlü karşılaştırma için kullanın (bölge başına gelir ve gider, kanal başına gelen ve giden).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"population-pyramid\",\n  \"title\": \"Active users by age bucket\",\n  \"categories\": [\"55+\", \"45–54\", \"35–44\", \"25–34\", \"18–24\"],\n  \"left\":  { \"label\": \"women\", \"color\": \"accent\",  \"values\": [ 9, 17, 26, 34, 22] },\n  \"right\": { \"label\": \"men\",   \"color\": \"success\", \"values\": [11, 19, 24, 30, 18] }\n}","lang":"json"},"output":{"type":"population-pyramid","title":"Yaş dilimine göre etkin kullanıcılar","categories":["55+","45–54","35–44","25–34","18–24"],"left":{"label":"kadın","color":"accent","values":[9,17,26,34,22]},"right":{"label":"erkek","color":"success","values":[11,19,24,30,18]},"k":"chart"}}
```

### type: range-bar {#chart-range-bar}

Öğe başına bir satır; her satır, isteğe bağlı `mid` çentiğiyle birlikte yatay bir bant olarak çizilen bir `[low, high]` aralığı taşır. Verinin kendisi *aralık* olduğunda kullanın — güven aralıkları, seçim anketleri (hata payı), maaş bantları, taban ve tavan fiyatlar, özetlenmiş hata çubukları. Sağdaki okuma sayısal aralığı gösterir; imleç üzerine gelindiğinde bilgi balonu düşük / yüksek / orta değerleri açar.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"range-bar\",\n  \"title\": \"P50 latency, 95% CI (ms)\",\n  \"ranges\": [\n    { \"label\": \"us-east-1\",  \"low\":  42, \"mid\":  48, \"high\":  56 },\n    { \"label\": \"eu-west-1\",  \"low\":  58, \"mid\":  64, \"high\":  72 },\n    { \"label\": \"ap-south-1\", \"low\":  88, \"mid\":  96, \"high\": 110, \"color\": \"warn\" },\n    { \"label\": \"sa-east-1\",  \"low\": 105, \"mid\": 118, \"high\": 132, \"color\": \"danger\" }\n  ]\n}","lang":"json"},"output":{"type":"range-bar","title":"P50 gecikmesi, %95 güven aralığı (ms)","ranges":[{"label":"us-east-1","low":42,"mid":48,"high":56},{"label":"eu-west-1","low":58,"mid":64,"high":72},{"label":"ap-south-1","low":88,"mid":96,"high":110,"color":"warn"},{"label":"sa-east-1","low":105,"mid":118,"high":132,"color":"danger"}],"k":"chart"}}
```

### type: pareto {#chart-pareto}

`value` alanına göre azalan sırada çubuklar + ikincil eksende birikimli yüzde çizgisi. Klasik 80/20 okuma biçimi — işletme, hata kök-neden denetimleri ve destek kaydı ayıklamasında "ilk N neden toplamın %80'ini açıklıyor" bulgusunu öne çıkarır. Satırları renderer sizin için sıralar; kesikli %80 kılavuzu sağdaki yüzde eksenine göre okunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"pareto\",\n  \"title\": \"Support tickets by category (last 30 d)\",\n  \"rows\": [\n    { \"label\": \"auth\",     \"value\": 142 },\n    { \"label\": \"billing\",  \"value\":  88 },\n    { \"label\": \"latency\",  \"value\":  72, \"color\": \"warn\" },\n    { \"label\": \"ui-bug\",   \"value\":  46 },\n    { \"label\": \"data\",     \"value\":  28 },\n    { \"label\": \"feature\",  \"value\":  18 },\n    { \"label\": \"other\",    \"value\":  12, \"color\": \"muted\" }\n  ]\n}","lang":"json"},"output":{"type":"pareto","title":"Kategoriye göre destek kayıtları (son 30 gün)","rows":[{"label":"kimlik doğrulama","value":142},{"label":"faturalama","value":88},{"label":"gecikme","value":72,"color":"warn"},{"label":"arayüz hatası","value":46},{"label":"veri","value":28},{"label":"özellik","value":18},{"label":"diğer","value":12,"color":"muted"}],"k":"chart"}}
```

## Parça-bütün {#family-partwhole}

Adlandırılmış dilimlere bölünmüş bir bütün. Donut ve pie klasik seçimlerdir; mutlak sayı önemliyse waffle daha iyi okunur; parçaların bir sıradüzeni varsa treemap.

### type: donut {#chart-donut}

Tek halkalı dağılım grafiği. Her `slice` bir `{label, value, color?}` nesnesidir; renderer değerleri toplamın yüzdesine çevirir, her dilim için bir yay çizer ve yanda toplam ile göstergeyi gösterir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"donut\",\n  \"title\": \"Page load breakdown\",\n  \"slices\": [\n    { \"label\": \"HTML\",  \"value\": 12, \"color\": \"accent\" },\n    { \"label\": \"CSS\",   \"value\": 28, \"color\": \"success\" },\n    { \"label\": \"JS\",    \"value\": 44, \"color\": \"warn\" },\n    { \"label\": \"Other\", \"value\": 16, \"color\": \"muted\" }\n  ]\n}","lang":"json"},"output":{"type":"donut","title":"Sayfa yükleme dökümü (KB)","slices":[{"label":"HTML","value":12,"color":"accent"},{"label":"CSS","value":28,"color":"success"},{"label":"JS","value":44,"color":"warn"},{"label":"Diğer","value":16,"color":"muted"}],"k":"chart"}}
```

### type: pie {#chart-pie}

donut ile aynı `slices` yükü; tek fark ortadaki boşluğun ve merkez okumasının olmamasıdır. Parça-bütün ilişkisi anlatılacak her şeyse ve mutlak toplamın ayrıca göze çarpması gerekmiyorsa pie'a uzanın. 2–4 dilimli dağılımlarda pie donut'tan daha iyi okunur; 5 ve üzeri dilimde donut (dilim başına gösterge şeridi daha nettir) ya da stacked-bar tercih edin.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"pie\",\n  \"title\": \"Build-time budget\",\n  \"slices\": [\n    { \"label\": \"chrome.js\",   \"value\": 40, \"color\": \"accent\" },\n    { \"label\": \"chrome.css\",  \"value\": 25, \"color\": \"success\" },\n    { \"label\": \"renderer.js\", \"value\": 20, \"color\": \"warn\" },\n    { \"label\": \"cli.py\",      \"value\": 15, \"color\": \"muted\" }\n  ]\n}","lang":"json"},"output":{"type":"pie","title":"Derleme süresi bütçesi","slices":[{"label":"chrome.js","value":40,"color":"accent"},{"label":"chrome.css","value":25,"color":"success"},{"label":"renderer.js","value":20,"color":"warn"},{"label":"cli.py","value":15,"color":"muted"}],"k":"chart"}}
```

### type: waffle {#chart-waffle}

Nokta matrisi dökümü. Varsayılan 10×10 ızgara (= 100 hücre). `segments`, `{label, count, color}` nesnelerinden oluşan bir listedir; renderer hücreleri sırayla, birim sayısı başına bir hücre olacak biçimde doldurur. Gösterge ızgaranın sağında durur ve her parçanın yüzdesini verir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"waffle\",\n  \"title\": \"User-status breakdown\",\n  \"segments\": [\n    { \"label\": \"Active\",   \"count\": 40, \"color\": \"success\" },\n    { \"label\": \"Trialing\", \"count\": 25, \"color\": \"accent\" },\n    { \"label\": \"Paused\",   \"count\": 10, \"color\": \"warn\" },\n    { \"label\": \"Churned\",  \"count\": 25, \"color\": \"danger\" }\n  ]\n}","lang":"json"},"output":{"type":"waffle","title":"Kullanıcı durumu dökümü","segments":[{"label":"Etkin","count":40,"color":"success"},{"label":"Denemede","count":25,"color":"accent"},{"label":"Duraklatılmış","count":10,"color":"warn"},{"label":"Ayrılmış","count":25,"color":"danger"}],"k":"chart"}}
```

### type: treemap {#chart-treemap}

Kareleştirilmiş yerleşimle alan-orantılı iç içe dikdörtgenler. `tree[]`, `{label, value, color?}` yapraklarından oluşan düz bir listedir; en büyük değerler en büyük dikdörtgenleri kaplar. Etiketler yalnızca dikdörtgen onları okunaklı taşıyacak kadar büyükse çizilir. Bileşim için kullanın (dile göre kod satırı, kaleme göre harcama, yola göre trafik).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"treemap\",\n  \"title\": \"LoC by language\",\n  \"tree\": [\n    {\"label\": \"JavaScript\", \"value\": 6200, \"color\": \"accent\"},\n    {\"label\": \"CSS\",        \"value\": 2400, \"color\": \"success\"},\n    {\"label\": \"Python\",     \"value\": 2800, \"color\": \"warn\"},\n    {\"label\": \"JSON\",       \"value\":  900, \"color\": \"muted\"},\n    {\"label\": \"Markdown\",   \"value\":  400, \"color\": \"danger\"}\n  ]\n}","lang":"json"},"output":{"type":"treemap","title":"Dile göre kod satırı","tree":[{"label":"JavaScript","value":6200,"color":"accent"},{"label":"CSS","value":2400,"color":"success"},{"label":"Python","value":2800,"color":"warn"},{"label":"JSON","value":900,"color":"muted"},{"label":"Markdown","value":400,"color":"danger"}],"k":"chart"}}
```

### type: sunburst {#chart-sunburst}

Işınsal sıradüzen. Derinlik başına eşmerkezli yaylar; yay uzunluğu düğüm değerlerinin toplamıyla orantılıdır. Treemap gibi, ama ışınsal — sığ ve geniş, dış yaprakları adlandırılmış ağaçlarda daha iyi okunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"sunburst\",\n  \"title\": \"Compute budget\",\n  \"tree\": {\n    \"label\": \"root\",\n    \"children\": [\n      {\n        \"label\": \"infra\",\n        \"children\": [\n          {\n            \"label\": \"compute\",\n            \"value\": 34\n          },\n          {\n            \"label\": \"storage\",\n            \"value\": 18\n          },\n          {\n            \"label\": \"network\",\n            \"value\": 12\n          }\n        ]\n      },\n      {\n        \"label\": \"product\",\n        \"children\": [\n          {\n            \"label\": \"web\",\n            \"value\": 22\n          },\n          {\n            \"label\": \"api\",\n            \"value\": 28\n          },\n          {\n            \"label\": \"jobs\",\n            \"value\": 14\n          }\n        ]\n      }\n    ]\n  }\n}","lang":"json"},"output":{"type":"sunburst","title":"İşlem bütçesi","tree":{"label":"root","children":[{"label":"altyapı","children":[{"label":"işlem","value":34},{"label":"depolama","value":18},{"label":"ağ","value":12}]},{"label":"ürün","children":[{"label":"web","value":22},{"label":"api","value":28},{"label":"işler","value":14}]}]},"k":"chart"}}
```

### type: polar-area {#chart-polar-area}

Bir çemberin çevresine dizilmiş çubuklar. Döngüsel biçimin kendisinin anlam taşıdığı döngüsel kategorik veriler (haftanın günleri, aylar, günün saatleri, pusula yönleri) içindir. Radar'dan ayrılır — radar = çok değişkenli dolu çokgen; polar-area = kategori başına dilim.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"polar-area\",\n  \"title\": \"Issues by day of week\",\n  \"sectors\": [\n    {\n      \"label\": \"Mon\",\n      \"value\": 28\n    },\n    {\n      \"label\": \"Tue\",\n      \"value\": 42\n    },\n    {\n      \"label\": \"Wed\",\n      \"value\": 56\n    },\n    {\n      \"label\": \"Thu\",\n      \"value\": 38\n    },\n    {\n      \"label\": \"Fri\",\n      \"value\": 30\n    },\n    {\n      \"label\": \"Sat\",\n      \"value\": 9\n    },\n    {\n      \"label\": \"Sun\",\n      \"value\": 6\n    }\n  ]\n}","lang":"json"},"output":{"type":"polar-area","title":"Haftanın gününe göre sorunlar","sectors":[{"label":"Pzt","value":28},{"label":"Sal","value":42},{"label":"Çar","value":56},{"label":"Per","value":38},{"label":"Cum","value":30},{"label":"Cmt","value":9},{"label":"Paz","value":6}],"k":"chart"}}
```

## Dağılım biçimi {#family-distribution}

Bir değerin toplamı değil, sıklığının nasıl yayıldığı. Kutulanmış sayımlar için histogram; çeyreklik özeti için box-plot; birden çok dağılımı dikeyde karşılaştırmak için ridgeline.

### type: histogram {#chart-histogram}

Kutu başına sıklık. Kutulamayı yazar verir (`{lo, hi, count}` biçiminde `bins[]`). Bitişik kutular bağlantılı bir dağılım olarak okunur; boşluklara izin verilir ama görünür boşlukla çizilir. Dağılım biçimi, gecikme kuyruğu, olaya kadar geçen süre için kullanın.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"histogram\",\n  \"title\": \"Request latency (ms)\",\n  \"bins\": [\n    {\"lo\":   0, \"hi\":  20, \"count\":  4},\n    {\"lo\":  20, \"hi\":  40, \"count\": 14},\n    {\"lo\":  40, \"hi\":  60, \"count\": 22},\n    {\"lo\":  60, \"hi\":  80, \"count\": 18},\n    {\"lo\":  80, \"hi\": 100, \"count\":  9},\n    {\"lo\": 100, \"hi\": 120, \"count\":  3}\n  ]\n}","lang":"json"},"output":{"type":"histogram","title":"İstek gecikmesi (ms)","bins":[{"lo":0,"hi":20,"count":4},{"lo":20,"hi":40,"count":14},{"lo":40,"hi":60,"count":22},{"lo":60,"hi":80,"count":18},{"lo":80,"hi":100,"count":9},{"lo":100,"hi":120,"count":3}],"k":"chart"}}
```

### type: box-plot {#chart-box-plot}

Çeyreklikler + bıyıklar + isteğe bağlı aykırı değerler — `boxes[]` girdisi başına bir satır. Zorunlu alanlar: `min`, `q1`, `median`, `q3`, `max`. İsteğe bağlı: bıyıkların ötesinde nokta olarak çizilen `outliers: [Number]`.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"box-plot\",\n  \"title\": \"Cold-start latency (ms) per region\",\n  \"boxes\": [\n    { \"label\": \"us-east-1\",  \"min\": 18, \"q1\": 32, \"median\": 48, \"q3\": 60, \"max\": 86, \"outliers\": [120] },\n    { \"label\": \"eu-west-1\",  \"min\": 22, \"q1\": 38, \"median\": 52, \"q3\": 66, \"max\": 92 },\n    { \"label\": \"ap-south-1\", \"min\": 38, \"q1\": 62, \"median\": 78, \"q3\": 96, \"max\": 132, \"outliers\": [180, 210] }\n  ]\n}","lang":"json"},"output":{"type":"box-plot","title":"Bölgeye göre soğuk başlangıç gecikmesi (ms)","boxes":[{"label":"us-east-1","min":18,"q1":32,"median":48,"q3":60,"max":86,"outliers":[120],"color":"accent"},{"label":"eu-west-1","min":22,"q1":38,"median":52,"q3":66,"max":92,"color":"success"},{"label":"ap-south-1","min":38,"q1":62,"median":78,"q3":96,"max":132,"outliers":[180,210],"color":"warn"}],"k":"chart"}}
```

### type: ridgeline {#chart-ridgeline}

Satır başına bir tane olmak üzere üst üste dizilmiş küçük dağılımlar. `distributions[].values` düz bir örneklemdir; renderer her örneklemi genel aralık üzerinde ~30 kutuya böler. Gruplar arasında biçim karşılaştırması için okunur (bölge başına gecikme, kesim başına etkileşim).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"ridgeline\",\n  \"title\": \"Per-region latency (ms)\",\n  \"distributions\": [\n    {\"label\": \"us-east-1\",  \"values\": [..raw samples..]},\n    {\"label\": \"eu-west-1\",  \"values\": [..raw samples..]},\n    {\"label\": \"ap-south-1\", \"values\": [..raw samples..]}\n  ]\n}","lang":"json"},"output":{"type":"ridgeline","title":"Bölge başına soğuk başlangıç gecikmesi (ms)","distributions":[{"label":"us-east-1","color":"accent","values":[22,28,30,34,36,38,40,42,44,46,48,50,52,54,56,60,62,64,68,72,76,82,90]},{"label":"eu-west-1","color":"success","values":[32,38,42,44,46,48,50,52,54,56,58,60,62,64,66,68,72,76,82,90,96]},{"label":"ap-south-1","color":"warn","values":[48,56,62,66,68,72,76,80,84,88,92,96,100,108,116,124,132,140,148,156,168,180,192,206]}],"k":"chart"}}
```

### type: density {#chart-density}

Gauss KDE ile yumuşatılmış histogram. Kutu sınırı yapaylıkları olmadan histogram gibi okunur. Varsayılan bant genişliği Silverman kuralıdır; daha dar ya da daha yumuşak eğriler için bandwidth ile değiştirin.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"density\",\n  \"title\": \"Response time density\",\n  \"values\": [\n    120,\n    130,\n    145,\n    150,\n    155,\n    160,\n    162,\n    168,\n    170,\n    172,\n    175,\n    178,\n    180,\n    180,\n    183,\n    188,\n    190,\n    195,\n    200,\n    210,\n    215,\n    225,\n    240,\n    260,\n    290,\n    340,\n    400,\n    520,\n    150,\n    165,\n    180,\n    195,\n    220\n  ]\n}","lang":"json"},"output":{"type":"density","title":"Yanıt süresi yoğunluğu","values":[120,130,145,150,155,160,162,168,170,172,175,178,180,180,183,188,190,195,200,210,215,225,240,260,290,340,400,520,150,165,180,195,220],"k":"chart"}}
```

### type: violin {#chart-violin}

Çekirdek yoğunluğuna dayalı box-plot alternatifi. Dağılım başına aynalanmış yoğunluk eğrisi (keman gövdesi) + IQR dikdörtgeni + ortanca çizgisi. Box-plot yalnızca çeyreklikleri gösterirken bu hem biçimi HEM de çeyreklikleri gösterir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"violin\",\n  \"title\": \"Latency by region\",\n  \"distributions\": [\n    {\n      \"label\": \"us-east\",\n      \"color\": \"accent\",\n      \"values\": [\n        120,\n        125,\n        128,\n        130,\n        135,\n        138,\n        140,\n        142,\n        145,\n        148,\n        150,\n        150,\n        155,\n        160,\n        162,\n        168,\n        170,\n        175,\n        180,\n        200\n      ]\n    },\n    {\n      \"label\": \"eu-west\",\n      \"color\": \"success\",\n      \"values\": [\n        80,\n        82,\n        85,\n        90,\n        92,\n        95,\n        98,\n        100,\n        102,\n        105,\n        108,\n        110,\n        110,\n        112,\n        115,\n        118,\n        120,\n        125,\n        130,\n        140\n      ]\n    },\n    {\n      \"label\": \"ap-south\",\n      \"color\": \"warn\",\n      \"values\": [\n        200,\n        210,\n        215,\n        220,\n        225,\n        230,\n        235,\n        240,\n        245,\n        248,\n        250,\n        252,\n        255,\n        260,\n        270,\n        280,\n        290,\n        310,\n        340,\n        400\n      ]\n    }\n  ]\n}","lang":"json"},"output":{"type":"violin","title":"Bölgeye göre gecikme","distributions":[{"label":"us-east","color":"accent","values":[120,125,128,130,135,138,140,142,145,148,150,150,155,160,162,168,170,175,180,200]},{"label":"eu-west","color":"success","values":[80,82,85,90,92,95,98,100,102,105,108,110,110,112,115,118,120,125,130,140]},{"label":"ap-south","color":"warn","values":[200,210,215,220,225,230,235,240,245,248,250,252,255,260,270,280,290,310,340,400]}],"k":"chart"}}
```

### type: beeswarm {#chart-beeswarm}

Tek eksenli dağılımın, veri noktası başına bir tane olmak üzere kaydırılmış noktalarla çizimi. Dikey yerleşim kuvvet dengesiyle bulunur, böylece herhangi bir x konumundaki nokta yoğunluğu sayıyı görsel olarak kodlar. Küçük örneklemlerde histogramdan daha dürüst okunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"beeswarm\",\n  \"title\": \"Survey scores\",\n  \"values\": [\n    3,\n    5,\n    4,\n    6,\n    7,\n    8,\n    7,\n    6,\n    7,\n    8,\n    8,\n    9,\n    7,\n    6,\n    5,\n    6,\n    7,\n    8,\n    9,\n    8,\n    7,\n    6,\n    7,\n    8,\n    9,\n    5,\n    4,\n    6,\n    7,\n    8,\n    7,\n    8,\n    9,\n    10,\n    7,\n    8,\n    6,\n    5,\n    7,\n    8\n  ]\n}","lang":"json"},"output":{"type":"beeswarm","title":"Anket puanları","values":[3,5,4,6,7,8,7,6,7,8,8,9,7,6,5,6,7,8,9,8,7,6,7,8,9,5,4,6,7,8,7,8,9,10,7,8,6,5,7,8],"k":"chart"}}
```

### type: hexbin {#chart-hexbin}

Çizim alanını altıgen hücrelerle döşer; her hücrenin donukluğu içine kaç `points[]` düştüğünü kodlar. Saçılımın üst üste bineceği durumlarda kullanın — tek tek noktaların anlamını yitirdiği ve yalnızca yoğunluğun önemli olduğu 10⁴ ve üzeri örneklem. `radius` hücre boyutunu viewBox pikseli cinsinden belirler; küçüldükçe çözünürlük artar ama gürültü de artar; büyüdükçe harita yumuşar ama yerel ayrıntı kaybolur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"hexbin\",\n  \"title\": \"Sample density\",\n  \"radius\": 16,\n  \"points\": [\n    {\"x\": 1.1, \"y\": 2.4},\n    {\"x\": 1.5, \"y\": 2.9},\n    {\"x\": 2.2, \"y\": 3.1}\n  ]\n}","lang":"json"},"output":{"type":"hexbin","title":"Örnek yoğunluğu (n ≈ 600)","radius":16,"points":[{"x":1.1,"y":2.4},{"x":1.5,"y":2.9},{"x":1.3,"y":2.7},{"x":1.2,"y":2.5},{"x":1.4,"y":2.8},{"x":1.0,"y":2.6},{"x":1.6,"y":2.3},{"x":1.1,"y":2.6},{"x":1.5,"y":2.5},{"x":1.3,"y":2.4},{"x":1.4,"y":2.6},{"x":1.2,"y":2.7},{"x":2.0,"y":3.0},{"x":2.2,"y":3.1},{"x":2.1,"y":3.2},{"x":2.3,"y":3.0},{"x":2.0,"y":3.3},{"x":2.4,"y":3.1},{"x":3.2,"y":3.6},{"x":3.0,"y":3.7},{"x":3.4,"y":3.5},{"x":3.1,"y":3.4},{"x":3.3,"y":3.7},{"x":3.2,"y":3.5},{"x":4.5,"y":4.2},{"x":4.7,"y":4.0},{"x":4.6,"y":4.4},{"x":4.4,"y":4.3},{"x":4.5,"y":4.1},{"x":4.8,"y":4.2},{"x":4.6,"y":4.0},{"x":4.5,"y":4.3},{"x":4.7,"y":4.4},{"x":5.2,"y":4.8},{"x":5.4,"y":4.7},{"x":5.0,"y":4.9},{"x":5.1,"y":4.8},{"x":5.3,"y":4.6},{"x":5.5,"y":4.7},{"x":6.0,"y":5.4},{"x":6.2,"y":5.3},{"x":6.1,"y":5.5},{"x":6.3,"y":5.2},{"x":6.4,"y":5.4},{"x":6.0,"y":5.6},{"x":0.6,"y":1.0},{"x":0.5,"y":1.2},{"x":0.4,"y":1.1},{"x":0.7,"y":0.9},{"x":0.6,"y":1.1},{"x":0.5,"y":1.0}],"k":"chart"}}
```

## Zaman içinde eğilim {#family-trend}

X ekseninde sıra, y ekseninde değer. Metin içi mikro eğilimler için sparkline; önce/sonra çiftleri için slope; yılın günü × haftanın günü etkinliği için calendar-heatmap.

### type: sparkline {#chart-sparkline}

Satır içi küçük çizgi / alan / çubuk. Eksen yok, çerçeve yok — çevresindeki metnin satır yüksekliğine göre boyutlanır. `values` düz bir sayı dizisidir. `variant` line (varsayılan), area (dolu) ya da bar (değer başına mini çubuk) seçer. `end_label` eğrinin sağında küçük bir açıklama olarak çizilir (`%62`, `↗` gibi).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"sparkline\",\n  \"values\": [12,14,18,17,22,25,28,31,30,35],\n  \"variant\": \"area\",\n  \"end_label\": \"35\"\n}","lang":"json"},"output":{"type":"sparkline","values":[12,14,18,17,22,25,28,31,30,35,33,38],"variant":"area","end_label":"↗ 38","k":"chart"}}
```

Sütun türevi — aynı düz `values` yükü, değer başına mini çubuklar için `"variant": "bar"` verin. Her değer sürekli bir eğilim değil de ayrık bir olay olduğunda kullanın (gün başına sayım, dakika başına istek).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"sparkline\",\n  \"values\": [4, 8, 12, 9, 14, 6, 11, 8],\n  \"variant\": \"bar\",\n  \"end_label\": \"11 events\"\n}","lang":"json"},"output":{"type":"sparkline","values":[4,8,12,9,14,6,11,8],"variant":"bar","end_label":"11 olay","k":"chart"}}
```

### type: slope {#chart-slope}

İki zaman noktası arasındaki değişim — sol sütun `from`, sağ sütun `to`, `items[]` girdisi başına bir eğim çizgisi. Açık bir `color` verilmedikçe renderer yükselenleri success, düşenleri danger rengiyle boyar. Soru 'kim yükseldi, kim düştü' olduğunda bunu kullanın.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"slope\",\n  \"title\": \"Page-load p95 (ms) — before / after CDN\",\n  \"from_label\": \"Before\",\n  \"to_label\":   \"After\",\n  \"items\": [\n    { \"label\": \"/home\",      \"from\": 1400, \"to\":  680 },\n    { \"label\": \"/dashboard\", \"from\": 2200, \"to\": 1100 },\n    { \"label\": \"/settings\",  \"from\":  900, \"to\": 1500 }\n  ]\n}","lang":"json"},"output":{"type":"slope","title":"Sayfa yükleme p95 (ms) — CDN öncesi / sonrası","from_label":"Önce","to_label":"Sonra","items":[{"label":"/home","from":1400,"to":680},{"label":"/dashboard","from":2200,"to":1100},{"label":"/settings","from":900,"to":1500}],"k":"chart"}}
```

### type: calendar-heatmap {#chart-calendar-heatmap}

Yılı hücrelere döken etkinlik ızgarası. `date_values`, ISO tarihinden sayısal değere bir eşlemedir; eşlemede olmayan günler takvimin biçimini göstermek için soluk çizilir. Solda Pzt, Çar, Cum etiketleri; üstte her ayın ilk hücresinde ay adı.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"calendar-heatmap\",\n  \"title\": \"Commits in 2026\",\n  \"year\": 2026,\n  \"date_values\": {\n    \"2026-01-04\": 3, \"2026-01-12\": 9,\n    \"2026-03-22\": 14, \"2026-07-01\": 6,\n    \"2026-11-15\": 11, \"2026-12-30\": 4\n  }\n}","lang":"json"},"output":{"type":"calendar-heatmap","title":"2026'daki işlemeler (örnek)","year":2026,"date_values":{"2026-01-04":3,"2026-01-12":9,"2026-01-18":6,"2026-02-03":8,"2026-02-17":12,"2026-02-28":5,"2026-03-08":14,"2026-03-22":17,"2026-03-30":9,"2026-04-11":6,"2026-04-25":10,"2026-05-09":13,"2026-05-22":22,"2026-06-15":8,"2026-07-04":4,"2026-08-19":11,"2026-09-30":7,"2026-10-12":9,"2026-11-15":16,"2026-11-29":4,"2026-12-22":6},"k":"chart"}}
```

### type: candlestick {#chart-candlestick}

Finansal OHLC. Her girdi bir işlem dönemidir; yükselen günler (kapanış ≥ açılış) success renginde, düşen günler danger renginde. Gövde açılıştan kapanışa, fitil en düşükten en yükseğe.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"candlestick\",\n  \"title\": \"Daily price action\",\n  \"entries\": [\n    {\n      \"date\": \"Mon\",\n      \"open\": 100,\n      \"high\": 108,\n      \"low\": 98,\n      \"close\": 105\n    },\n    {\n      \"date\": \"Tue\",\n      \"open\": 105,\n      \"high\": 112,\n      \"low\": 102,\n      \"close\": 110\n    },\n    {\n      \"date\": \"Wed\",\n      \"open\": 110,\n      \"high\": 115,\n      \"low\": 99,\n      \"close\": 101\n    },\n    {\n      \"date\": \"Thu\",\n      \"open\": 101,\n      \"high\": 104,\n      \"low\": 92,\n      \"close\": 94\n    },\n    {\n      \"date\": \"Fri\",\n      \"open\": 94,\n      \"high\": 102,\n      \"low\": 92,\n      \"close\": 100\n    }\n  ]\n}","lang":"json"},"output":{"type":"candlestick","title":"Günlük fiyat hareketi","entries":[{"date":"Pzt","open":100,"high":108,"low":98,"close":105},{"date":"Sal","open":105,"high":112,"low":102,"close":110},{"date":"Çar","open":110,"high":115,"low":99,"close":101},{"date":"Per","open":101,"high":104,"low":92,"close":94},{"date":"Cum","open":94,"high":102,"low":92,"close":100}],"k":"chart"}}
```

### type: stream {#chart-stream}

Ortalanmış yığılmış alan. Her katman alttan yığılmak yerine x ekseni üzerinde ortalanır. Toplamın değiştiği bileşim eğilimlerini göstermek için elverişlidir; ortalanmış biçim akan bir dere gibi okunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"stream\",\n  \"title\": \"Page views by source\",\n  \"categories\": [\n    \"W1\",\n    \"W2\",\n    \"W3\",\n    \"W4\",\n    \"W5\",\n    \"W6\",\n    \"W7\",\n    \"W8\"\n  ],\n  \"series\": [\n    {\n      \"label\": \"direct\",\n      \"values\": [\n        60,\n        80,\n        75,\n        90,\n        110,\n        120,\n        100,\n        95\n      ]\n    },\n    {\n      \"label\": \"organic\",\n      \"values\": [\n        40,\n        55,\n        70,\n        85,\n        90,\n        95,\n        110,\n        130\n      ]\n    },\n    {\n      \"label\": \"referral\",\n      \"values\": [\n        20,\n        30,\n        28,\n        45,\n        55,\n        60,\n        70,\n        80\n      ]\n    }\n  ]\n}","lang":"json"},"output":{"type":"stream","title":"Kaynağa göre sayfa görüntüleme","categories":["H1","H2","H3","H4","H5","H6","H7","H8"],"series":[{"label":"doğrudan","values":[60,80,75,90,110,120,100,95]},{"label":"organik","values":[40,55,70,85,90,95,110,130]},{"label":"yönlendirme","values":[20,30,28,45,55,60,70,80]}],"k":"chart"}}
```

### type: bump {#chart-bump}

Y ekseninin değer yerine SIRA olduğu çizgi grafiği. Her seri kategoriler boyunca sıralanır; lider tablosu değiştiğinde çizgiler kesişir. 'Her yıl bir numara kimdi' — beğeni kayması, pazar payı liderleri, spor sıralamaları.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"bump\",\n  \"title\": \"Top-3 cities by visits\",\n  \"categories\": [\n    \"2020\",\n    \"2021\",\n    \"2022\",\n    \"2023\",\n    \"2024\"\n  ],\n  \"series\": [\n    {\n      \"label\": \"Berlin\",\n      \"values\": [\n        80,\n        75,\n        90,\n        95,\n        92\n      ]\n    },\n    {\n      \"label\": \"Lisbon\",\n      \"values\": [\n        70,\n        85,\n        75,\n        80,\n        88\n      ]\n    },\n    {\n      \"label\": \"Krakow\",\n      \"values\": [\n        60,\n        70,\n        80,\n        65,\n        75\n      ]\n    },\n    {\n      \"label\": \"Tallinn\",\n      \"values\": [\n        40,\n        50,\n        60,\n        70,\n        80\n      ]\n    }\n  ]\n}","lang":"json"},"output":{"type":"bump","title":"Ziyarete göre ilk 3 şehir","categories":["2020","2021","2022","2023","2024"],"series":[{"label":"Berlin","values":[80,75,90,95,92]},{"label":"Lizbon","values":[70,85,75,80,88]},{"label":"Krakov","values":[60,70,80,65,75]},{"label":"Tallinn","values":[40,50,60,70,80]}],"k":"chart"}}
```

### type: horizon {#chart-horizon}

Sıkıştırılmış zaman serisi. Her `series` ince bir şeride dönüşür; değerler taban çizgisinin üstünde gitgide koyulaşan bantlara katlanır, böylece 36 px'lik bir şerit 200 px'lik bir çizgi grafiğiyle aynı bilgiyi taşıyabilir. Dikeyde üst üste dizilmiş çok sayıda zaman serisini karşılaştırmak için kullanın — bölge başına sunucu yükü, uç nokta başına gecikme — yani seri başına biçimin mutlak piksel yüksekliğinden daha önemli olduğu durumlar. `bands` (varsayılan 3) katlamanın aralığı ne kadar sıkıştıracağını belirler.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"horizon\",\n  \"title\": \"Request rate (req/s) by region\",\n  \"bands\": 3,\n  \"categories\": [\"00:00\", \"04:00\", \"08:00\", \"12:00\", \"16:00\", \"20:00\"],\n  \"series\": [\n    { \"label\": \"us-east-1\", \"color\": \"accent\",  \"values\": [120, 140, 380, 620, 540, 290] },\n    { \"label\": \"eu-west-1\", \"color\": \"success\", \"values\": [ 80, 110, 220, 410, 600, 380] },\n    { \"label\": \"ap-south-1\",\"color\": \"warn\",    \"values\": [340, 480, 510, 360, 240, 180] }\n  ]\n}","lang":"json"},"output":{"type":"horizon","title":"Bölgeye göre istek hızı (istek/sn)","bands":3,"categories":["00:00","04:00","08:00","12:00","16:00","20:00"],"series":[{"label":"us-east-1","color":"accent","values":[120,140,380,620,540,290]},{"label":"eu-west-1","color":"success","values":[80,110,220,410,600,380]},{"label":"ap-south-1","color":"warn","values":[340,480,510,360,240,180]}],"k":"chart"}}
```

## Akış / dönüşüm {#family-flow}

Bir miktarın aşamalar ya da kaynaklar arasında nasıl hareket ettiği. Sıralı düşüş için funnel; herhangi iki düğüm arasındaki serbest ağırlıklı akışlar için sankey.

### type: funnel {#chart-funnel}

Dönüşüm aşamalarındaki düşüş. `stages[]`, `{label, value, color?}` nesnelerinden oluşan sıralı bir listedir. Renderer komşu aşamalar arasına daralan bir bant çizer; sağdaki okuma değeri ve ilk aşamaya oranını gösterir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"funnel\",\n  \"title\": \"Signup conversion\",\n  \"stages\": [\n    {\"label\": \"Visitors\",   \"value\": 1000},\n    {\"label\": \"Signed up\",  \"value\":  680},\n    {\"label\": \"Activated\",  \"value\":  430},\n    {\"label\": \"Upgraded\",   \"value\":  180},\n    {\"label\": \"Retained 30d\",\"value\":  120}\n  ]\n}","lang":"json"},"output":{"type":"funnel","title":"Kayıt dönüşümü","stages":[{"label":"Ziyaretçiler","value":1000,"color":"muted"},{"label":"Kaydolanlar","value":680,"color":"accent"},{"label":"Etkinleşenler","value":430,"color":"accent"},{"label":"Yükseltenler","value":180,"color":"warn"},{"label":"30 gün kalanlar","value":120,"color":"success"}],"k":"chart"}}
```

### type: sankey {#chart-sankey}

Aşamalar arasında, bağ değerine göre kalınlaşan eğrisel şeritlerle akış. `nodes[]` `{id, label?, color?}`, `links[]` ise düğüm kimliklerine gönderme yapan `{source, target, value}` biçimindedir. Renderer soldan sağa sütun yerleşimini bağ grafiğinden türetir (BFS derinliği), her sütun içindeki düğümleri gelen ya da giden toplamlarına göre yığar ve her çift arasına kübik Bezier şeridi çizer.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"sankey\",\n  \"title\": \"Where time goes\",\n  \"nodes\": [\n    {\"id\": \"source\",  \"label\": \"Working hours\", \"color\": \"muted\"},\n    {\"id\": \"build\",   \"label\": \"Shipping\",   \"color\": \"accent\"},\n    {\"id\": \"plan\",    \"label\": \"Planning\",   \"color\": \"accent\"},\n    {\"id\": \"meet\",    \"label\": \"Meetings\",   \"color\": \"warn\"},\n    {\"id\": \"code\",    \"label\": \"Code\",       \"color\": \"success\"},\n    {\"id\": \"review\",  \"label\": \"Review\",     \"color\": \"success\"},\n    {\"id\": \"docs\",    \"label\": \"Docs\",       \"color\": \"accent\"}\n  ],\n  \"links\": [\n    {\"source\": \"source\", \"target\": \"build\",  \"value\": 24},\n    {\"source\": \"source\", \"target\": \"plan\",   \"value\":  9},\n    {\"source\": \"source\", \"target\": \"meet\",   \"value\":  7},\n    {\"source\": \"build\",  \"target\": \"code\",   \"value\": 14},\n    {\"source\": \"build\",  \"target\": \"review\", \"value\":  6},\n    {\"source\": \"build\",  \"target\": \"docs\",   \"value\":  4},\n    {\"source\": \"plan\",   \"target\": \"docs\",   \"value\":  3}\n  ]\n}","lang":"json"},"output":{"type":"sankey","title":"Zaman nereye gidiyor","nodes":[{"id":"source","label":"Çalışma saatleri","color":"muted"},{"id":"build","label":"Yayımlama","color":"accent"},{"id":"plan","label":"Planlama","color":"accent"},{"id":"meet","label":"Toplantılar","color":"warn"},{"id":"code","label":"Kod","color":"success"},{"id":"review","label":"İnceleme","color":"success"},{"id":"docs","label":"Belgeler","color":"accent"}],"links":[{"source":"source","target":"build","value":24},{"source":"source","target":"plan","value":9},{"source":"source","target":"meet","value":7},{"source":"build","target":"code","value":14},{"source":"build","target":"review","value":6},{"source":"build","target":"docs","value":4},{"source":"plan","target":"docs","value":3}],"k":"chart"}}
```

### type: gantt {#chart-gantt}

Zaman ekseni üzerinde, iş başına bir tane olmak üzere yatay çubuklar. Proje takvimleri, sürüm planları, yol haritası pencereleri. start / end sayısaldır — birimi yazar seçer (gün, hafta, saat ya da tick_format='date' ile Unix ms).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"gantt\",\n  \"title\": \"Release plan (weeks)\",\n  \"tasks\": [\n    {\n      \"label\": \"Discovery\",\n      \"start\": 0,\n      \"end\": 3,\n      \"color\": \"accent\"\n    },\n    {\n      \"label\": \"Design\",\n      \"start\": 2,\n      \"end\": 6,\n      \"color\": \"accent\"\n    },\n    {\n      \"label\": \"Build\",\n      \"start\": 5,\n      \"end\": 14,\n      \"color\": \"success\"\n    },\n    {\n      \"label\": \"Integrate\",\n      \"start\": 12,\n      \"end\": 16,\n      \"color\": \"warn\"\n    },\n    {\n      \"label\": \"QA + launch\",\n      \"start\": 15,\n      \"end\": 20,\n      \"color\": \"danger\"\n    }\n  ]\n}","lang":"json"},"output":{"type":"gantt","title":"Sürüm planı (hafta)","tasks":[{"label":"Keşif","start":0,"end":3,"color":"accent"},{"label":"Tasarım","start":2,"end":6,"color":"accent"},{"label":"Yapım","start":5,"end":14,"color":"success"},{"label":"Bütünleme","start":12,"end":16,"color":"warn"},{"label":"Test + yayım","start":15,"end":20,"color":"danger"}],"k":"chart"}}
```

## Ağ / ilişki {#family-network}

Düğümler arasındaki kenarlar. Serbest biçimli çizgeler için network (kuvvetle gevşetilmiş yerleşim); tümü bağlı yönlü akış matrisleri için chord.

### type: network {#chart-network}

Küçük bir Fruchterman-Reingold benzeri kuvvet gevşetmesiyle (her çizimde ~60 yineleme) düğüm-bağ şeması. ~50 düğüme kadar olan çizgeler için uygundur — daha büyük yapılar gerçek bir çizge görselleştirme kütüphanesi ister. `nodes[]` + `links[]` `sankey` ile aynı biçimdedir. Düğüm yarıçapı derece ile ölçeklenir; bir düğümün üzerine gelmek bilgi balonunda etiketini ve derecesini açar.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"network\",\n  \"title\": \"Pages link graph\",\n  \"nodes\": [\n    {\"id\": \"index\"},     {\"id\": \"reference\"},  {\"id\": \"glossary\"},\n    {\"id\": \"architecture\"}, {\"id\": \"cli\"},   {\"id\": \"roadmap\"}\n  ],\n  \"links\": [\n    {\"source\": \"index\", \"target\": \"reference\"},\n    {\"source\": \"index\", \"target\": \"glossary\"},\n    {\"source\": \"index\", \"target\": \"architecture\"},\n    {\"source\": \"index\", \"target\": \"cli\"},\n    {\"source\": \"index\", \"target\": \"roadmap\"},\n    {\"source\": \"reference\", \"target\": \"glossary\"},\n    {\"source\": \"reference\", \"target\": \"architecture\"},\n    {\"source\": \"architecture\", \"target\": \"cli\"}\n  ]\n}","lang":"json"},"output":{"type":"network","title":"Sayfa bağlantı çizgesi","nodes":[{"id":"index"},{"id":"reference"},{"id":"glossary"},{"id":"architecture"},{"id":"cli"},{"id":"roadmap"}],"links":[{"source":"index","target":"reference"},{"source":"index","target":"glossary"},{"source":"index","target":"architecture"},{"source":"index","target":"cli"},{"source":"index","target":"roadmap"},{"source":"reference","target":"glossary"},{"source":"reference","target":"architecture"},{"source":"architecture","target":"cli"}],"k":"chart"}}
```

### type: chord {#chart-chord}

Dairesel ilişki şeması. `groups[]` çevre sırasını tanımlar (saat 12'den başlayarak saat yönünde); `matrix` ise `matrix[i][j]` değerinin `groups[i]` öğesinden `groups[j]` öğesine akışı verdiği N×N'lik bir akış matrisidir. Her grup, toplam giren+çıkan akışıyla orantılı bir dış yay kaplar; merkezden geçen şeritler ikili akışları taşır.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"chord\",\n  \"title\": \"Cross-team handoffs (this week)\",\n  \"groups\": [\n    {\"id\": \"design\",  \"color\": \"accent\"},\n    {\"id\": \"eng\",     \"color\": \"success\"},\n    {\"id\": \"product\", \"color\": \"warn\"},\n    {\"id\": \"docs\",    \"color\": \"muted\"}\n  ],\n  \"matrix\": [\n    [0, 8, 3, 2],\n    [4, 0, 5, 6],\n    [2, 7, 0, 1],\n    [3, 4, 1, 0]\n  ]\n}","lang":"json"},"output":{"type":"chord","title":"Ekipler arası devirler (bu hafta)","groups":[{"id":"design","color":"accent"},{"id":"eng","color":"success"},{"id":"product","color":"warn"},{"id":"docs","color":"muted"}],"matrix":[[0,8,3,2],[4,0,5,6],[2,7,0,1],[3,4,1,0]],"k":"chart"}}
```

### type: arc-diagram {#chart-arc-diagram}

Yatay bir taban çizgisine eşit aralıklarla yerleştirilmiş düğümler; her bağ, kaynağını ve hedefini birleştiren yarım daire biçiminde bir yayı taban çizgisinin üstüne çizer. `network`/`sankey` ile aynı `nodes` + `links` yükü — değişen tek şey yerleşimdir. Düğümlerin *sırası* anlam taşıdığında (soyağacı, kronoloji, cümle içinde sözcük komşuluğu) ve kuvvetle gevşetilmiş bir ağ bu sırayı gizleyeceğinde kullanın. Yay kalınlığı `links[].value` ile ölçeklenir; yay rengi kaynak düğümün renk değişkenini izler.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"arc-diagram\",\n  \"title\": \"Talk references (in slide order)\",\n  \"nodes\": [\n    {\"id\": \"intro\",       \"label\": \"Intro\"},\n    {\"id\": \"problem\",     \"label\": \"Problem\"},\n    {\"id\": \"prior\",       \"label\": \"Prior work\"},\n    {\"id\": \"method\",      \"label\": \"Method\",   \"color\": \"success\"},\n    {\"id\": \"results\",     \"label\": \"Results\",  \"color\": \"warn\"},\n    {\"id\": \"discussion\",  \"label\": \"Discussion\"},\n    {\"id\": \"conclusion\",  \"label\": \"Conclusion\"}\n  ],\n  \"links\": [\n    {\"source\": \"intro\",       \"target\": \"problem\",    \"value\": 2},\n    {\"source\": \"problem\",     \"target\": \"prior\",      \"value\": 4},\n    {\"source\": \"problem\",     \"target\": \"method\",     \"value\": 6},\n    {\"source\": \"prior\",       \"target\": \"method\",     \"value\": 3},\n    {\"source\": \"method\",      \"target\": \"results\",    \"value\": 8},\n    {\"source\": \"results\",     \"target\": \"discussion\", \"value\": 5},\n    {\"source\": \"discussion\",  \"target\": \"conclusion\", \"value\": 3},\n    {\"source\": \"prior\",       \"target\": \"discussion\", \"value\": 2}\n  ]\n}","lang":"json"},"output":{"type":"arc-diagram","title":"Sunum göndermeleri (slayt sırasıyla)","nodes":[{"id":"intro","label":"Giriş"},{"id":"problem","label":"Problem"},{"id":"prior","label":"Önceki çalışmalar"},{"id":"method","label":"Yöntem","color":"success"},{"id":"results","label":"Sonuçlar","color":"warn"},{"id":"discussion","label":"Tartışma"},{"id":"conclusion","label":"Vargı"}],"links":[{"source":"intro","target":"problem","value":2},{"source":"problem","target":"prior","value":4},{"source":"problem","target":"method","value":6},{"source":"prior","target":"method","value":3},{"source":"method","target":"results","value":8},{"source":"results","target":"discussion","value":5},{"source":"discussion","target":"conclusion","value":3},{"source":"prior","target":"discussion","value":2}],"k":"chart"}}
```

## Çok değişkenli / matris {#family-matrix}

Kayıt başına ikiden çok boyut. Değere göre renklenen iki boyutlu ızgara için heatmap; N değişken arasında ikili saçılımlar için scatter-matrix; N ekseni kesen kayıt başına çoklu çizgiler için parallel-coordinates.

### type: heatmap {#chart-heatmap}

Değere göre renklenen N×M hücre ızgarası. `cells` iki boyutlu bir dizidir (dış = satırlar, iç = sütunlar). İsteğe bağlı `row_labels` / `col_labels` kenarları etiketler. `scale` palet ailesini seçer: sequential (vurgu rengi üzerinde tek yönlü rampa) ya da diverging (artılar için vurgu, eksiler için danger). Ham değer için herhangi bir hücrenin üzerine gelin.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"heatmap\",\n  \"title\": \"Latency by service × hour\",\n  \"row_labels\": [\"svc-a\", \"svc-b\", \"svc-c\"],\n  \"col_labels\": [\"00\", \"06\", \"12\", \"18\"],\n  \"cells\": [[12,18,42,30],[8,22,36,24],[40,50,28,16]]\n}","lang":"json"},"output":{"type":"heatmap","title":"Servis × saate göre gecikme","row_labels":["svc-a","svc-b","svc-c","svc-d"],"col_labels":["00","04","08","12","16","20"],"cells":[[12,18,26,42,30,18],[8,22,36,24,16,10],[40,50,28,16,12,8],[6,12,18,24,38,50]],"k":"chart"}}
```

### type: scatter-matrix {#chart-scatter-matrix}

Çok değişkenli bağıntı okuması için N×N'lik mini saçılım ızgarası. `variables[]` her ekseni tanımlar; `records[]` ise değişken kimliğine göre anahtarlanmış nesnelerden oluşan düz bir listedir. Tanım aralıkları açıkça bildirilmedikçe kayıtlardan türetilir.

> [!TIP] Nasıl okunur
> Köşegen hücreler (sol üstten sağ alta) her değişkeni adlandırır. Köşegen dışı hücreler sütun değişkenini X'te, satır değişkenini Y'de çizer. Her hücrenin sol üstünde bir `r=` çipi durur — iki değişken arasındaki Pearson bağıntısı (-1 ile +1 arası). `|r| ≥ 0.7` olan değerler koyu vurguyla görünür: incelemeye değer güçlü ilişkiler bunlardır. Çifti, n'i ve r'yi bilgi balonunda görmek için köşegen dışı herhangi bir hücrenin üzerine gelin; sabitlemek için tıklayın.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"scatter-matrix\",\n  \"title\": \"Page metrics\",\n  \"variables\": [\n    {\"key\": \"lines\",   \"label\": \"Lines\"},\n    {\"key\": \"images\",  \"label\": \"Images\"},\n    {\"key\": \"charts\",  \"label\": \"Charts\"},\n    {\"key\": \"reads\",   \"label\": \"Reads\"}\n  ],\n  \"records\": [\n    {\"lines\":  320, \"images\":  4, \"charts\":  2, \"reads\":  120},\n    {\"lines\":  180, \"images\":  2, \"charts\":  0, \"reads\":   60},\n    ... 20 more rows ...\n  ]\n}","lang":"json"},"output":{"type":"scatter-matrix","title":"Sayfa ölçümleri","variables":[{"key":"lines","label":"Satır"},{"key":"images","label":"Görsel"},{"key":"charts","label":"Grafik"},{"key":"reads","label":"Okuma"}],"records":[{"lines":320,"images":4,"charts":2,"reads":120},{"lines":180,"images":2,"charts":0,"reads":60},{"lines":540,"images":7,"charts":5,"reads":210},{"lines":90,"images":1,"charts":0,"reads":40},{"lines":410,"images":5,"charts":3,"reads":160},{"lines":260,"images":3,"charts":2,"reads":90},{"lines":720,"images":9,"charts":8,"reads":310},{"lines":150,"images":1,"charts":1,"reads":55},{"lines":380,"images":4,"charts":3,"reads":140},{"lines":510,"images":6,"charts":4,"reads":180},{"lines":220,"images":2,"charts":1,"reads":80},{"lines":470,"images":5,"charts":4,"reads":190}],"k":"chart"}}
```

### type: parallel-coordinates {#chart-parallel-coordinates}

Değişken başına bir dikey eksen; her kayıt, ölçeklenmiş konumundan geçerek bütün eksenleri kesen bir çoklu çizgi çizer. Çok değişkenli kümeleri (birbirine yaklaşan çizgiler) ya da aykırı değerleri (ayrışan çizgiler) yakalamak için en uygunudur. Her kayıttaki isteğe bağlı `_label` ve `_color` onu görsel olarak işaretler.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"parallel-coordinates\",\n  \"title\": \"Build performance\",\n  \"variables\": [\n    {\"key\": \"pages\",     \"label\": \"Pages\"},\n    {\"key\": \"size_kb\",   \"label\": \"Total KB\"},\n    {\"key\": \"build_ms\",  \"label\": \"Build ms\"},\n    {\"key\": \"lighthouse\",\"label\": \"Lighthouse\"}\n  ],\n  \"records\": [\n    {\"pages\":  10, \"size_kb\":  240, \"build_ms\":  900, \"lighthouse\": 96, \"_color\": \"success\"},\n    {\"pages\":  25, \"size_kb\":  540, \"build_ms\": 1400, \"lighthouse\": 94, \"_color\": \"accent\"},\n    ...\n  ]\n}","lang":"json"},"output":{"type":"parallel-coordinates","title":"Derleme başarımı","variables":[{"key":"pages","label":"Sayfa"},{"key":"size_kb","label":"Toplam KB"},{"key":"build_ms","label":"Derleme ms"},{"key":"lighthouse","label":"Lighthouse"}],"records":[{"pages":10,"size_kb":240,"build_ms":900,"lighthouse":96,"_color":"success"},{"pages":25,"size_kb":540,"build_ms":1400,"lighthouse":94,"_color":"accent"},{"pages":40,"size_kb":920,"build_ms":2300,"lighthouse":91,"_color":"accent"},{"pages":60,"size_kb":1500,"build_ms":3800,"lighthouse":88,"_color":"warn"},{"pages":90,"size_kb":2400,"build_ms":6500,"lighthouse":82,"_color":"warn"},{"pages":130,"size_kb":3800,"build_ms":11200,"lighthouse":74,"_color":"danger"}],"k":"chart"}}
```

## Hedef / ilerleme {#family-goal}

Bir değerin bilinen bir aralığın neresinde durduğu (çoğu zaman bir hedefle birlikte). Tek yay için gauge; bölge bantlarıyla gerçekleşen-hedef karşılaştırması için bullet; çok eksenli profil karşılaştırması için radar.

### type: gauge {#chart-gauge}

0 → max arası yarım daire yay; güncel değerde bir ibre / dolgu ve isteğe bağlı bir hedef çentiği. Hedefe olan uzaklığın asıl mesele olduğu tek ölçümlü durum göstergeleri (SLO bütçesi, nakit ömrü, çalışma süresi) için kullanın. İsteğe bağlı `zones`, değerin arkasına renkli eşik bantları boyar.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"gauge\",\n  \"title\": \"SLO budget\",\n  \"value\": 92,\n  \"max\": 100,\n  \"target\": 80,\n  \"label\": \"of monthly window remaining\",\n  \"zones\": [\n    { \"from\":  0, \"to\": 50, \"tone\": \"danger\",  \"label\": \"breaching\" },\n    { \"from\": 50, \"to\": 80, \"tone\": \"warn\",    \"label\": \"caution\"   },\n    { \"from\": 80, \"to\": 100,\"tone\": \"success\", \"label\": \"healthy\"   }\n  ]\n}","lang":"json"},"output":{"type":"gauge","title":"SLO bütçesi","value":92,"max":100,"target":80,"label":"aylık pencereden kalan","zones":[{"from":0,"to":50,"tone":"danger","label":"aşımda"},{"from":50,"to":80,"tone":"warn","label":"dikkat"},{"from":80,"to":100,"tone":"success","label":"sağlıklı"}],"k":"chart"}}
```

### type: bullet {#chart-bullet}

Bantlanmış yatay bir yol üzerinde gerçekleşen ile hedefin karşılaştırması — Stephen Few'in bullet grafiği. `tracks[]` girdisi başına bir satır: `label`, `value` (güncel), `target` (isteğe bağlı dikey çentik), `max` (sağ kenar) ve değerin arkasına boyanan isteğe bağlı `zones`.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"bullet\",\n  \"title\": \"Quarter at a glance\",\n  \"tracks\": [\n    { \"label\": \"Revenue ($M)\", \"value\": 92, \"target\": 80, \"max\": 120,\n      \"zones\": [{ \"from\":0, \"to\":40, \"tone\":\"danger\" }, { \"from\":40, \"to\":80, \"tone\":\"warn\" }, { \"from\":80, \"to\":120, \"tone\":\"success\" }] },\n    { \"label\": \"NPS\",          \"value\": 58, \"target\": 65, \"max\": 100, \"color\": \"warn\" }\n  ]\n}","lang":"json"},"output":{"type":"bullet","title":"Çeyreğe tek bakış","tracks":[{"label":"Gelir ($M)","value":92,"target":80,"max":120,"color":"success","zones":[{"from":0,"to":40,"tone":"danger"},{"from":40,"to":80,"tone":"warn"},{"from":80,"to":120,"tone":"success"}]},{"label":"NPS","value":58,"target":65,"max":100,"color":"warn","zones":[{"from":0,"to":30,"tone":"danger"},{"from":30,"to":60,"tone":"warn"},{"from":60,"to":100,"tone":"success"}]},{"label":"Kayıp oranı (%)","value":3,"target":5,"max":12,"color":"success"}],"k":"chart"}}
```

### type: radar {#chart-radar}

Merkezden ışıyan N kol, seri başına bir dolu çokgen. 3–8 eksen ve 1–4 seri için en uygunudur. `axes[].label` kolu adlandırır; isteğe bağlı `axes[].max` eksen başına ölçeklemeyi geçersiz kılar. `series[].values` dizisi `axes` ile sıra sıra hizalanmalıdır.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"radar\",\n  \"title\": \"Database shortlist — seven criteria\",\n  \"axes\": [\n    { \"label\": \"Throughput\" },\n    { \"label\": \"Latency p99\" },\n    { \"label\": \"Cost\"     },\n    { \"label\": \"Docs\"     },\n    { \"label\": \"Operability\" },\n    { \"label\": \"Ecosystem\" },\n    { \"label\": \"Recovery\" }\n  ],\n  \"series\": [\n    { \"label\": \"Postgres\",  \"color\": \"accent\",  \"values\": [8, 7, 9, 9, 8, 9, 8] },\n    { \"label\": \"Cassandra\", \"color\": \"success\", \"values\": [9, 8, 6, 6, 5, 7, 6] },\n    { \"label\": \"DynamoDB\",  \"color\": \"warn\",    \"values\": [9, 9, 4, 8, 9, 6, 9] }\n  ]\n}","lang":"json"},"output":{"type":"radar","title":"Veritabanı kısa listesi — yedi ölçüt","axes":[{"label":"İş hacmi"},{"label":"Gecikme p99"},{"label":"Maliyet"},{"label":"Belgeler"},{"label":"İşletilebilirlik"},{"label":"Ekosistem"},{"label":"Kurtarma"}],"series":[{"label":"Postgres","color":"accent","values":[8,7,9,9,8,9,8]},{"label":"Cassandra","color":"success","values":[9,8,6,6,5,7,6]},{"label":"DynamoDB","color":"warn","values":[9,9,4,8,9,6,9]}],"k":"chart"}}
```

## Karo kartogramlar {#family-geo}

Kaba bir dünya karo ızgarasına yerleştirilmiş bölge başına değer. Gerçek bir harita DEĞİLDİR — ülke sınırları çizilmez — ama görsel ritim, bölgeleri tek bakışta karşılaştırmaya yeter. Dürüst adı `tile-map`; `geo` takma ad olarak kalır.

### type: tile-map (takma ad: geo) {#chart-geo}

Karo kartogram. `regions[]`, `id` alanı bir ISO 3166-1 Alpha-2 ülke kodu (US, GB, DE, BR, ...) ya da yapay `OTH` kovası olan `{id, value, label?}` nesnelerinden oluşan bir listedir. Kit, düz bir dünyayı yaklaşıklayan sabit bir karo ızgarasıyla (~60 hücre) gelir; olmayan bölgeler yerleşimin okunması için soluk yer tutucu çerçeveler olarak çizilir. Hücre dolgusu tek renkli sıralı bir rampada değerle ölçeklenir. Bu bilinçli olarak koroplet DEĞİLDİR — ülke sınırı yok, topojson bağımlılığı yok.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"chart\",\n  \"type\": \"geo\",\n  \"title\": \"Site traffic by country (k visits)\",\n  \"regions\": [\n    {\"id\": \"US\", \"value\":  82, \"label\": \"United States\"},\n    {\"id\": \"GB\", \"value\":  18, \"label\": \"United Kingdom\"},\n    {\"id\": \"DE\", \"value\":  24, \"label\": \"Germany\"},\n    {\"id\": \"FR\", \"value\":  11, \"label\": \"France\"},\n    {\"id\": \"BR\", \"value\":  14, \"label\": \"Brazil\"},\n    {\"id\": \"IN\", \"value\":  38, \"label\": \"India\"},\n    {\"id\": \"JP\", \"value\":  21, \"label\": \"Japan\"},\n    {\"id\": \"AU\", \"value\":   9, \"label\": \"Australia\"},\n    {\"id\": \"OTH\",\"value\":  47, \"label\": \"Other\"}\n  ]\n}","lang":"json"},"output":{"type":"geo","title":"Ülkeye göre site trafiği (bin ziyaret)","regions":[{"id":"US","value":82,"label":"Amerika Birleşik Devletleri"},{"id":"CA","value":6,"label":"Kanada"},{"id":"MX","value":4,"label":"Meksika"},{"id":"BR","value":14,"label":"Brezilya"},{"id":"AR","value":3,"label":"Arjantin"},{"id":"GB","value":18,"label":"Birleşik Krallık"},{"id":"FR","value":11,"label":"Fransa"},{"id":"DE","value":24,"label":"Almanya"},{"id":"ES","value":8,"label":"İspanya"},{"id":"IT","value":7,"label":"İtalya"},{"id":"NL","value":5,"label":"Hollanda"},{"id":"SE","value":4,"label":"İsveç"},{"id":"PL","value":6,"label":"Polonya"},{"id":"TR","value":9,"label":"Türkiye"},{"id":"RU","value":4,"label":"Rusya"},{"id":"IN","value":38,"label":"Hindistan"},{"id":"CN","value":22,"label":"Çin"},{"id":"JP","value":21,"label":"Japonya"},{"id":"KR","value":12,"label":"Güney Kore"},{"id":"ID","value":7,"label":"Endonezya"},{"id":"AU","value":9,"label":"Avustralya"},{"id":"ZA","value":3,"label":"Güney Afrika"},{"id":"NG","value":4,"label":"Nijerya"},{"id":"OTH","value":47,"label":"Diğer / eşlenmemiş"}],"k":"chart"}}
```
