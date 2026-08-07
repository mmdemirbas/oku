---
title: Başvuru
eyebrow: Başvuru
subtitle: Bir yazarın ihtiyaç duyduğu her şey tek sayfada — proje kurulumu, sayfa anatomisi, her yapı taşının JSON biçimi ve canlı örneği, sayfa başına üstveri, derleme çıktıları.
date: 2026-05-18
order: 20
summary: Proje kurulumu, sayfanın biçimi, JSON şekli ve canlı örneğiyle her yapı taşı, üstveri, derleme çıktıları.
---

> [!TLDR]
> Projeyi bir kez kurun, sonra JSON sayfaları yazın. Her sayfa, tür etiketli bloklardan oluşan bir ağaçtır; bu sayfa o türleri (satır içi, düzyazı, vurgu, yerleşim, görsel), bunların birbirine nasıl bağlandığını, sayfa başına üstveriyi ve derleme çıktılarını anlatır.
>
> - Kurulum · oku init, _oku sembolik bağını ve bir index.html iskeletini oluşturur. Proje başına bir kez.
> - Sayfa · kind:"page" → title + meta + blocks; bloklar ya bölümdür (içlerinde içerik blokları taşır) ya da üst düzey tldr / kpi-grid.
> - Satır içi · glossary-term, ext-ref, code, em, strong, link
> - Düzyazı · paragraph, heading, list, code, annotated-code
> - Vurgu · callout, insight, info-tip
> - Yerleşim · tldr, kpi-grid, table, compare-grid, step-flow
> - Görsel · chart (scatter / line / area / bubble / quadrant / bar / stacked-bar / grouped-bar / donut), diagram, live-snippet
> - Derleme · oku build → dist/standalone/ (tek dosyalar) ve dist/site/ (+ manifest, llms.txt, Pagefind)

## Proje kurulumu {#setup}

Proje başına bir kez yapılır. Sayfaların _oku/chrome.js ve kardeşlerine hiçbir şey kopyalamadan başvurabilmesi için kiti bağlar.

```bash
cd path/to/your-project/docs
oku init     # creates _oku symlink + index.html in cwd

# Optional: drop a starter page into the docs root
# (The starter pair ships inside the html_doc package — for a
# git checkout it lives at src/html_doc/templates/starter.json.)

cd ..
oku serve    # http://localhost:9876 with live reload
```

init'ten sonra projenizde kit deposunu gösteren bir `docs/_oku/` sembolik bağı bulunur. Her sayfa kite `<script src="_oku/chrome.js">` ve `<link href="_oku/chrome.css">` üzerinden başvurur — kopya yok, sürüm kayması yok. Kiti tek yerde güncelleyin, bütün projeler onu alsın.

> [!NEUTRAL] kit.json — projenizi tanımlayın
> Her projenin docs/kit.json dosyası hangi sözlük alanlarının etkinleşeceğini, tercih edilen dili ve projeye özgü sözlük ya da ext-ref değişikliklerini belirler. Kit başlangıç alanlarıyla gelir (data-platforms, web, ai-llm) — hangisi işinize yarıyorsa onu seçin. Alan seçimini ayrıntısıyla sözlük sayfası anlatır.

## Bir sayfanın anatomisi {#anatomy}

Her JSON sayfasının kökü kind:"page" değeridir ve üç parçası vardır: title, meta, blocks.

```json
{
  "$schema": "https://raw.githubusercontent.com/mmdemirbas/html-doc/main/kit/schema/page.schema.json",
  "kind": "page",
  "schema_version": 1,
  "title": "My note",
  "accent": "teal",
  "meta": {
    "eyebrow": "Notes",
    "subtitle": "One-line subtitle below the H1.",
    "date": "2026-05-18",
    "order": 10,
    "summary": "One-line summary for nav tooltips and llms.txt."
  },
  "blocks": [
    { "kind": "tldr", "summary": "...", "bullets": ["..."] },
    { "kind": "section", "id": "overview", "title": "Overview", "blocks": [
      { "kind": "paragraph", "content": "Plain prose works as a string." }
    ]}
  ]
}
```

### Üst düzey alanlar {#top-level}

- `kind` — `"page"` olmak zorundadır. İşleyici başka bir değeri geri çevirir.
- `title` — zorunlu. Hem `<title>` hem de kapaktaki H1 olur.
- `accent` — isteğe bağlı. Ya adlandırılmış bir belirteç (`teal`, `amber`, `indigo`) ya da bir CSS renk değeri. `kit.json` içindeki ağaç varsayılanını yalnızca bu sayfa için değiştirir.
- `meta` — isteğe bağlı nesne. Aşağıdaki Sayfa başına üstveri bölümüne bakın; markdown kaynağında bunlar ön bilgi anahtarlarıdır. Çoğu sayfada yazmaya değen tek alan `summary`dir.
- `blocks` — içerik ağacı. Üst düzey blokların dizisi (tldr, kpi-grid, section).

> [!TIP] summary neden önemli
> meta.summary dört yerde karşınıza çıkar: üzerine gelindiğinde page-nav ipucu, yapay zekâ tüketicileri için llms.txt site haritası satırı, Pagefind arama özeti ve kapak alt başlığı. Sayfanın ne içerdiğine odaklanan tek ve derli toplu bir cümle olsun — merak uyandıran bir tanıtım değil.

### Markdown kaynakları {#markdown-sources}

docs kökünün altındaki her `.md` dosyası birinci sınıf sayfadır — site ağacında görünür, kitin içindekiler listesi ve çerçevesiyle işlenir, `oku check / build / serve` sırasında JSON sayfaların yanında sağ salim kalır. Kite geçmeden önce hiçbir şeyi dönüştürmeniz gerekmez; var olan Markdown belgeleri olduğu gibi girer.

#### Markdown → kit dönüşümü {#markdown-kit-conversion}

Her Markdown yapısı belirli bir kit bloğuna ya da satır içi düğüme karşılık gelir. Doğrunun kaynağı tablodur — satır sırası, dönüştürücünün ayrıştırma ağacında yürüdüğü sıradır.

