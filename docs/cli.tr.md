---
title: CLI başvurusu
eyebrow: Başvuru
subtitle: Dokuz komut - oku init, build, clean, spec, vendor, verify, migrate, check, serve. Çoğu zaman CLI'nin varlığını unutacak şekilde tasarlandı.
date: 2026-05-18
order: 50
summary: oku init / build / clean / spec / vendor / verify / migrate / check / serve — her birinin ne yaptığı.
---

> [!TLDR]
> init, içinde bulunduğunuz dizini belge kökü olarak hazırlar: _oku sembolik bağı + index.html giriş taslağı. build tek amaçlı iki ağaç üretir — dist/standalone/ ve dist/site/ (manifesto + llms.txt + Pagefind ile). clean dist/ dizinini siler. migrate sayfa-JSON kaynaklarını v3 markdown'a çevirir. check her sayfayı denetler. serve yerel bir HTTP sunucusu çalıştırır ve manifestoyu, llms.txt'yi ve kit.json'u bellekte üretir — kaynak dizinleri tek giriş taslağı dışında temiz kalır.
>
> - init, içinde bulunduğunuz dizini belge kökü sayar. Sayfaların duracağı yerden çalıştırın (genellikle önce docs/ alt dizinine geçin).
> - Kaynak dizinleri MD (ya da eski JSON) dosyalarını ve tek bir index.html giriş taslağını tutar; böylece IDE üzerinden sunulan akışlar geliştirme sunucusu çalışmadan da işler.
> - build aynı sonucu verir; yeniden çalıştırmak güvenlidir. dist/standalone/ ve dist/site/ her seferinde silinir.
> - clean dist/ dizinini tümüyle kaldırır — zaten yoksa hiçbir şey yapmaz.
> - serve manifestoyu her istekte yeniden üretir — kaynağa hiçbir şey yazılmaz.
> - jsonschema zorunlu bir bağımlılıktır (sayfa doğrulaması); pagefind ise isteğe bağlı `oku[search]` ek paketidir (arama dizini).

## oku init {#init}

