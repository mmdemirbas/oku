---
title: Tablolar
eyebrow: Başvuru · tablolar
order: 22
summary: tablo yapı taşı — düz satırlar, gruplanmış satırlar, etiket süzgeçleri, pano / kanban görünümü, yapışkan başlıklar, sütun genişliği ayarı.
parent: reference
---

## Tablo yapı taşı {#tables}

### table {#table}

Birinci sınıf JSON tablosu. İki biçimi vardır: düz `rows` ya da gruplanmış `groups`. Gerçek bir `<table>` olarak işlenir, yanında da bir denetim çubuğu gelir (süzme kutusu, sayaç, Tablo / Liste / Kart görünüm düğmesi, yapışkan başlık, tam genişliğe oturma). Nesne biçiminde yazılan başlıklar ve hücreler, çok değerli hücrelerle çalışan etiket süzgeçleri tanımlar; gruplar katlanabilir. Bir başlığın `status` eşlemesi, o sütunun değerlerini renk kodlu durum rozetlerine çevirir (`good` / `warn` / `bad` / `info` / `neutral`) — eşlemeyi yazar kendi değerleriyle kurduğu için renk dili her dilde aynı kalır.

### Düz satırlar {#tables-flat}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\n    \"Aşama\",\n    { \"label\": \"Durum\",\n      \"status\": { \"done\": \"good\", \"in-progress\": \"warn\", \"queued\": \"neutral\" } },\n    \"Süre\"\n  ],\n  \"rows\": [\n    [\"Planlama\",   \"done\",         \"1 gün\"],\n    [\"Geliştirme\", \"done\",         \"3 gün\"],\n    [\"Test\",       \"in-progress\",  \"2 gün\"],\n    [\"Yayın\",      \"queued\",       \"—\"]\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Aşama",{"label":"Durum","status":{"done":"good","in-progress":"warn","queued":"neutral"}},"Süre"],"rows":[["Planlama","done","1 gün"],["Geliştirme","done","3 gün"],["Test","in-progress","2 gün"],["Yayın","queued","—"]]}}
```

### Grup başına sayımla gruplanmış satırlar {#tables-grouped}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\"Motor\", \"Depolama\", \"Lisans\"],\n  \"groups\": [\n    { \"title\": \"Lakehouse biçimleri\",\n      \"rows\": [\n        [\"Apache Iceberg\", \"Nesne deposu\", \"Apache 2.0\"],\n        [\"Delta Lake\",     \"Nesne deposu\", \"Apache 2.0\"]\n      ]\n    },\n    { \"title\": \"Sorgu motorları\",\n      \"rows\": [[\"Trino\", \"Takılabilir\", \"Apache 2.0\"]]\n    }\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Motor","Depolama","Lisans"],"groups":[{"t":"Lakehouse biçimleri","rows":[["Apache Iceberg","Nesne deposu","Apache 2.0"],["Apache Hudi","Nesne deposu","Apache 2.0"],["Delta Lake","Nesne deposu","Apache 2.0"]]},{"t":"Sorgu motorları","rows":[["Trino","Takılabilir","Apache 2.0"],["Presto","Takılabilir","Apache 2.0"]]}]}}
```

### Etiket süzgeçleri ve çok değerli hücreler {#tables-chips}