```oku-table
{"headers":["Markdown","Şuna dönüşür"],"rows":[["YAML ön bilgi bloğu (`--- ... ---`)","`page.title` + `page.meta`"],["ATX başlık H1","`page.title`"],["ATX başlık H2","`section` (id başlıktan otomatik türetilir)"],["ATX başlık H3 / H4","etkin bölümün içinde `heading` bloğu"],["Şunları içeren paragraf: `**kalın**` / `*eğik*` / `~~üstü çizili~~` / `` `kod` `` / `[metin](url \"başlık\")` / `![alt](src)` / `<https://auto.link>`","`paragraph` + satır içi düğümler"],["Ters bölü kaçışı (`\\*`, `\\[`, `` \\` ``)","karakterin kendisi — vurgu tetiklenmez"],["Karakter göndermesi (`&amp;`, `&mdash;`, `&#8594;`)","çözülmüş karakter"],["Sert satır sonu (sonda iki boşluk ya da sonda `\\`)","paragrafın içinde `<br>`"],["Kaynak biçimli bağlantılar `[metin][etiket]` + `[etiket]: url`","satır içi bağlantı düğümü"],["Dipnotlar `[^id]` + `[^id]: …`","Numaralı üst simge + bir 'Dipnotlar' bölümü"],["Tanım listesi (`terim\\n: tanım`)","html-inline üzerinden `<dl>`"],["Satır içi HTML izin listesi (`a, code, em, strong, span, sup, sub, br, mark, kbd, samp, del, ins, abbr`)","html-inline olduğu gibi geçer"],["Çitli kod bloğu (` ```lang `)","`code` (dil korunur)"],["Çitli `mermaid` bloğu","`diagram` (kitin diyagram yapı taşıyla işlenir)"],["Sırasız ve sıralı listeler, iç içe","`list` (html-inline çocuklarıyla)"],["Alıntı bloğu (`>`)","`<blockquote>`; bir GFM uyarısı (`> [!NOTE]`, `[!TIP]`, `[!WARNING]`, `[!CAUTION]`, `[!IMPORTANT]`, ayrıca kitin `[!TLDR]` biçimi) o türde bir `callout` olur"],["GFM boru işaretli tablo","`table`"],["Konu ayracı (`---`, `***`, `___`)","`<hr>`"]]}
```

> [!INFO] Göreli .md bağlantıları .html olarak yeniden yazılır
> Bir Markdown sayfasındaki `[genel bakış](other.md#section)`, işlenirken `other.html#section` olur; böylece .md sayfaları arasındaki bağlantılar .json sayfaları arasındakiyle aynı biçimde çalışır. Mutlak adresler (http, https, mailto), yalnızca parça gösteren başvurular (`#section`) ve mutlak yollar (`/x`) olduğu gibi geçer.

### Markdown görüntüleyicisi {#markdown-viewer}

Okuyucu tıkladığında hâlâ `.md` diyen bir bağlantı, dosyayı tarayıcının düz metin görünümüne bırakmak yerine kitin salt okunur görüntüleyicisinde açılır.

<div class="callout tip">
<h4>Deneyin</h4>
<p><a href="reference.tr.md">Bu sayfanın kendi Markdown kaynağını açın</a>. Bağlantı bir HTML adacığının içine yazıldığı için size hâlâ <code>.md</code> diyerek ulaşır — düzyazıya yazılmış göreli bir bağlantı <code>reference.tr.html</code> hâline getirilir ve sizi zaten okumakta olduğunuz sayfaya götürürdü.</p>
</div>

Görüntüleyici sayfanın üzerinde açılır; sayfanın kendisi hiçbir yere gitmez. Dosyanın yolunu, ön bilgideki `title` ve `summary` değerlerini, işlenmiş belgeyi ve baytları birebir tutan, kopyalama düğmeli bir **Kaynak** bölmesini taşır. Ham dosyaya çıkış kapısı **Dosyayı aç**tır. Escape, arka perde ve kapatma düğmesi görüntüleyiciyi kapatır.

Hangi bağlantıların oraya ulaştığı yukarıdaki yeniden yazma kuralından çıkar. Düzyazıya yazılan *göreli* bir bağlantı `.html` olur, çünkü o dosya bu ağaçta bir sayfadır ve sayfanın tamamı bir dosya görüntüleyicisini geçer. Yeniden yazmanın bile bile dokunmadıkları görüntüleyiciye gider:

```oku-table
{"headers":["Bağlantı","Okuyucuya nasıl ulaşır","Neyi açar"],"rows":[["düzyazıda `[plan](notes/plan.md)`","`notes/plan.html`","işlenmiş sayfayı"],["düzyazıda `[plan](/notes/plan.md)`","`/notes/plan.md`","görüntüleyiciyi"],["adacıkta `<a href=\"notes/plan.md\">`","`notes/plan.md`","görüntüleyiciyi"],["`[spec](https://example.com/s.md)`","değişmeden","öteki siteyi, yeni sekmede"]]}
```

Yalnızca düz sol tıklama sayılır. Cmd / Ctrl / Shift / orta tıklama, bir `target` ve `download` — hepsi *bana dosyayı ver, senin okuyuşunu değil* demektir ve tarayıcının davranışını korur.

Bir sayfanın yayımlandığı üç yol dosyaya farklı biçimde ulaşır; okuyucu hangisinin çalıştığını ayırt edemez:

```oku-table
{"headers":["Nereden açıldı","Dosya nasıl okunur"],"rows":[["`oku serve`","geliştirme sunucusundan çekilir"],["`dist/site/`","çekilir — derleme her `.md` kaynağını kendi `.html` dosyasının yanına kopyalar"],["`file://` üzerinden `dist/standalone/`","derleme sırasında HTML'e gömülen bir eşlemeden okunur"]]}
```

Derlemenin işin içine girmesinin nedeni `file://` durumudur: `file://` kökenli bir sayfa yanı başındaki dosyayı okuyamaz; bu yüzden `oku build`, sayfalarının bağlandığı her `.md` dosyasını, yazıldığı hâliyle href'i anahtar alarak içeri gömer. Derlemenin çözemediği bir bağlantı — eksik, ağacın dışında ya da 512K'dan büyük — okuyucunun karşısında hata vermek yerine derleme sırasında bildirilir.

> [!NEUTRAL] Her Markdown dosyası varsayılan olarak bir sayfadır
> README.md, CHANGELOG.md, CLAUDE.md, AGENTS.md, LICENSE.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md ve gezicinin ulaştığı diğer bütün `.md` dosyaları sayfa olarak görünür. Birini gizlemek için SKIP_DIRS listesindeki bir alt dizine taşıyın (`dist/`, `_oku/`, `.git/`, `.venv/`, `node_modules/`, `templates/`, `_internal/`).