Belge kökü başına bir kez. Sayfaların _oku/chrome.js gibi yolları kullanabilmesi için bir _oku sembolik bağı ve IDE üzerinden sunulan akışların doğrudan açtığı bir index.html giriş taslağı oluşturur (IntelliJ'in yerleşik HTTP sunucusu, Live Server vb.). İkisi de içinde bulunduğunuz dizine iner — örtük bir docs/ alt dizini yoktur.

```bash
cd ~/path/to/your-project/docs
oku init

# ✓ Linked /path/to/your-project/docs/_oku -> /path/to/oku/kit
# ✓ Created /path/to/your-project/docs/index.html
#
#   Author pages as <name>.md next to index.html (JSON still works).
#   Open index.html in your IDE, or run `oku serve` from the
#   project root for a live-reloading dev server.
```

> [!NEUTRAL] Yinelenebilir ve kendini onarır
> init'i yeniden çalıştırmak güvenlidir. Sembolik bağ zaten kite çözümleniyorsa "already linked" yazar. Bayat bir hedefi gösteriyorsa (örneğin kit deposu taşınmışsa) init onu sessizce tazeler. _oku konumunda sembolik bağ olmayan bir dosya varsa bu kullanıcı verisi sayılır ve işlem reddedilir. Var olan bir index.html'e dokunulmaz, böylece düzenlemeleriniz korunur.

## oku build {#build}

İçinde bulunduğu dizini gezer, bütün dist çıktılarını üretir. dist/site/ dizinini yayımlamadan önce, dist/standalone/ dosyalarını paylaşmadan önce ya da arama dizininin tazelenmesi gereken her seferde çalıştırın. Kaynak dizinine hiçbir zaman yazılmaz.

```bash
cd ~/path/to/your-project
oku build

# ✓ Doctree check: 6 page(s) clean
# ✓ Wrote dist/site/site-manifest.json (6 JSON page(s))
# ✓ Wrote dist/site/llms.txt
# ✓ Synthesized 6 stub(s) for pages without on-disk .html
# ✓ Pagefind index built: dist/site/pagefind/
# ✓ Built 6 HTML file(s):
#
#   standalone (inline, send-as-file):
#                file:///.../dist/standalone/docs/index.html
#                ...
#
#   site (shared assets, multi-page):
#   site root:   file:///.../dist/site
#                ...
```

```oku-step-flow
{"steps":[{"t":"*.json ve *.md sayfalarını özyinelemeli gez","b":"dist/, _oku/, node_modules/, .git/, venv/, __pycache__/, bütün nokta ile başlayan dizinler ve kit.json içindeki skip_dirs girdileri atlanır. Proje isterse .gitignore dosyasını da bu listeye ekleyebilir: kit.json içinde \"skip_gitignored\": true — varsayılan olarak kapalıdır, çünkü bir projenin sürüm denetiminin dışında tuttuğu şey ile sitesinin dışında tuttuğu şey ayrı sorulardır. Açıkken git'in neyi elediğini check ve build tek satırda söyler. kind:\"page\" taşıyan dosyalar (ve bütün .md dosyaları) sayfa sayılır."},{"t":"Şema doğrulaması","b":"Her sayfa kit/schema/page.schema.json şemasına göre denetlenir. Hatalar alan yollarıyla birlikte yazılır. jsonschema zorunlu bir bağımlılık olduğundan kurulu bir oku bu geçişi her zaman çalıştırır; düz `python3 bin/oku` yolu bunu atlayabilir, orada build tek satırlık bir ipucu yazıp geçer."},{"t":"build_standalone — sayfa başına tek dosya (insanlar, file://)","b":"Her sayfa için HTML taslağı bellekte üretilir; chrome.css/.js, chrome-boot.js, renderer.js, sayfa JSON'u, kit paketi ve site manifestosu çekirdeği (window.__okuManifest) dosyanın içine gömülür. Sayfa başına kendi kendine yeten tek dosya; yan dosya yok. Çıktı, dizin yapısı korunarak dist/standalone/ altına yazılır."},{"t":"build_site — çok sayfalı yayımlanabilir çıktı (insanlar, HTTP)","b":"Sayfa başına bir taslak yazılır ve kaynak JSON, dizin yapısı korunarak dist/site/ altına kopyalanır. Kit bir kez dist/site/_oku/ içine kopyalanır. Site kökünde, kopyalanmış kitin yanında tek bir site-manifest.json yazılır (chrome.js belge kökünü _oku/ dizininin durduğu yerden çözer ve manifestoyu çalışma anında oradan çeker). Dizine alınması için çıkarılan metin gizli data-pagefind-body içine yerleştirilir."},{"t":"build_llms_txt (LLM tüketicileri)","b":"Site kökünde, manifestonun yanına tek bir llms.txt site haritası (llmstxt.org uzlaşımı) bırakılır. Yapay zekâ için asıl yüzey .md sayfa kaynaklarının kendisi olduğundan ikiz bir ağaç üretilmez."},{"t":"Pagefind dizini (isteğe bağlı)","b":"dist/site/ üzerinde pagefind çalıştırılır; önce pagefind[bin] Python paketiyle gelen ikili dosya (oku[search] ek paketiyle kurulur), sonra PATH üzerindeki pagefind, sonra npx pagefind denenir. Çıktı dist/site/pagefind/ altına yazılır. Hiçbiri yoksa kurulum ipucuyla birlikte sessizce geçilir."}]}
```

> [!WARN] build kendi dist ağaçlarını siler
> build, yeniden üretmeden önce dist/standalone/ ve dist/site/ dizinlerini kaldırır (eski bir derlemeden kalmışsa dist/markdown/ dizinini de), böylece bayat dosyalar birikmez. dist/ altına koyduğunuz başka her şeye dokunulmaz — bütün dist/ ağacını silmek için oku clean kullanın.

### Okuduğum sayfanın güncel olduğunu nereden bilirim? {#build-provenance}

İçeriğe bakarak anlayamazsınız; giderilmiş bir kusurun eski bir dosyadan ikinci kez bildirilmesi böyle olur. Bu yüzden üretilen her sayfa, kendi künyesini kenar çubuğunun altında, site ağacının hemen altında taşır:

```
oku v0.6.5 · kit 2026-08-14-r37
built 3 days ago                     [Rebuild]
```

`kit`, `oku --version` çıktısındaki alanın aynısıdır ve aynı biçimde yazılır; böylece kenar çubuğu ile uçbirim doğrudan karşılaştırılabilir. Damga kendi tarihini taşır — güncel numarayı bilmeden "bu dosya ne kadar eski" sorusunu tek bir sayının yanıtlamasını sağlayan şey budur.

**Rebuild bir komut kopyalar. Komutu çalıştırmaz, çalıştıramaz da.** `file://` adresinden ya da durağan bir sunucudan açılan bir sayfanın kabuğa ulaşan bir kanalı yoktur. Canlı sunucusu olan tek yüzey `oku serve`'dür; orada da `_oku/` kurulu kiti gösterir, yani sunulan sayfa hiçbir zaman bayat olan değildir — gerçek bir yeniden üretme düğmesi yalnızca kimsenin ihtiyaç duymadığı yerde çalışırdı. Tıklama komutu hem gösterir hem kopyalar:

```bash
cd ~/code/notes && oku build
```

`cd` şundan var: üretilmiş bir dosya kaynağının nerede durduğu hakkında hiçbir şey söylemez, siz de onu başka bir yerden okuyorsunuz. Yol, ev dizininizin altındaysa `~` ile kısalır ve yalnızca `dist/` içine ve tek dosyalık sayfalara yazılır — sürüm denetimine giren `index.html` taslağına hiçbir zaman yazılmaz.

Sayfanın size söyleyemeyeceği şey, kurulu kitin ne kadar gerisinde kaldığıdır. Bunu öğrenmek ağa sormak demektir; bir belge de bir meslektaşınız açtı diye kendi başına ağa çıkmamalıdır. Bu karşılaştırmayı, iki sayıyı da elinde tuttuğu tek anda, `oku build` yazdırır:

```
✓ Built 12 HTML file(s):
  kit 2026-08-11-r33 → 2026-08-14-r37
```

## oku clean {#clean}

Geçerli proje kökündeki dist/ ağacını kaldırır. Yinelenebilir — dist/ yoksa hiçbir şey yapmaz. Kaynak dosyalara ve _oku sembolik bağına dokunulmaz.

```bash
oku clean

# ✓ Removed /path/to/your-project/dist

# Second run, nothing left:
oku clean

# ✓ Nothing to clean — /path/to/your-project/dist does not exist.
```

- Bir sürüm çıktısı yayımlamadan, dal değiştirmeden önce ya da sadece temiz bir derlemeden emin olmak için işe yarar.
- Zincirlemek güvenli: oku clean && oku build.
- Kaynak sayfalara, _oku sembolik bağına ya da kit.json'a dokunmaz. Yalnızca üretilmiş çıktıyı siler.

## oku spec {#spec}

Herhangi bir blok türü ya da grafik türü için doğrudan yapıştırılabilir
bir veri gövdesi yazdırır. Kitte 14 blok türü ve 53 grafik türü var;
bunların biçimi, yazarın o an yazdığı sayfaya bakarak çıkaramayacağı tek
şey.

```bash
oku spec                # bütün adlar, gruplanmış
oku spec sankey         # yapıştırmaya hazır çit
oku spec table --json   # çitsiz, yalnızca veri gövdesi
```

```oku-table
{"headers":["Argüman","Varsayılan","Etkisi"],"rows":[["`name`","—","Bir blok türü (`table`, `kpi-grid`, …) ya da bir grafik türü (`sankey`, `gantt`, …). Bütün adları listelemek için boş bırakın. Tanınmayan bir ad 1 ile çıkar ve en yakın eşleşmeleri önerir."],["`--json`","kapalı","Çiti değil, yalnızca veri gövdesini yazdırır. Veri gövdesini program içinde oluştururken işe yarar."]]}
```

Örnekler tekerleğin içinde dağıtıldığı için bu komut, aracı kuran her
projede çalışır — kitin kendi belge ağacında duran
[kaynak sayfasının](reference.tr.md) aksine. Her örneğin hem şemaya hem
de yapısal denetimlere uygunluğu sınanır; dolayısıyla yazdırdığı şey
`oku check`'ten olduğu gibi geçer.

## oku verify {#verify}

Üretilen sayfaları başsız bir tarayıcıda açar ve kaynak denetiminin
göremediğini bildirir. `oku check` kaynağı okur; bu, sonucu okur.

```bash
oku build && oku verify

# ✓ 38 page(s) render clean at 1440px and 360px
```

```oku-table
{"headers":["Denetlenen","Kaynak denetimi neden göremez"],"rows":[["Diyagramlar çizildi mi","Kaynak ayrıştırılıyor; asıl başarısız olan çizici ve bu yalnızca tarayıcıda görülür."],["Hiçbir figür boş kutu değil","Geçerli ama yanlış bir veri gövdesi doğrulamayı geçer ve hiçbir şey çizmez. Şemanın yapısı gereği ulaşamadığı hata budur."],["1440px ve 360px'te yana kaydırma yok","Taşma bir geometri sorunudur; kaynakta hiçbir karşılığı yoktur."],["Konsol ya da sayfa hatası yok","Bir adacığın betiği hata fırlattığında bunu hiçbir durağan denetim göremez."]]}
```

Tarayıcı gerekir: `uv tool install 'oku[verify]'` ardından
`playwright install chromium`. Tarayıcı yoksa komut bunu söyler ve 2 ile
çıkar; almadığı bir başarıyı bildirmez.

Uzak bir adrese giden isteğin başarısız olması yok sayılır — bu, sayfanın
değil ağın durumudur ve yazarın düzeltemeyeceği sebeplerle başarısız olan
bir denetime kimse güvenmez. Yerel dosyaların eksikliği bildirilir.

## oku vendor {#vendor}

İki çalışma zamanı bağımlılığını bir kez indirir; böylece üretilen
sayfalar ağ olmadan da çalışır. Diyagramları mermaid çizer, kodu Prism
renklendirir; ikisi de her sayfa açılışında bir CDN'den yükleniyordu.

```bash
oku vendor            # eksik olanı indir
oku vendor --update   # yeniden indir (yeni bir sürüm çıktıysa)
```

```oku-table
{"headers":["Argüman","Varsayılan","Etkisi"],"rows":[["`--update`","kapalı","Kopya yerinde olsa bile yeniden indirir. Yeni bir sürüme geçerken kullanın."],["(yok)","—","Yalnızca eksik olanı indirir. `oku build` bunu ilk seferde kendisi yapar, dolayısıyla çoğu proje bu komutu hiç çalıştırmaz."]]}
```

Dosyalar kurulu kitin `vendor/` dizinine iner; yani makine başına bir kez
indirilir ve bütün projeler aynı kopyayı kullanır. `oku build` çıktının
yanına tek bir `_oku/vendor/` kopyalar; her sayfa o kopyayı okur, orada
bulamazsa CDN'e döner.

Bağımlılıklar sayfaların içine **gömülmez**. mermaid tek başına 3,3 MB;
buna karşılık tek dosyalık bir sayfa 1,1 MB. Gömülseydi, çizim içeren her
sayfa kendi kopyasını taşırdı. Çevrimdışı çalışmak tek dosya olmayı
gerektirmez; baytların ağ olmadan erişilebilir olmasını gerektirir.

## oku migrate {#migrate}

Sayfa-JSON kaynaklarını (v1 ya da v2) v3 markdown'a çevirir. Her `foo.json` yanındaki `foo.md` dosyasına dönüşür ve JSON kaldırılır. Göç isteğe bağlıdır — işleyici v1/v2 sayfaları süresiz kabul eder — bu yüzden diskteki kaynağı güncel yazım biçiminde istediğinizde çalıştırın.

```bash
cd ~/path/to/your-project/docs
oku migrate

#   migrated architecture.json → architecture.md
#
# Migrated 1 page(s).

# Nothing left to convert:
oku migrate

# ✓ No page-JSON files found under /path/to/your-project/docs
```

```oku-table
{"headers":["Değişken","Öntanımlı","Etkisi"],"rows":[["`path`","`.`","Göç ettirilecek dosya ya da dizin. Dizin özyinelemeli gezilir; kit.json, site-manifest.json, package.json ve tsconfig.json atlanır, sayfa olmayan her şey de öyle."],["`--dry-run`","kapalı","Değişecek dosyaları yazdırır, hiçbir şey yazmaz. Yine 0 ile çıkar."],["`--keep-json`","kapalı","Kaynak .json dosyasını üretilen .md yanında bırakır. Araçlar .json'u yeğlediğinden, kalan dosya siz onu silene kadar .md dosyasını gölgeler."]]}
```

Silmeyi güvenli kılan iki koruma var. `.md` dosyası zaten bulunan bir sayfanın üzerine yazılmaz, atlanır; ayrıca her dönüşüm, JSON silinmeden önce bellekte gidiş dönüş sınanır — üretilen markdown geri ayrıştırılıp kaynakla parmak izi karşılaştırması yapılır. Kayıpsız gidip dönemeyen sayfa atlanır, kaynağı korunur ve durumu bildirmenizi isteyen bir ileti yazılır.

Çıkış kodu yalnızca girdi yolu yoksa 1 olur; hiçbir şey göç ettirmeyen bir çalıştırma da 0 ile çıkar.

## oku check {#check}

Projedeki her sayfayı denetler — `.md` kaynaklarını da sayfa-JSON dosyalarını da. Şema doğrulaması artı yapısal ve içeriksel denetimler. Hızlıdır, milisaniyelerle ölçülür. oku becerisinin kendiliğinden doğrulama adımı olarak tasarlandı.

```bash
oku check

# ✓ 11 page(s) clean (schema + structural + content)
#
# oku check --strict       # exit 1 on warnings too
# oku check --json         # machine-parseable output
# oku check --verbose      # also surface info-level nudges
# oku check --errors-only  # suppress warnings in the report
```

Bulgular üç önem derecesine ayrılır; `--json` çıktısında bunlar `error` / `warning` / `info` olarak görünür. Herhangi bir hata varsa (ya da `--strict` altında herhangi bir uyarı varsa) çıkış kodu 1, aksi hâlde 0 olur.

```oku-table
{"headers":["Önem","Kodlar","Neyi yakalar"],"rows":[["**hata**","`schema`, `deprecated-kind`, `unknown-kind`, `invalid-block`, `duplicate-anchor`, `chart-*`, `stray-demo`, `no-title`, `shadowed-source`, `json-parse-failed`","Sayfa yapısı sorunları, kaldırıldığı hâlde hâlâ kullanılan yapı taşları, ne markdown metni ne de türü belirtilmiş nesne olan bir gövde girdisi, yinelenen bölüm / başlık kimlikleri, bozuk grafik yükleri, docs/reference.md dışında kalan örnek sayfalar, başlıksız bir sayfa, düzenlediğiniz kaynağı gölgeleyen bir .json."],["**hata** · markdown","`fence-not-lifted`, `setext-heading`, `island-unclosed`","Gövdesi bilinen bir türden tek bir JSON nesnesi olmayan `oku-*` çiti; türlü bloğa dönüşemediği için kod bloğu olarak kalmıştır. Setext (`===` alt çizgili) başlık — katı GFM alt kümesi yalnızca ATX `#` başlıklarını kabul eder. Etiketi hiç kapanmayan bir HTML adacığı: ardından gelen her şey onun içine yazılır, yani bölümün geri kalanını da içine alır — hem sayfa sonunda hem de her `##` başlığında bildirilir, çünkü bölüm sınırı, motorun tek geçişte işlediği blok dizisini bitirir."],["**uyarı**","`process-breadcrumb`, `placeholder-text`, `unresolved-glossary`, `unresolved-extref`, `unresolved-link`, `unresolved-anchor`, `filepath-missing`, `filepath-outside`, `unknown-meta-key`, `translation-anchor-drift`","Süreç ya da geçmiş göndermesi içeren metin (round-N, vN-review, fixed-in-round; kit yalnızca güncel davranışı belgeler). Hâlâ yer tutucu taşıyan metin (TODO, TBD, lorem ipsum, XXX). kit/glossary/ ve kit/extrefs/ altında karşılığı bulunmayan sözlük terimleri ve dış kaynaklar. Sayfaya göre var olmayan bir dosyayı ya da işaret ettiği sayfada başlık kimliği bulunmayan bir `#parça` adresini gösteren bağlantı veya görsel. O yolda dosya bulunmayan ya da proje kökünün dışına çıkan bir `#f/` dosya göndermesi — sayfa, önizlediği dosyaların baytlarını içinde taşır; projenin dışına uzanan bir gönderme bunları yayımlamış olurdu, bu yüzden o rozet yalnızca kopyalanabilir bir yol gösterir. Kitin tanımadığı bir ön bilgi anahtarı; en yakın tanıdığı anahtarla birlikte bildirilir. Sayfanın bir dilinde bulunup çevirisinde bulunmayan başlık kimliği — dil düğmesi okurun parça adresini karşıya taşıdığı için, okuru içinde derinlemesine gezdiği sayfanın en başına düşürür."],["**uyarı** · markdown","`ambiguous-hr`, `heading-level-skip`, `indented-code`, `lazy-continuation`, `undefined-footnote`, `undefined-link-reference`","Metin satırının hemen altındaki `---`: CommonMark'ta setext başlık, kitte yatay çizgi — öncesine boş satır koyun. Bir düzey atlayan başlık (`##` ardından doğrudan `####`); bu, ekran okuyucular ve sayfa içi içindekiler için ana hattı bozar. Boş satırdan sonra gelen dört boşluk girintili blok; CommonMark bunu kod bloğu, kit ise paragraf okur. `>` işareti olmadan sürdürülen alıntı satırı. Sayfada tanımı bulunmayan bir `[^id]` ya da `[label]` göndermesi — düz metin olarak işlenir, başka hiçbir işaret vermez."],["**uyarı** · sunum","`redundant-meta`, `prose-only-section`, `island-hand-styled`, `group-of-one`, `figure-restates-headings`","Bir başkasını yineleyen alan (`summary` metnini olduğu gibi taşıyan `subtitle`, `date` değerini taşıyan `updated`). Göze hitap eden hiçbir şey içermeyen, üç ya da daha çok paragraflık bölüm — tablo, grafik, şema, kart ızgarası ya da kod bloğu yok; bilgi kutusu sayılmaz. Kitin sınıfları ve CSS değişkenleri üzerine kurulmak yerine sabit renkler ya da kendi `<style>` bloğunu taşıyan HTML adacığı. Tek üyeyle kullanılmış karşılaştırma ızgarası / adım akışı / KPI ızgarası / grafik ızgarası; oysa bu yapı taşlarının bütün işi üyeler arasındaki ilişkidir. Düğüm etiketleri sayfanın kendi bölüm başlıkları olan bir şema."],["**bilgi**","`code-no-language`, `no-summary`, `html-island`, `empty-table`, `hand-set-derivable`, `accent-divergence`, `filepath-not-carried`","Dili bildirilmemiş kod blokları. meta.summary alanı olmayan sayfalar. HTML adacıkları (kitte işlenirler, dış markdown görüntüleyiciler bunları atar). Başlıkları olan ama satırı olmayan tablo. Derlemenin kendi türettiği bir alanın elle doldurulmuş olması. Aynı dizindeki üç ya da daha çok sayfanın, kit.json'da öntanımlı bir değer yokken farklı vurgu renkleri seçmesi. Sayfanın içinde taşınamayacak kadar büyük bir `#f/` dosyası; rozet dosyayı adlandırır ve yolunu kopyalar, önizleme sunmaz."]]}
```

> [!TIP] oku beceri akışına eklemek
> Bir HTML çıktısını bitti saymadan önce oku check --strict çalıştırın. Bulguları programla işlemek için --json kullanın. Denetleyici, kendiliğinden doğrulama döngüsünün en hızlı adımıdır — tarayıcı gerekmez.
>
> Sunum kuralları, bilgilendirmenin bunları düz metin olarak taşımak zorunda kalmaması için var. Bir kılavuza yazılmış biçem kuralı zamanla çürür, çünkü göz ardı edildiğinde hiçbir şey başarısız olmaz; denetleyicinin uyguladığı kural çürümez. Burada yalnızca karara bağlanabilir olan yarısı yaşıyor — şemanın asıl noktayı taşıyıp taşımadığı hâlâ okurun sorusu.

## oku serve {#serve}

Proje kökünde yerel HTTP sunucusu. Sayfa başına .html taslaklarını, site-manifest.json ve llms.txt dosyalarını her istekte bellekte üretir — kaynak dizini temiz kalır. 9876'dan başlayarak ilk boş kapıyı seçer.

```bash
oku serve

# ✓ Serving /path/to/your-project on http://localhost:9876
#   Stop with Ctrl-C.
#
#   HTML files:
#     http://localhost:9876/docs/index.html
#     http://localhost:9876/docs/reference.html
#     ...
```

- İçinde bulunduğu dizinden yukarı doğru yürüyerek docs/_oku dizinini barındıran klasörü bulur ve oradan sunar. Projenin herhangi bir yerinden çalıştırabilirsiniz.
- 9876–9900 aralığındaki ilk boş kapı. 9900'de durur (hepsi doluysa hata verir).
- Yanındaki .json ya da .md dosyalarından /<docs>/<name>.html taslaklarını anında üretir; site-manifest.json ve llms.txt için de aynısını yapar. Dosya sistemine hiçbir şey yazılmaz.
- Pagefind serve tarafından kurulmaz. Tam metin arama gerekiyorsa önce oku build çalıştırın; aksi hâlde serve sayfa içi çapa aramasına düşer.
- Bulduğu ilk HTML dosyasını öntanımlı tarayıcıda açar. Durdurmak için Ctrl-C.

> [!TIP] Neden file:// değil de HTTP
> Tarayıcılar yerel dosyalara HTTP'den farklı kurallar uygular — sembolik bağ çözümü, fetch ve ES modül içe aktarmaları file:// üzerinde sessizce başarısız olur ya da tutarsız davranır. Yerel HTTP sunucusu bunu aşar. macOS'ta bir file:// adresi açmak ayrıca <live-snippet> içindeki iframe kum havuzu için önemli olan bazı aynı-kaynak kurallarını devre dışı bırakır. Her zaman sunucudan açın.

> [!NOTE] İsteğe bağlı bayraklar
> <strong>--no-watch</strong> dosya sistemi izleyicisini ve canlı yenilemeyi kapatır (yalnızca durağan sunum).<br><strong>--no-search</strong> başlangıçtaki arka plan Pagefind dizin üretimini atlar. İkisi de öntanımlı olarak açıktır, böylece geliştirme döngüsü zengin olur; daha hafif bir serve isterseniz kapatın.

## Bağımlılıklar {#optional-deps}

Biri zorunlu, biri isteğe bağlı.

```oku-compare-grid
{"cards":[{"t":"jsonschema — sayfa doğrulaması, zorunlu","b":"Temel `dependencies` listesinde bildirildiği için kurulu her oku onu taşır. Bir zamanlar isteğe bağlıydı ve sonucu şu oldu: `oku check` bir sayfayı temiz ilan ederken o sayfanın üç bloğu boş alan olarak işleniyordu — kurulu araçta jsonschema yoktu, şema geçişi sessizce boşa döndü ve yalnızca yapısal denetimler çalıştı. Sessiz geçiş dalı, bunu hâlâ atlayabilen tek yol için duruyor: uv olmadan `python3 bin/oku`. Orada build bir ipucu yazar ve doğrulamayı geçer.","verdict":"neutral"},{"t":"pagefind — arama dizini, isteğe bağlı","b":"`search` ek paketi (`oku[search]`) kendi ikili dosyasını getiren `pagefind[bin]` paketini çeker — brew, npm ya da npx gerekmez. PATH üzerindeki bir `pagefind` ya da `npx pagefind` de çalışır; build önce paketle gelen ikiliyi, sonra PATH'i, sonra npx'i dener. Hiçbiri yoksa: arama düğmesi yine görünür ama tıklandığında \"Search index not found\" der. Biri varsa: build, dist/site/ altına ~50–100 KB'lık bir pagefind/ dizini ekler.","verdict":"neutral"}]}
```

## Kurulum ve çalıştırma {#future}

Sık sorulduğu için burada duruyor.

CLI'yi çağırmanın iki yolu var.

### uv ile kurulu {#installed-via-uv}

```bash
uv tool install .
# Now `oku` is on PATH globally:
oku serve
```

oku'yu bir konsol betiği olarak kurar. Tekerlek paketi chrome.{css,js}, schema/, glossary/ ve extrefs/ dosyalarını oku/assets/ içine, başlangıç şablonlarını da oku/templates/ altına koyar; böylece init ve build her şeyi bir git yerleşimi olmadan bulur.

### Kurulum olmadan ağaç içinde {#in-tree-without-install}

```bash
uv run bin/oku serve
# Or plain python3 — both work:
python3 bin/oku serve
```

`bin/oku`, `src/` dizinini sys.path'e ekleyip `oku.cli.main()` çağıran ince bir ara katmandır. PEP 723 satır içi üstverisi, uv ile çağrıldığında jsonschema'yı geçici bir sanal ortama çeker.