Başlıklar `filter: "chips"` ile sabit bir etiket kümesi tanımlayabilir; hücreler de bir ya da birden çok etiket değerine ait olmak için `{ value, values }` nesne biçimini kullanır. Sütunlar arasında VE, bir sütunun içinde VEYA geçerlidir. Metin süzgeciyle birlikte çalışır.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\n    \"Motor\",\n    { \"label\": \"Etiketler\", \"filter\": \"chips\",\n      \"values\": [\"lakehouse\", \"streaming\", \"query\"] },\n    { \"label\": \"Olgunluk\", \"filter\": \"chips\",\n      \"values\": [\"incubating\", \"ga\", \"experimental\"] }\n  ],\n  \"rows\": [\n    [\"Apache Iceberg\",\n      { \"values\": [\"lakehouse\"] },\n      { \"value\": \"GA\", \"values\": [\"ga\"] }],\n    [\"Apache Paimon\",\n      { \"values\": [\"lakehouse\", \"streaming\"] },\n      { \"value\": \"Kuluçkada\", \"values\": [\"incubating\"] }],\n    [\"Trino\",\n      { \"values\": [\"query\"] },\n      { \"value\": \"GA\", \"values\": [\"ga\"] }]\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Motor",{"label":"Etiketler","filter":"chips","values":["lakehouse","streaming","query","metadata"]},{"label":"Olgunluk","filter":"chips","values":["incubating","ga","experimental"]}],"rows":[["Apache Iceberg",{"values":["lakehouse","metadata"]},{"value":"GA","values":["ga"]}],["Apache Hudi",{"values":["lakehouse","streaming"]},{"value":"GA","values":["ga"]}],["Delta Lake",{"values":["lakehouse"]},{"value":"GA","values":["ga"]}],["Apache Paimon",{"values":["lakehouse","streaming"]},{"value":"Kuluçkada","values":["incubating"]}],["Trino",{"values":["query"]},{"value":"GA","values":["ga"]}],["Apache Flink",{"values":["streaming"]},{"value":"GA","values":["ga"]}],["Pulsar Functions",{"values":["streaming","metadata"]},{"value":"Deneysel","values":["experimental"]}]]}}
```

### Pano görünümü: kanban şeritleri, bildirilen sırayla {#tables-board}

Tablo bloğuna `view: "board"` yazın; sayfa doğrudan kanban şeritleriyle açılır — satırlar karta dönüşür ve grup sütununun her ayrı değeri için bir şerit açılır. Şerit sırasını sabitlemek için sütun başlığına `boardOrder` ekleyin; eklemezseniz şeritler ilk görülme sırasına dizilir ve bu, istediğiniz kanban akışına pek uymaz. Satır verisinde geçen ama `boardOrder` içinde bulunmayan değerler sona alınır, böylece yazar eksiği fark eder. Öteki görünümler (Tablo / Liste / Kart) görünüm düğmesinde bir tıklama uzaktadır.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"view\": \"board\",\n  \"headers\": [\n    \"İş\",\n    { \"label\": \"Durum\",\n      \"boardOrder\": [\"queued\", \"in-progress\", \"blocked\", \"done\"] }\n  ],\n  \"rows\": [\n    [\"Sürüm etiketini oluştur\",       \"queued\"],\n    [\"CI dizeyini bağla\",             \"in-progress\"],\n    [\"Tedarikçi güvenlik incelemesi\", \"blocked\"],\n    [\"Kimlik katmanını taşı\",         \"done\"],\n    [\"RFC taslağını yaz\",             \"in-progress\"],\n    [\"Değişiklik günlüğünü güncelle\", \"queued\"]\n  ]\n}","lang":"json"},"output":{"k":"table","view":"board","headers":["İş",{"label":"Durum","boardOrder":["queued","in-progress","blocked","done"]}],"rows":[["Sürüm etiketini oluştur","queued"],["CI dizeyini bağla","in-progress"],["Tedarikçi güvenlik incelemesi","blocked"],["Kimlik katmanını taşı","done"],["RFC taslağını yaz","in-progress"],["Değişiklik günlüğünü güncelle","queued"]]}}
```

### Çok satırlı hücreler için sütun bazında sarma {#tables-wrap}

Başlık nesnesine `wrap: true` yazdığınızda o sütundaki hücreler kaynaktaki satır sonlarını (`\n`) olduğu gibi korur. Anlatı taşıyan sütunlarda kullanın — tasarım notları, ödünleşimler, hata iletisi gövdeleri — hücrenin içeriği tek satır yerine kısa bir paragraf olarak okunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"table\",\n  \"headers\": [\n    \"Seçenek\",\n    { \"label\": \"Ödünleşim\", \"wrap\": true }\n  ],\n  \"rows\": [\n    [\"Veritabanının sahtesini kullan\",\n     \"CI'da hızlı.\\nGerçek SQL hatalarını kaçırır.\\nGeçen çeyrekteki şema göçü bozulması sahtenin arasından sızdı.\"],\n    [\"Testcontainers\",\n     \"Kurulumu yavaş (~3 sn/test).\\nŞema ve sürücü davranışını yakalar.\\nDocker gerektirir.\"]\n  ]\n}","lang":"json"},"output":{"k":"table","headers":["Seçenek",{"label":"Ödünleşim","wrap":true}],"rows":[["Veritabanının sahtesini kullan","CI'da hızlı.\nGerçek SQL hatalarını kaçırır.\nGeçen çeyrekteki şema göçü bozulması sahtenin arasından sızdı."],["Testcontainers","Kurulumu yavaş (~3 sn/test).\nŞema ve sürücü davranışını yakalar.\nDocker gerektirir."]]}}
```