## Düzyazı yapı taşları {#prose}

paragraph, heading, list, code — her düzyazı bölümünün dört yapı taşı. Birlikte kullanıldıklarında tipik içeriğin yaklaşık %80'ini karşılarlar.

### paragraph {#paragraph}

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"paragraph\", \"content\": [\n  \"Düz metin, içinde bir \",\n  { \"kind\": \"strong\", \"text\": \"kalın parça\" },\n  \" ve bir \",\n  { \"kind\": \"code\", \"text\": \"code\" },\n  \" aralığı.\"\n] }","lang":"json"},"output":"Düz metin, içinde bir **kalın parça** ve bir `code` aralığı."}
```

### heading {#heading}

Bir bölümün içindeki alt başlıklar. `level` 3 ya da 4 olur (h1 = sayfa başlığı, h2 = bölüm başlığı — ikisi de kendiliğinden üretilir). Kalıcı bağlantı için isteğe bağlı `id`; verilmezse başlıktan türetilir.

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"heading\", \"level\": 3, \"title\": \"Alt başlık\", \"id\": \"sub\" }","lang":"json"},"output":"### Alt başlık {#heading-sample-3}"}
```

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"heading\", \"level\": 4, \"title\": \"Alt alt başlık\" }","lang":"json"},"output":"#### Alt alt başlık {#heading-sample-4}"}
```

### list {#list}

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"list\", \"style\": \"bullet\", \"items\": [\n  \"Düz dizge öğesi.\",\n  [\"Ya da \", { \"kind\": \"code\", \"text\": \"inline\" }, \" düğümleri taşıyan bir dizi.\"]\n] }","lang":"json"},"output":"- Düz dizge öğesi.\n- Ya da `inline` düğümleri taşıyan bir dizi."}
```

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"list\", \"style\": \"numbered\", \"items\": [\"adım 1\", \"adım 2\", \"adım 3\"] }","lang":"json"},"output":"1. adım 1\n2. adım 2\n3. adım 3"}
```

### code {#code}

Kod blokları. `language` bilgilendirme amaçlıdır; işleyici iç `<code>` öğesine bir `language-*` sınıfı koyar, böylece Prism (CDN'den geç yüklenir) istendiğinde renklendirir. Çalışma zamanı ardından satır numaralı gri bir kenar sütunu ekler ve süslü parantez kullanan dillerde katlanabilir her bölgenin açılış satırına bir tıklama hedefi koyar.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"code\",\n  \"language\": \"python\",\n  \"source\": \"def hello():\\n    print('world')\"\n}","lang":"json"},"output":"```python\ndef hello():\n    print('world')\n```"}
```

### annotated-code {#annotated-code}

Numaralı kod açıklamaları. Kaynağın içindeki `(1)` / `(2)` gibi imler, yanlarında numaralı bir yan panelle eşleşen dairesel vurgu rozetlerine dönüşür. Bir rozetin üzerine gelmek, ipucunu satırın ALTINA açar (kodu hiç örtmez) ve gösterdiği satırı vurgular. Rozetle panel öğesi arasında gidip gelmek için tıklayın.

Her açıklama ayrıca bir aralık ya da küme işaretlemek için `lines` (1'den başlayan satır belirtimi — `"3"`, `"1-3"`, `"1,5-7"`) ve/veya üzerine gelindiğinde belirli metin parçalarını vurgulamak için `match` (dizge ya da dizi) taşıyabilir. `lines` verilmiş ve satır içinde `(N)` imi yoksa rozet kendiliğinden listelenen ilk satırın başına yerleşir — kaynak temiz kalır.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"annotated-code\",\n  \"language\": \"javascript\",\n  \"source\": \"const x = 1; // (1)\\nfunction greet(name) {\\n  return `Hello, ${name}!`;\\n}\",\n  \"annotations\": [\n    { \"id\": 1, \"content\": \"<code>const</code> blok kapsamlı bir bağ oluşturur.\" },\n    { \"id\": 2, \"content\": \"İşlev gövdesi — 2-4. satırları vurgular.\", \"lines\": \"2-4\" },\n    { \"id\": 3, \"content\": \"Şablon dizgesinde değer yerleştirme.\", \"match\": \"${name}\" }\n  ]\n}","lang":"json"},"output":{"k":"annotated-code","src":"const x = 1; // (1)\nfunction greet(name) {\n  return `Hello, ${name}!`;\n}","lang":"javascript","annotations":[{"id":1,"content":"<code>const</code> blok kapsamlı bir bağ oluşturur."},{"id":2,"content":"İşlev gövdesi — bu rozetin üzerine gelmek 2-4. satırları kenar sütununda vurgular.","lines":"2-4"},{"id":3,"content":"Şablon dizgesinde değer yerleştirme — bu rozetin üzerine gelmek <code>${name}</code> parçasını vurgular.","match":"${name}"}]}}
```

## Vurgu yapı taşları {#emphasis}

callout, insight, info-tip — içeriği farklı ağırlıklarla öne çıkarmanın üç yolu. Ağırlığı, okuyucuya vermek istediğiniz işarete göre seçin.

### callout {#callout}

Blok düzeyinde temalı not. `type` renk bandını seçer: `warn` / `warning` / `caution` (kehribar), `danger` (kırmızı), `success` / `tip` (yeşil), `info` / `note` (vurgu mavisi), `neutral` (gri, varsayılan). `title` isteğe bağlıdır. `content` bir richString'dir. İsteğe bağlı `bind`, bu callout'u aynı bind anahtarını taşıyan başka bir blokla eşler — birinin üzerine gelmek ötekini parlatır (bkz. Kesişen özellikler › Birlikte vurgulanan çiftler).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"warn\",\n  \"title\": \"Kilide dikkat\",\n  \"content\": \"Sıkıştırma bir üstveri kilidi tutar; uzun işler yazarları bekletir.\"\n}","lang":"json"},"output":"> [!WARN] warn\n> Sarı çerçeveli; çekinceler için kullanılır."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"danger\",\n  \"title\": \"danger\",\n  \"content\": \"Kırmızı çerçeveli; kırıcı değişiklikler ya da riskler için kullanılır.\"\n}","lang":"json"},"output":"> [!DANGER] danger\n> Kırmızı çerçeveli; kırıcı değişiklikler ya da riskler için kullanılır."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"success\",\n  \"title\": \"success\",\n  \"content\": \"Yeşil çerçeveli; onaylar için kullanılır.\"\n}","lang":"json"},"output":"> [!SUCCESS] success\n> Yeşil çerçeveli; onaylar için kullanılır."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"neutral\",\n  \"title\": \"neutral\",\n  \"content\": \"Gri çerçeveli; genel notlar için kullanılır.\"\n}","lang":"json"},"output":"> [!NEUTRAL] neutral\n> Gri çerçeveli; genel notlar için kullanılır."}
```

### insight {#insight}

Ana çıkarım için bir alıntı kutusu. Paragraftan daha büyük ve daha ayırt edici — bölüm başına yavaşlamaya değen tek cümleyi işaretlemek için kullanılır.

```oku-example
{"code":{"k":"code","src":"{ \"kind\": \"insight\", \"content\": \"Kilitleme yapı taşı katalogdur. Anlık görüntüler ise çok sürümlü çalışmanın düzeneğidir.\" }","lang":"json"},"output":{"k":"insight","b":"Kilitleme yapı taşı katalogdur. Anlık görüntüler ise çok sürümlü çalışmanın düzeneğidir."}}
```

### info-tip {#info-tip}

Kılık değiştirmiş yerel `<details>` — varsayılan olarak kapalıdır, tıklayınca açılır. Göz gezdirme yolunu bozmadan isteğe bağlı derinliği ertelemek için kullanın. `content` bir içerik bloğu dizisi alır (paragraf, kod, callout, ...).

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"info-tip\",\n  \"summary\": \"Kilit gerçekte nasıl çalışır\",\n  \"content\": [\n    { \"kind\": \"paragraph\", \"content\": \"İki yazar yarışır ...\" }\n  ]\n}","lang":"json"},"output":"> [!TIP] Canlı bir info-tip açmak için tıklayın\n> Okuyucuların meraklı %5'i hikâyenin tamamını isterken kalan %95'inin ilerlemesi gerektiğinde doğru yapı taşı info-tip'tir."}
```

## Yapılandırılmış yerleşim yapı taşları {#layout}

tldr, kpi-grid, compare-grid, step-flow — düzyazının doğru biçim olmadığı yerler için.

### tldr {#tldr}

Yalnızca üst düzeyde kullanılır. İsteğe bağlı `title`, bir `summary` satırı ve `bullets` taşıyan öne çıkarılmış açılış kutusu — her madde zengin metindir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"tldr\",\n  \"summary\": \"Tek cümlelik öz.\",\n  \"bullets\": [\n    \"Üç ila beş somut madde.\",\n    \"Her madde sözlük terimi gibi satır içi türler taşıyabilir.\"\n  ]\n}","lang":"json"},"output":"> [!TLDR] TL;DR (örnek)\n> Tek cümlelik öz. Özet satırı maddelerden büyüktür ve önce okunur.\n>\n> - Üç ila beş somut madde.\n> - Her madde sözlük terimi ya da bağlantı gibi satır içi türler taşıyabilir.\n> - Asıl kullanımı üst düzeyde durmasıdır; buradaki metnin içinde örnek olsun diye duruyor."}
```

### kpi-grid {#kpi-grid}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"kpi-grid\",\n  \"tiles\": [\n    { \"num\": \"17\",   \"label\": \"Yapı taşı\" },\n    { \"num\": \"JSON\", \"label\": \"Kaynak\" },\n    { \"num\": \"0\",    \"label\": \"İçerik için derleme adımı\" }\n  ]\n}","lang":"json"},"output":{"k":"kpi-grid","tiles":[{"num":"17","label":"Yapı taşı"},{"num":"JSON","label":"Kaynak"},{"num":"0","label":"İçerik için derleme adımı"}]}}
```

### compare-grid {#compare-grid}

Yan yana kartlar. `verdict` değeri `good`, `bad` ya da `neutral` olur — üst kenarlığın rengini belirler.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"compare-grid\",\n  \"cards\": [\n    { \"verdict\": \"bad\",  \"title\": \"Önce\", \"content\": \"...\" },\n    { \"verdict\": \"good\", \"title\": \"Sonra\", \"content\": \"...\" }\n  ]\n}","lang":"json"},"output":{"k":"compare-grid","cards":[{"t":"Elle yazılan HTML (v1)","b":"Elle yazılmış etiketler. Ağaç düzenlemeleri dizge işlemleriyle. Yapay zekâ araçları için kırılgan.","verdict":"bad"},{"t":"Yazılan JSON","b":"Yapılandırılmış ağaç. Atomik düzenlemeler. Sözleşme JSON.parse'tır.","verdict":"good"}]}}
```

Kapsam çeşitlemesi — `verdict` değerini `in` (yeşil kenarlık) ya da `out` (soluk) yapın ve kartın içine madde listesi koymak için `items` kullanın. `content` ile `items` bir arada bulunabilir — önce content, altında items işlenir.

Izgaraya `"preview": true` verildiğinde ızgara bir **seçiciye** dönüşür: `href` değeri sayfa içi bir çapa olan her kart, o çapadan sonra gelen figürün siluetini gösterir. Resim, kartın yanına ayrıca yazılmaz; işlenmiş figürden klonlanır, böylece okuyucunun varacağı şeyle çelişmesi olanaksızdır. Yazılar düşürülür — sütunun tamamı için dizilmiş bir figür, sütunun aşağı yukarı dörtte birinde gösterilir ve orada bir etiket yazı değil kirdir — adı zaten kartın kendi başlığı taşır. Düzyazıya ya da hiçbir şeye bağlanan kart olduğu gibi kalır, yani bayrağı karışık bir ızgarada açmak güvenlidir. [`docs/charts.md`](charts.tr.md) bunu 53 grafik türünün tamamı için kullanır.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"compare-grid\",\n  \"cards\": [\n    { \"verdict\": \"in\",  \"title\": \"v1\",      \"items\": [\"...\"] },\n    { \"verdict\": \"out\", \"title\": \"İleride\", \"items\": [\"...\"] }\n  ]\n}","lang":"json"},"output":{"k":"compare-grid","cards":[{"t":"Şimdi çıkıyor","b":"- JSON kaynağından çalışma zamanında işleme\n- EN/TR destekli çok alanlı sözlük\n- Visual Viewport parmakla yakınlaştırma düzeltmesi\n- Derlenmiş sitelerde Pagefind araması","verdict":"in"},{"t":"Kapsam dışı","b":"- Markdown ile yazma yolu\n- Sunucu tarafında işleme\n- Kullanıcı başına kimlik doğrulama\n- Satır içi sözlük düzenleme arayüzü","verdict":"out"}]}}
```

### step-flow {#step-flow}

Sıralı eylemler, derleme adımları ya da geçiş yolları için numaralı kartlar.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"step-flow\",\n  \"steps\": [\n    { \"num\": \"1\", \"title\": \"Kurulum\", \"meta\": \"~1 dk\", \"content\": \"oku init\" },\n    { \"num\": \"2\", \"title\": \"Yazım\", \"content\": \"JSON sayfasını yazın.\" }\n  ]\n}","lang":"json"},"output":{"k":"step-flow","steps":[{"t":"Kurulum","b":"docs kökünüze cd ile girin; ardından oku init orada _oku sembolik bağını ve bir index.html iskeletini kurar.","meta":"~1 dk · proje başına bir kez"},{"t":"Yazım","b":"Yan yana bir JSON sayfası ve bir HTML iskeleti yazın; işleyici JSON'u sayfa yüklenirken çeker.","meta":"yinelemeli"},{"t":"Derleme","b":"oku build → dist/standalone/ (tek dosyalık HTML'ler) ve dist/site/ (ortak varlıklı çok sayfalı site + manifest + llms.txt + Pagefind).","meta":"yayına almadan ya da tek dosyayı paylaşmadan önce"}]}}
```

### timeline {#timeline}

Her girdisi bir **durum** taşıyan sıralı bir dizi. Hem sıranın hem
durumun anlatının parçası olduğu yerde kullanın: bir iddianın sonradan
düzeltildiği hata ayıklama öyküsü, karar günlüğü, olay sırası, sürüm
geçmişi.

Komşusu [step-flow](#step-flow) ve yanlış olanı seçmek sık yapılan
hatadır. step-flow, **okuyucunun izlemesi beklenen bir yordamdır**;
orada her adım eşit ölçüde doğrudur. Timeline ise **olanların
kaydıdır** ve üzerindeki bir girdi sonradan bırakılmış bir iddia
olabilir — nokta bu yüzden bir durum taşır, adım numarası taşımaz.

`status` şunlardan biridir: `note` (varsayılan, sessiz içi boş nokta),
`done` (dolu, sonuçlanmış), `open` (içi boş, ileri sürülmüş ama
sonuçlanmamış) ya da `dropped` (içi boş, geri alınmış ya da yerini
başkasına bırakmış). `label` girdiye yazarın kendi verdiği addır —
rengi durum, anlamı etiket taşır; böylece `"iddia #1"`, `"2026-03-04"`
ve `"v0.4.0"` her biri için ayrı renk uydurmadan çalışır.

```oku-example
{"code":{"k":"code","lang":"json","src":"{\n  \"k\": \"timeline\",\n  \"events\": [\n    {\n      \"status\": \"open\",\n      \"label\": \"iddia #1\",\n      \"t\": \"\\\"Sorun motorun derlemesinde\\\"\",\n      \"b\": \"Kodun ilk okuması. Akla yatkın ve **doğrulanmamış** — bir kuşku, bulgu değil.\"\n    },\n    {\n      \"status\": \"dropped\",\n      \"label\": \"düzeltildi\",\n      \"t\": \"Öteki yöne fazla yüklenildi\",\n      \"b\": \"Sonra \\\"tamamen bizim boşluğumuz\\\" tarafına savruldu. O da erkendi; yol henüz ölçülmemişti.\"\n    },\n    {\n      \"status\": \"done\",\n      \"label\": \"doğrulandı\",\n      \"t\": \"Boşluk gerçek ve bize ait\",\n      \"b\": \"Oluşturma yolu ölçüldü. `e326b65` ile düzeltildi.\"\n    }\n  ]\n}"},"output":{"k":"timeline","events":[{"status":"open","label":"iddia #1","t":"\"Sorun motorun derlemesinde\"","b":"Kodu okurken gelen ilk sezgi: içeri alınmış derleme değeri başka biçimde veriyor olmalı. Akla yatkın ve **doğrulanmamış** — bir kuşku, bulgu değil."},{"status":"dropped","label":"düzeltildi","t":"Öteki yöne fazla yüklenildi","b":"Sonra \"tamamen bizim boşluğumuz, motorun suçu yok\" tarafına savruldu. O da erkendi: uzak yol henüz ölçülmemişti."},{"status":"done","label":"doğrulandı","t":"Boşluk gerçek ve bize ait","b":"Oluşturma yolu ölçüldü. Dönüştürücümüz üstveri *verildiğinde* çalışıyor, ama birincil API hiç geçersiz kılınmamıştı — değer, dönüştürücü çalışmadan önce yok oluyordu. `e326b65` ile düzeltildi."},{"status":"note","label":"hâlâ açık","t":"Bir boşluk aşağı akışta duruyor ve bize ait değil","b":"Bellekteki şema alanı taşıdığı hâlde diske yazılan dosya onu atlıyor. Bu kayıp, doğru şema teslim edildikten sonra, satıcının yazma yolunun içinde oluşuyor."}]}}
```

## live-snippet {#visual}

Düzenlenebilir HTML/CSS/JS metin alanı + korumalı iframe önizlemesi.

### live-snippet {#live-snippet}

Korumalı iframe önizlemesiyle düzenlenebilir HTML/CSS/JS. Girişte 220 ms geciktirme. `language` şimdilik yalnızca `html-css-js` değerini alır (v1'in tek kipi). Sıfırla düğmesi özgün `source` içeriğini geri getirir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"live-snippet\",\n  \"label\": \"Renk geçişini ve iletiyi düzenleyin\",\n  \"source\": \"<style>...</style>\\n<div>...</div>\"\n}","lang":"json"},"output":{"k":"live-snippet","src":"<style>\n  body { margin:0; height:100vh; display:grid; place-items:center;\n         background: linear-gradient(135deg, #115e59, #2dd4bf);\n         font-family: system-ui; }\n  .box { background:white; padding:20px 28px; border-radius:12px;\n         box-shadow:0 8px 24px rgba(0,0,0,0.15); }\n  h1 { margin:0 0 6px; color:#0f766e; font-size:20px; }\n  p  { margin:0; color:#475569; font-size:14px; }\n</style>\n<div class=\"box\">\n  <h1>Parçacığı deneyin</h1>\n  <p>Soldaki kaynağı düzenleyin.</p>\n</div>","label":"İşaretlemeyi düzenleyin — önizleme anında güncellenir"}}
```

## Satır içi türler {#inline}

Her richString içinde kullanılır — paragraph.content, list.items[*], callout.content ve benzerleri. Bir dizide dizgeleri bu nesnelerle karıştırın.

### glossary-term {#glossary-term}

Üzerine gelince tanımı taşıyan bir ipucu açılır; tıklayınca sabitlenir. `term` değerini etkin sözlük alanlarında öncelik sırasıyla çözer. İki alan aynı terimi kullandığında ayrımı `in` yapar. `lang`, o örnek için proje dilini geçersiz kılar.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Üzerine gelin: \",\n    { \"kind\": \"glossary-term\", \"term\": \"ACID\", \"text\": \"ACID\" },\n    \" — sabitlemek için tıklayın; açık kalması için imleci ipucuna doğru götürün.\"\n  ]\n}","lang":"json"},"output":"Üzerine gelin: [ACID](#g/ACID) — sabitlemek için tıklayın; açık kalması için imleci ipucuna doğru götürün."}
```

### ext-ref {#ext-ref}

glossary-term gibidir ama dış varlıklar içindir (araçlar, makaleler, kişiler). Üzerine gelme, köprü kurma ve sabitleme davranışı aynıdır. `_oku/extrefs/<domain>.json` dosyasından okur (ya da proje kit.json değişikliklerinden). Her girdinin bir `summary` ve bir `link` alanı vardır; ipucu adı ve özeti gösterir, yanında bağlantıya giden bir Daha fazlası düğmesi bulunur.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Gücünü şuradan alır: \",\n    { \"kind\": \"ext-ref\", \"name\": \"Pagefind\", \"text\": \"Pagefind\" },\n    \" — kart için üzerine gelin, sabitlemek için tıklayın, yeni sekmede açmak için satır içi bağlantıya tıklayın.\"\n  ]\n}","lang":"json"},"output":"Gücünü şuradan alır: [Pagefind](#x/Pagefind) — kart için üzerine gelin, sabitlemek için tıklayın, yeni sekmede açmak için satır içi bağlantıya tıklayın."}
```

### code, em, strong, link {#code-em-strong-link}

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Satır içi \",\n    { \"kind\": \"code\",   \"text\": \"build_manifest()\" },\n    \", \",\n    { \"kind\": \"em\",     \"text\": \"eğik\" },\n    \", \",\n    { \"kind\": \"strong\", \"text\": \"kalın\" },\n    \" ve yeni sekmede açılan bir \",\n    { \"kind\": \"link\",   \"text\": \"jsDelivr\", \"href\": \"https://cdn.jsdelivr.net\" },\n    \" bağlantısı.\"\n  ]\n}","lang":"json"},"output":"Satır içi `build_manifest()`, *eğik*, **kalın** ve yeni sekmede açılan bir [jsDelivr](https://cdn.jsdelivr.net) bağlantısı."}
```

Dipnotlar ve kaynak biçimli bağlantılar sayfanın tamamında çözülür; tanım, kullanıldığı yerden uzakta durabilir — kaynağın sonunda ya da bambaşka bir blokta. Aşağıdaki paragraf canlıdır: bir dipnot[^ref-demo] ve bu sayfanın altındaki tanımlardan işlenen bir [kaynak bağlantısı][pagefind-site].

```markdown
A claim that needs a source[^ref-demo] and a [reference link][pagefind-site].

[^ref-demo]: Definitions may appear anywhere on the page.
[pagefind-site]: https://pagefind.app "Pagefind"
```

Satır içi yapılar iki yönde de iç içe geçer — vurgunun içinde bağlantı, bağlantının içinde vurgu, kalının içinde kod aralığı. Yalnızca kod aralığı gövdesini olduğu gibi tutar; ters tırnak içine yazılan markdown kaynak olarak görünür kalır.

```oku-example
{"code":{"k":"code","src":"İç içe geçme işler: **[kalın bir bağlantı](https://example.com)**, [**kalın** içeren bağlantı](https://example.com), **kalının içinde `kod`** ve **içinde *eğik* olan kalın**. Ters tırnağın içinde hiçbir şey ayrıştırılmaz: `**[a](b)**`.","lang":"markdown"},"output":"İç içe geçme işler: **[kalın bir bağlantı](https://example.com)**, [**kalın** içeren bağlantı](https://example.com), **kalının içinde `kod`** ve **içinde *eğik* olan kalın**. Ters tırnağın içinde hiçbir şey ayrıştırılmaz: `**[a](b)**`."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"paragraph\",\n  \"content\": [\n    \"Temizlenmiş satır içi HTML olduğu gibi geçer: \",\n    { \"kind\": \"html\", \"text\": \"<kbd>Ctrl</kbd>\" },\n    \" + \",\n    { \"kind\": \"html\", \"text\": \"<kbd>C</kbd>\" },\n    \" seçimi kopyalar; kimya dipnotu olarak da H<sub>2</sub>O.\"\n  ]\n}","lang":"json"},"output":"Temizlenmiş satır içi HTML olduğu gibi geçer: <kbd>Ctrl</kbd> + <kbd>C</kbd> seçimi kopyalar; kimya dipnotu olarak da H<sub>2</sub>O."}
```

## Sayfa başına üstveri {#metadata}

Yazmanız gereken iki alan var: `title` ve `summary`. Geri kalanların
hepsi ya türetilir ya da ağaçtan devralınır; yine de varsayılan yanlış
kaldığında her biri sayfa bazında değiştirilebilir.

`summary` yerini iki kez hak eder — hem gezinme ipucu, llms.txt satırı
ve arama özetidir, hem de `subtitle` yazılmadığında kapak alt başlığını
doldurur.

```oku-table
{"headers":["Alan",{"label":"Kim sağlar","filter":"chips","values":["Yazar belirler","kit.json'dan gelir","Türetilir","İsteğe bağlı"]},"Anlamı"],"rows":[["`title`",{"value":"Yazar belirler","values":["Yazar belirler"]},"Sayfanın başlığı. Makul bir varsayılanı olmayan tek alan."],["`summary`",{"value":"Yazar belirler","values":["Yazar belirler"]},"Tek satır. Gezinme ipucu, llms.txt satırı, arama özeti — ve `subtitle` yoksa kapak alt başlığı."],["`order`",{"value":"Yazar belirler","values":["Yazar belirler"]},"Site ağacındaki sıralama anahtarı. Küçük değer önce gelir; eşitlikte başlığa bakılır."],["`parent`",{"value":"Yazar belirler","values":["Yazar belirler"]},"Üst sayfanın kimliği — bu sayfayı site ağacında onun altına yerleştirir."],["`accent`",{"value":"kit.json'dan gelir","values":["kit.json'dan gelir"]},"Adlandırılmış belirteç (teal, amber, indigo, rose…) ya da herhangi bir CSS rengi. Ağacın tamamı için `kit.json` içinde bir kez verin; bir sayfa ancak gerçekten ayrıştığında değiştirsin."],["`audience`",{"value":"kit.json'dan gelir","values":["kit.json'dan gelir"]},"Kapak üstveri satırında görünen serbest biçimli okuyucu etiketi. `kit.json` içinde ağacın tamamı için; bakımcıya dönük tek tük sayfada sayfa bazında değiştirilir."],["`read_time`",{"value":"Türetilir","values":["Türetilir"]},"Gövdeden dakikada 220 sözcük varsayılarak kestirilir, iki dakikanın altında hiç yazılmaz. Değiştirmek için elle verin; elle sayılmış bir değer ilk düzenlemede eskir."],["`updated`",{"value":"Türetilir","values":["Türetilir"]},"Dosyanın son işleme tarihi. Bile bile dosya sistemi değişiklik zamanı değil — taze bir kopya bütün ağacı bugün güncellenmiş gibi damgalardı. Sessiz, eğik bir satır olarak işlenir ve `date` ile aynıysa gösterilmez."],["`eyebrow`",{"value":"İsteğe bağlı","values":["İsteğe bağlı"]},"H1'in üstündeki küçük etiket. Gezinmenin zaten göstermediği bir şey söylemiyorsa yazmayın."],["`subtitle`",{"value":"İsteğe bağlı","values":["İsteğe bağlı"]},"H1'in altında tek paragraf. Yalnızca kapağın `summary` dışında bir şey söylemesi gerektiğinde lazım olur."],["`date`",{"value":"İsteğe bağlı","values":["İsteğe bağlı"]},"Yayın tarihi, olduğu gibi gösterilir — kit onu hiç ayrıştırmaz."],["`lang`",{"value":"İsteğe bağlı","values":["İsteğe bağlı"]},"Dil kodu. Proje varsayılanını yalnızca bu sayfada değiştirir."]]}
```

> [!TIP] Bir varsayılan nereye ait
> Bir ağacın her sayfasında aynı olan değer `kit.json` dosyasına
> aittir; on bir ayrı ön bilgi bloğunda yinelenmez. Gövdenin zaten ima
> ettiği bir değer — sayfanın okunma süresi, en son ne zaman değiştiği
> — derlemeye aittir. Bir sayfa gereksiz yere bir alan yazdığında
> `oku check` uyarır.

## Derleme çıktıları {#build}

oku build, dist/ altında her okuyucu kitlesi için bir tane olmak üzere üç ağaç üretir. Yazarların geliştirme sırasında bunu çalıştırması gerekmez — çalışma zamanı işleyicisi JSON'u doğrudan çeker — ama arama, tek dosyalık standalone kipi ve llms.txt site haritası için derleme şarttır.

```oku-step-flow
{"steps":[{"t":"dist/site/","b":"Yayına alınabilir çok sayfalı site. Her HTML ve JSON, dizin yapısı korunarak kopyalanır. Kit varlıkları dist/site/_oku/ altında toplanır. site-manifest.json, kopyalanan kitin yanında site kökünde durur — chrome.js docs kökünü _oku/ nerede duruyorsa oradan çözer ve dosyayı orada arar. Herhangi bir durağan sunucuya bırakın.","meta":"insanlar, HTTP"},{"t":"dist/standalone/","b":"Tek dosyalık çıktılar. Her HTML; kit JS'sini, CSS'ini, sayfa JSON'unu, sözlük paketini ve manifesti window.__okuManifest olarak içine gömer. Sayfa başına, çevrimdışı açılan kendi kendine yeten bir dosya — e-postaya ek olarak göndermeye hazır. Ayrı bir manifest ya da llms.txt gerekmez.","meta":"insanlar, file://"},{"t":".md kaynakları + dist/site/llms.txt","b":"İkiz bir ağaç yok: yapay zekâ ve LLM için asıl yüzey doğrudan .md sayfa kaynaklarıdır. Derleme, site kökünde manifestin yanına tek bir llms.txt site haritası bırakır (sayfa başına bir satır: URL + başlık + özet, llmstxt.org geleneği).","meta":"yapay zekâ / LLM tüketicileri"}]}
```

> [!SUCCESS] Pagefind araması — isteğe bağlı bağımlılık
> pagefind PATH üzerindeyse (brew install pagefind ya da npx pagefind), derleme ayrıca dist/site/ ağacını dist/site/pagefind/ altında dizinler. Yoksa sessizce atlar. Çerçevedeki arama düğmesi yalnızca derlenmiş sitelerde çalışır.

## Yerleşim / çerçeve — sayfa JSON'unda değil {#layout-chrome}

page-chrome, page-nav, page-toc sayfa JSON'unda değil, HTML iskeletinde tanımlanır. İskelet src/html_doc/templates/starter.html dosyasından kopyalanır ve ona genellikle dokunmazsınız.

```html
<page-chrome></page-chrome>

<div class="layout">
  <page-nav></page-nav>
  <main id="main-content"></main>
  <page-toc></page-toc>
</div>

<script>
  window.addEventListener('DOMContentLoaded', function () {
    OkuRenderer.autoBoot();
  });
</script>
```

- `<page-chrome>` — sağ üstteki sistem kümesi (arama, uyarı, tema düğmesi). Kenar çubukları için kenar sekmeleri. Visual Viewport parmakla yakınlaştırma izleyicisi.
- `<page-nav>` — İçindekiler çekmecesinin üstündeki kutulu site ağacı; site-manifest.json dosyasını okur (standalone derlemelerde gömülü window.__okuManifest değerini). Etkin sayfayı işaretler. Onu sol üstteki çerçeve şeridinde duran İçindekiler düğmesi sürer ve düğmenin ne yaptığı onu nasıl kullandığınıza bağlıdır: üzerine gelirseniz panel sayfanın üstünde belirir, bir başlık seçene ya da uzaklaşana kadar durur, metnin genişliğine dokunmaz; tıklarsanız sabitlenir, sütunu içeri alır ve anahat yanınızdayken okursunuz, vurgu da bulunduğunuz yeri izler. Sabitlenmiş panelde bir başlığa tıklamak paneli kapatmadan gezinir. 900px'in altında içeri alacak yer olmadığı için tıklama paneli yine sayfanın üstünde açar. Alttaki bilgi satırı kit sürümünü taşır.
- `<page-toc>` — aynı sol kenar çubuğunda site ağacının altına yerleşen bölüm içindekiler listesi. Başlığı geçerli sayfanın adını gösterir; liste, işleyici oku:rendered olayını verdikten sonra main > section > h2/h3 öğelerinden kurulur.

> [!TIP] Yerleşimi özelleştirmek
> Kitin varsayılanları bilgi tabanı sayfalarının neredeyse hepsinde çalışır. Tek seferlik sayfalarda (gezinmesiz, tek sayfalık bir çıktı) iskeletten `<page-nav>` öğesini çıkarın. O olmayınca yerleşim iki sütuna döner (içindekiler solda, v1'deki gibi). İşleyici bunu umursamaz; ona ait olan yalnızca `<main>` öğesidir.

## Kesişen özellikler {#cross-cutting}

Yeni bir blok türü getirmeyen ama var olan bir bloğun nasıl işlendiğini değiştiren davranışlar.

### ext-ref üzerinden kaynak kartları {#ext-ref-cards}

Var olan `ext-ref` girdileri, türüne göre renklenen kaynak kartlarına kendiliğinden yükselir (paper / rfc / release / blog / other). Tür, extref girdisinden okunur ya da bağlantının alan adından çıkarılır. Satır içi kaynak metni, noktalı alt çizgisinde türün rengini alır; üzerine gelince açılan kart tür tonunda bir simge, tek aralıklı bir alan adı rozeti, isteğe bağlı yazar + tarih satırı ve bir özet taşır.

Satır içi örnek — kartı görmek için herhangi bir kaynağın üzerine gelin: özgün anlık görüntü yalıtımı savunması için [Iceberg makalesi](#x/Iceberg paper), HTTP sorun ayrıntıları biçimi için [RFC 9457](#x/RFC 9457), motorlar arası sıralama düzenleri için [Iceberg 1.4 sürümü](#x/Iceberg 1.4 release).

### Birlikte vurgulanan çiftler · [data-bind] {#data-bind}

Herhangi iki bloğa `bind: "step-3"` ekleyin; biri üzerine gelindiğinde ya da odaklandığında ikisi birden parlar. Birine tıklayın — ekran dışında kalan eşi görünür alana kayar. Çift başına tek satırlık katılım; tür değişikliği gerekmez.

Satır içi örnek — bu paragrafın üzerine gelin ya da odaklanın, aşağıdaki callout eşzamanlı olarak renklenir. İkisi aynı data-bind anahtarını paylaşır.

> [!TIP] Eşlenmiş callout
> Yukarıdaki paragrafın üzerine gelmek bu callout'un kenarlığını yakar. Bu callout'un üzerine gelmek paragrafı yakar. Aynı anahtar, iki yön.

### Son güncelleme satırı {#meta-updated}

`meta.updated`, kapak üstveri satırının altında sessiz, eğik bir satır olarak işlenir. Salt güven işareti — okuyucu sayfanın ne kadar taze olduğunu bir bakışta anlar.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"page\",\n  \"title\": \"Notum\",\n  \"meta\": {\n    \"date\": \"2026-05-10\",\n    \"updated\": \"2026-05-18\",\n    \"read_time\": \"~3 dk\"\n  },\n  \"blocks\": [ ... ]\n}","lang":"json"},"output":"<div style=\"padding:14px 16px; background:var(--surface-2); border:1px solid var(--border-soft); border-radius:10px; line-height:1.5;\"><div style=\"font:600 22px Inter,sans-serif; color:var(--text); margin-bottom:6px;\">Notum</div><div style=\"font-size:12.5px; color:var(--text-soft); letter-spacing:0.02em;\">~3 dk okuma · 2026-05-10</div><div style=\"margin-top:4px; font-size:11.5px; color:var(--text-faint); font-style:italic; letter-spacing:0.02em;\">Son güncelleme 2026-05-18</div></div>"}
```

### Uyarı kutusu eşadları {#admonition-aliases}

Callout `type` alanı hem kitin özgün adlarını (`warn / warning / danger / success / neutral`) hem de sektörde yerleşik eşadları (`note / tip / info / caution`) kabul eder. Aşağıdaki her satır, iki ayrı sözcük dağarcığından ulaşılan aynı asıl biçimlendirmedir.

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"note\",\n  \"title\": \"note · neutral eşadı\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!NOTE] note · neutral eşadı\n> `type: \"note\"`, `type: \"neutral\"` ile aynı okunur — genel bilgilendirme tonu."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"tip\",\n  \"title\": \"tip · success eşadı\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!TIP] tip · success eşadı\n> `type: \"tip\"`, `type: \"success\"` ile eşleşir — olumlu öneri için yeşil vurgu."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"info\",\n  \"title\": \"info\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!INFO] info · bilgilendirme tonlu neutral eşadı\n> Yüzeyi neutral ile aynı; ayrılmış ad, Docusaurus / Mintlify alışkanlıklarını bozmadan bırakır."}
```

```oku-example
{"code":{"k":"code","src":"{\n  \"kind\": \"callout\",\n  \"type\": \"caution\",\n  \"title\": \"caution · warning eşadı\",\n  \"content\": \"...\"\n}","lang":"json"},"output":"> [!CAUTION] caution · warning eşadı\n> Kehribar kenarlık ve simge; `type: \"warning\"` ile aynı görünür."}
```

[^ref-demo]: Tanımlar sayfanın herhangi bir yerinde durabilir — işleyici hiçbir şey üretmeden önce hepsini toplar, sonra kullanılanları burada listeler.

[pagefind-site]: https://pagefind.app "Pagefind"
