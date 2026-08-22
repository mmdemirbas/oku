---
title: Yol haritası
subtitle: Az önce yayımlananlar, hâlâ açık olanlar ve kitin biçimini belirleyen kilitli kararlar.
audience: Bakımcı
order: 999
summary: oku için açık işler, son eklenenler ve kilitlenmiş tasarım kararları.
accent: amber
---

> [!TLDR]
> Grafik kitinin büyük bölümü etkileşimlidir — bilgi balonları, tıklayarak sabitleme, imleç süpürmesi, tam ekranda etkileşimi koruyan lightbox, çakışmayan etiketler, tıklanabilir mini kartlarla aileye göre gruplanmış katalog. Açık işler uzun kuyruktaki gösterge etkileşimi, sürüklenebilir ağ düğümleri, lightbox kaydırma çubuğu + mini harita ve iç içe dillerde kod vurgulama çevresinde yoğunlaşıyor.
>
> - Etkileşim kapsamı: aşağıdaki tablodaki her tür, imleç üzerine gelindiğinde gerçek çapa verisiyle bağlama duyarlı bir bilgi balonu açar. Kartezyen + ridgeline + sparkline + gauge, bilgi balonunu konuma göre güncelleyen eşlenik bir imleç taşır.
> - Görsel incelik: quadrant + bubble etiket çakışma çözümü uçuşa yasak bölgeleri gözetir. Parallel-coordinates çizgi kalınlığı 3.6 → 5px, imleçle birlikte diğerleri solar. Donut/pie'da sabitlenen dilimler büyür ve vurgu çizgisi alır. Mermaid yazı boyutu 13px ile sınırlanır, en-boy uyumu uzun dikey şemaları kırpar.
> - Yerleşim: kaynak / çıktı sütunları reference / charts / tables sayfalarındaki her örnek çiftinde kutu üstünden hizalıdır — piksel farkı sıfır.
> - Bilgi balonu: genişliği sabitleme durumları arasında değişmez; sabitlendiğinde açık bir × kapatma düğmesi çıkar; `_tipPinned` bayrağı imleçle sürülen grafiklerin sabitlenmiş içeriğin üzerine yazmasını engeller.
> - Aileye göre seçim: her biri küçük bir canlı çizim taşıyan 43 tıklanabilir mini kart — okuyucu istediği biçimi görüp doğrudan o türün tam örneğine tıklar.
> - Panonun diğer yarısı sağlamlık: pakete alınmış yazı tipleri, atomik derleme,
>   dinleyicilerin bırakılması, klavyeyle açılan kenar çubuğu katlaması. On üç
>   madde; aşağıda alana ve önceliğe göre süzülebilir.
> - `oku`, PATH üzerinde bir sistem komutu olarak durur (uv tool install).

## Anlık durum {#snapshot}

Kitin bugün nerede durduğu, sayılarla.

```oku-kpi-grid
{"tiles":[{"num":"53","label":"Şemanın kabul ettiği grafik türü"},{"num":"50","label":"Grafikler sayfasında işlenmiş örneği olan tür"},{"num":"19","label":"Kataloglanmış Mermaid şema türü"},{"num":"11","label":"Grafikler sayfasındaki amaç ailesi"},{"num":"20","label":"oku check --strict altında temiz belge sayfası"},{"num":"1500+","label":"Pytest testi — yeşil"},{"num":"2","label":"oku build başına derleme ağacı (standalone / site)"},{"num":"10","label":"Seri renk rampası (--series-1..10)"}]}
```

## Özelliğe göre grafik etkileşimi {#interactivity}

Hangi grafik türünün hangi etkileşim bileşenini taşıdığı. Dolu hücreler yayımlanmış, boş hücreler kuyruktadır. Tablo 53 türün 28'ini kaydeder; kalanlar henüz burada kataloglanmadı.

```oku-table
{"headers":["Tür",{"label":"Aile","filter":"chips","values":["cartesian","categorical","distribution","part-to-whole","flow","hierarchy","matrix","trend","goal","geo"]},"Bilgi balonu","Tıkla-sabitle","İmleçle vurgu","Eşlenik imleç","Tam ekran"],"rows":[["scatter",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["line",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["area",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["bubble",{"value":"cartesian","values":["cartesian"]},"●","●","●","●","●"],["quadrant",{"value":"cartesian","values":["cartesian"]},"●","●","●","—","●"],["bar",{"value":"categorical","values":["categorical"]},"●","●","●","—","—"],["stacked-bar",{"value":"categorical","values":["categorical"]},"●","●","●","—","—"],["grouped-bar",{"value":"categorical","values":["categorical"]},"●","●","●","—","—"],["donut",{"value":"part-to-whole","values":["part-to-whole"]},"●","●","●","—","●"],["pie",{"value":"part-to-whole","values":["part-to-whole"]},"●","●","●","—","●"],["waffle",{"value":"part-to-whole","values":["part-to-whole"]},"●","●","○","—","●"],["treemap",{"value":"hierarchy","values":["hierarchy"]},"●","●","○","—","●"],["heatmap",{"value":"matrix","values":["matrix"]},"●","●","○","—","●"],["histogram",{"value":"distribution","values":["distribution"]},"●","●","○","—","●"],["sparkline",{"value":"trend","values":["trend"]},"●","●","—","●","●"],["gauge",{"value":"goal","values":["goal"]},"●","●","—","●","●"],["radar",{"value":"categorical","values":["categorical"]},"●","●","○","—","●"],["box-plot",{"value":"distribution","values":["distribution"]},"●","●","○","—","●"],["bullet",{"value":"goal","values":["goal"]},"●","●","○","—","●"],["slope",{"value":"trend","values":["trend"]},"●","●","○","—","●"],["calendar-heatmap",{"value":"trend","values":["trend"]},"●","●","○","—","●"],["ridgeline",{"value":"distribution","values":["distribution"]},"●","●","○","●","●"],["sankey",{"value":"flow","values":["flow"]},"●","●","○","—","●"],["network",{"value":"flow","values":["flow"]},"●","●","○","—","●"],["scatter-matrix",{"value":"matrix","values":["matrix"]},"●","●","○","—","●"],["parallel-coordinates",{"value":"matrix","values":["matrix"]},"●","●","●","—","●"],["chord",{"value":"flow","values":["flow"]},"●","●","○","—","●"],["geo",{"value":"geo","values":["geo"]},"●","●","○","—","●"]]}
```

> [!NEUTRAL] Simge anahtarı
> ● yayımlandı · ○ kuyrukta · — uygulanmaz. Bilgi balonu ve tıkla-sabitle, yukarıda kayıtlı 28 türün tamamında yayımlanmış durumda. İmleçle vurgu (bir öğenin üzerine gelindiğinde ötekilerin solması) Kartezyen olmayan türlerin çoğunda hâlâ kuyrukta. Eşlenik imleç yalnızca süpürme ekseni olan grafiklerde anlamlıdır (Kartezyen, ridgeline, sparkline, gauge). Tam ekran lightbox, SVG grafiklerinde grafik etkileşimini korur; bar türevleri DIV tabanlıdır ve bunun yerine sayfanın olağan kaydırmasını kullanır.

## Açık / sürmekte {#open}

Kanban panosu — kapsamı daraltmak için alana ya da önceliğe göre süzün. Her çip süzer; pano görünümü duruma göre gruplar.

```oku-table
{"view":"board","headers":["Madde",{"label":"Durum","boardOrder":["in-flight","queued","exploring","shipped"]},{"label":"Alan","filter":"chips","values":["charts","diagrams","tables","kit","docs","build"]},{"label":"Öncelik","filter":"chips","values":["P1","P2","P3"]},{"label":"Emek","filter":"chips","values":["S","M","L"]}],"rows":[["Network — okuyucunun grafiği elle çözebilmesi için sürüklenebilir düğümler",{"value":"queued","values":["queued"]},{"value":"charts","values":["charts"]},{"value":"P1","values":["P1"]},{"value":"M","values":["M"]}],["Bütün grafik türlerinde etkileşimli gösterge (donut/pie/waffle/radar/box-plot — Kartezyen + bar davranışına eşitlensin)",{"value":"queued","values":["queued"]},{"value":"charts","values":["charts"]},{"value":"P2","values":["P2"]},{"value":"M","values":["M"]}],["İç içe kod vurgulama (HTML içinde JS, Markdown içinde bash — çitli blok içinde alt dil algılama)",{"value":"queued","values":["queued"]},{"value":"kit","values":["kit"]},{"value":"P2","values":["P2"]},{"value":"M","values":["M"]}],["Lightbox: sığmayan büyütülmüş grafikler için kaydırma çubuğu + resim içinde resim mini haritası",{"value":"queued","values":["queued"]},{"value":"kit","values":["kit"]},{"value":"P2","values":["P2"]},{"value":"M","values":["M"]}],["Kartezyen olmayan grafiklerde imleçle vurgu (ötekileri soldurma) — donut/pie/waffle/treemap/heatmap vb.",{"value":"queued","values":["queued"]},{"value":"charts","values":["charts"]},{"value":"P3","values":["P3"]},{"value":"S","values":["S"]}],["Katalog araştırması — waterfall, marimekko, dot-matrix, joy-plot, sunburst",{"value":"exploring","values":["exploring"]},{"value":"charts","values":["charts"]},{"value":"P3","values":["P3"]},{"value":"M","values":["M"]}],["Renderer'ın GFM ayrıştırıcısında dipnotlar + başvuru biçimli bağlantılar (b[] dizeleri boyunca sayfa düzeyinde durum)",{"value":"shipped","values":["shipped"]},{"value":"kit","values":["kit"]},{"value":"P3","values":["P3"]},{"value":"M","values":["M"]}],["Tepkisel metin: ${expr} yerleştirme + form girdilerinde oku-bind çift yönlü bağlama (eklemeli, v3'ü değiştirmeden oturur)",{"value":"exploring","values":["exploring"]},{"value":"kit","values":["kit"]},{"value":"P3","values":["P3"]},{"value":"L","values":["L"]}],["Inter ve JetBrains Mono yazı tiplerini pakete al; bugün her sayfa açılışta Google'dan çekiyor",{"value":"shipped","values":["shipped"]},{"value":"build","values":["build"]},{"value":"P1","values":["P1"]},{"value":"M","values":["M"]}],["Derlemeyi atomik yap: yeni ağaçları eskinin yanına yazıp yer değiştir, böylece hata eski çıktıyı bozmaz",{"value":"shipped","values":["shipped"]},{"value":"build","values":["build"]},{"value":"P1","values":["P1"]},{"value":"M","values":["M"]}],["İşlenen bir .md içindeki betiğin ne yapabileceğine karar ver — görüntüleyici bugün onu çalıştırıyor",{"value":"exploring","values":["exploring"]},{"value":"kit","values":["kit"]},{"value":"P1","values":["P1"]},{"value":"M","values":["M"]}],["Özel elemanlar bağladıklarını bıraksın: ışık kutusu kaydırma/yakınlaştırma, sütun genişletme, grafik yeniden ayarı, kaydırma takibi",{"value":"queued","values":["queued"]},{"value":"kit","values":["kit"]},{"value":"P2","values":["P2"]},{"value":"M","values":["M"]}],["Kenar çubuğu bölüm katlaması klavyeyle erişilebilir olsun (başlık odak almıyor, durum taşımıyor)",{"value":"queued","values":["queued"]},{"value":"kit","values":["kit"]},{"value":"P2","values":["P2"]},{"value":"S","values":["S"]}],["Çizilecek satırı olmayan grafik yükü boş çerçeve yerine durumu söylesin",{"value":"queued","values":["queued"]},{"value":"charts","values":["charts"]},{"value":"P2","values":["P2"]},{"value":"S","values":["S"]}],["island-hand-styled mermaid bloklarını da gezsin — hex yazılmış bir classDef aynı kusur",{"value":"queued","values":["queued"]},{"value":"docs","values":["docs"]},{"value":"P2","values":["P2"]},{"value":"S","values":["S"]}],["İki kaynak gösterme ögesi seri belirteci yerine hex sabiti boyuyor",{"value":"shipped","values":["shipped"]},{"value":"kit","values":["kit"]},{"value":"P2","values":["P2"]},{"value":"S","values":["S"]}],["Proje sınırının dışındaki görsel sessizce gömülmesin, denetimde bildirilsin",{"value":"queued","values":["queued"]},{"value":"build","values":["build"]},{"value":"P2","values":["P2"]},{"value":"S","values":["S"]}],["Yazarın dizinini taşımayan bir künye: makineden çıkan sayfa için bir kapatma seçeneği",{"value":"queued","values":["queued"]},{"value":"build","values":["build"]},{"value":"P2","values":["P2"]},{"value":"S","values":["S"]}],["Adında # veya ? olan dosya, hiçbir bağlantının ulaşamayacağı bir sayfaya dönüşüyor",{"value":"queued","values":["queued"]},{"value":"build","values":["build"]},{"value":"P3","values":["P3"]},{"value":"S","values":["S"]}],["Sayfanın anatomisi v1 JSON değil v3 markdown biçimini anlatsın",{"value":"queued","values":["queued"]},{"value":"docs","values":["docs"]},{"value":"P2","values":["P2"]},{"value":"S","values":["S"]}],["Tarayıcı testleri saate değil koşula baksın (bugün 193 sn sabit bekleme)",{"value":"queued","values":["queued"]},{"value":"kit","values":["kit"]},{"value":"P3","values":["P3"]},{"value":"M","values":["M"]}]]}
```

## Son eklenenler {#recent}

- Kaynak gösterme türünün rengi artık bir belirteçten geliyor, yani temayı izliyor. `paper` türü hem kart simgesinde hem alıntılanan sözcüklerin altındaki çizgide `#4338ca` boyuyordu — `--series-3`'ün açık tema değeri — ve koyu sayfada dört kardeşi ters dönerken o açık kaldı: kendi simge zemininde 2,05:1, ötekilerde 8,7 ile 14,8 arası. Şimdi 8,35:1.
- Yarıda kalan bir derleme yalnızca yeni sayfalara mal olur: her sayfa önce `dist/.build-<pid>/` içine yazılır, en sonda yerine taşınır. Daha önce yarıda kalan bir derleme, üretilmiş 120 dosyanın 120'sini siliyordu.
- Yazı tipleri sayfayla birlikte gelir: Inter ve JetBrains Mono dört değişken woff2 olarak pakete alındı, `_oku/vendor/fonts/` altından paylaşılır. Tek dosyalık bir sayfa açılışta Google'a üç istek yapıyordu; artık hiç yapmıyor.
- Blok + satır içi ayrıştırıcı üzerinde GFM uyumluluk geçişi: ters eğik çizgi kaçışları, sözcük içi alt çizgi kuralı, görseller, üstü çizili metin, otomatik bağlantılar, bağlantı başlıkları, karakter başvuruları, sert satır sonları, `***` / `___` çizgileri, `~~~` çitleri, ATX kapanış dizileri, sıralı liste başlangıcı, çok paragraflı liste maddeleri, tablolarda kaçırılmış dikey çizgiler, sütun hizalaması, düzensiz satırların normalleştirilmesi, benzersiz başlık çapaları.
- Dipnotlar ve başvuru biçimli bağlantılar, b[] dizeleri boyunca sayfa genelinde çözülüyor; `oku check` tanımsız bir başvuruda uyarıyor.
- Standart docs/ yerleşimi için site gezintisi: manifest kitin indiği yere yazılıyor ve kendine ait sayfası olmayan bir düzey artık ağacı bozmuyor.
- `oku serve`, init dizininin dışındaki sayfalar için kite geri düşüyor ve istek yollarındaki yüzde kodlamasını çözüyor (ASCII dışı dosya adları).
- Kaynak biçimi v3 (markdown öncelikli) uçtan uca yayımlandı; v2 sayfaları için yapısal denetim yeniden ayağa kaldırıldı.
- Kaynak biçimleri, gerçekten yayımlanan ikiye indirildi: `.md` (yazarın yazdığı) ve `.json` (markdown biçimi ortaya çıkmadan önce yazılmış sayfalar). Ölçümlü karşılaştırma için taşınan üçü — html öncelikli, asciidoc, djot — derlemleri ve gidiş-dönüş testleriyle birlikte silindi. HTML, adın çağrıştırdığı anlamda hiçbir zaman adaylardan biri olmadı: o, her derlemenin ÇIKTISIDIR.
- Yol tabanlı gezinme yönlendiricisi — URL yolu ile çizilen sayfa artık ayrışamıyor; eski karma bağlantılar normalleşiyor.
- Geniş şemalar sütunlarına her zaman sığıyor: SVG en fazla yazıldığı boyutta çizilir ve sütuna göre küçülür; viewBox'ı da mermaid'in kutusu ile gerçek içerik sınır kutusunun birleşimine göre yeniden ayarlanır, böylece mermaid'in o kutunun dışına yerleştirdiği hiçbir şey kesilmez. Geniş bir şemada ayrıntıyı okumak lightbox'ın işidir. Bu, yazılan boyutun %90'ını taban alan eski davranışın yerini aldı; geniş akış şemalarının taşmasına ve kırpılmış görünmesine yol açan oydu.
- Lightbox: görüntü alanının tamamını kaplayan çerçeve; şemalar da grafikler gibi canlı öğeyi taşıyor (etkileşim tümüyle korunuyor).
- Renderer'da satır içi arındırılmış HTML izin listesi geri getirildi; sunburst birinci halka için gösterge çipleri kazandı.
- Tarayıcı gerileme takımı (gerçek serve işleyicisine karşı başsız chromium) varsayılan pytest koşusuna bağlandı.

Bu döngüde yayımlanan öne çıkanlar. İşleme başına tam geçmiş git log içinde.

```oku-kpi-grid
{"tiles":[{"num":"53","label":"Şemanın kabul ettiği grafik türü"},{"num":"7","label":"Eşlenik imleç süpürmesi olan grafik"},{"num":"10","label":"Grafikler sayfasında amaca göre gruplanmış aile"},{"num":"0","label":"Quadrant Playwright taramasında görünür etiket-köşe çakışması"}]}
```

- Aileye göre seçim yeniden yazıldı — canlı küçük çizimler taşıyan 43 tıklanabilir mini kart; tıklama doğrudan o türün tam örneğine götürüyor.
- Grafikler sayfası 10 amaç ailesine göre yeniden gruplandı (Kartezyen / Kategorik / Parça-bütün / Dağılım / Eğilim / Akış / Ağ / Çok değişkenli / Hedef / Coğrafi).
- Kod / çıktı hizalaması her yerde sıfır piksel — her belge sayfasındaki her örnek çiftinde kutular üstten hizalanıyor.
- Bilgi balonunun genişliği sabitleme durumları arasında değişmiyor; sabitlenmiş balon bir × kapatma düğmesi alıyor; görüntü alanına sabitlenmiş konumlandırma onu tam ekran lightbox'ın üstüne çıkarıyor.
- Kartezyen grafikler eşlenik dikey kesik çizgi imleci ve imlecin en yakın x konumundaki her seri değerini listeleyen konuma özel bir bilgi balonu kazandı.
- Ridgeline + sparkline imleç işleyicileri zengin bilgi balonunu imleç konumuna göre güncelliyor (önceden yalnızca girişte sabitti).
- Quadrant köşe etiketi ve Kartezyen gösterge kümesi, veri etiketleri için uçuşa yasak bölge sayılıyor — `_deconflictLabels` bu bölgelere düşecek etiketleri kaydırıyor ya da gizliyor.
- Bubble göstergesinin arka planı tümüyle donuk — devasa bir baloncuk artık çip etiketlerinin arasından sızamıyor.
- Parallel-coordinates çizgisi dururken 3.6px, imleç altında 5px; imleçle birlikte ötekiler soluyor, böylece vurgulanan kayıt öne çıkıyor.
- Donut / pie'da sabitlenen dilimler büyüyor ve vurgu çizgisi alıyor; grafik biçimlerinde genel odak çerçevesi kaldırıldı.
- Gauge bölgeleri isteğe bağlı etiketler ve imleçle sürülen konum-değeri inceleyicisi kazandı.
- Mermaid kırpılma önlemi: `.okd-render` artık overflow:hidden, en-boy uyumu uzun dikey şemaları 70vh ile sınırlıyor, tüm SVG metinlerinde yazı boyutu 13px'e sabitlendi.
- Compare-grid kartları isteğe bağlı `href` kazandı — kartın tamamı tıklanabilir. Aileye göre seçim bunu kullanıyor.
- Tablolarda çok satırlı hücre içeriği için sütun başına `wrap: true`.
- Yüzeydeki bütün html-doc göndermeleri kaldırıldı (eski ad yalnızca GitHub URL'sinde kaldı).

## Kilitlenmiş kararlar {#decisions}

Her biri bir zamanlar açık bir soruydu; gelecekteki katkıcılar yeniden tartışmasın diye burada toplandı.

- Proje adı = oku (Türkçe buyrum kipi). Her katman `oku` okur: paket (src/oku/), kit CSS önekleri (okt- / okc- / okd-), JS küresel değişkenleri (__oku*), olay adları (oku:*), veri öznitelikleri (data-oku-*) ve custom element etiket adları.
- GitHub uzak adresi github.com/mmdemirbas/html-doc olarak kalıyor — şema $id'si, git-clone örneği ve jsdelivr CDN adresi hep oraya bakıyor. Yerel depo dizininin adı uzak adresi izliyor.
- Örnek çifti içindeki kod / çıktı sütunları kutunun üst kenarında hizalanmak ZORUNDA. Kod olmayan çıktılar için 24px'lik boşluk yok — kod ve çıktı sütunlarının görünen üst kenarları, çıktının türü ne olursa olsun aynı hizada durur.
- Bilgi balonunun genişliği sabitleme durumları arasında değişmez. Sabitli ile sabitsiz arasındaki fark alt yazı metni ve kapatma düğmesinin görünürlüğüdür, ASLA sınır kutusu değil.
- ext-ref sunucu adı bir gezinme bağlantısı DEĞİLDİR. Tıklamak bilgi balonunu sabitler; hedef adres, kaynak kartının içinde tıklanabilir bir alan adı bağlantısı olarak durur. Öğe başına tek işlev.
- Pagefind bir sistem ikilisi değil, bir Python bağımlılığıdır — `oku[search]` eki `pagefind[bin]>=1.5` çeker.
- Yerleşim = A seçeneği (ortalanmış belge, üç kademeli içerik genişliği döngüsü: narrow / comfortable / max).
- Üçüncü kuşak görseller (sankey / network / scatter-matrix / parallel-coordinates / chord / geo) kitin kendi grafik türleri olarak yayımlanıyor — üçüncü taraf grafik kütüphanesi yok.
- Grafikler / tablolar / şemalar, Başvuru'nun alt sayfalarıdır (meta.parent: 'reference').
- Kaynak biçimi = v3, markdown öncelikli. Bir sayfa `.md` dosyasıdır: YAML ön verisi + katı GFM gövdesi (girintili kod bloğu yok, setext başlık yok, gevşek devam yok — denetlenir, yine de geçerli GFM'dir); kit bileşenleri, gövdesi tek satırlık derli toplu bir JSON olan ```oku-<tür> çitleridir; şemalar, altına italik bir açıklama satırı gelen ```mermaid çitleridir; blok düzeyindeki ham HTML adaları (script dâhil) kite dokunulmadan geçer ve `oku check` tarafından denetlenir. Karar, belirteç sayımı (markdown, v2 JSON'dan ≈ %20 daha yalın, HTML'den çok daha yalın), LLM üretim doğruluğu ve ekosistemin yönü ölçüldükten sonra verildi; HTML öncelikli biçim değerlendirildi ve depoda duran, sürekli düzenlenen kaynaklar için elendi. JSON sayfaları (v1/v2) uyum katmanlarıyla çizilmeye devam ediyor; `oku migrate` onları dönüştürüyor.
- Derleme çıktıları = iki ağaç (standalone, site). dist/markdown ikizi yok — `.md` kaynakları yapay zekâ/LLM için kanonik yüzeydir; llms.txt site belge kökünde durur.

## İlkeler {#principles}

Okuyucuya, yazara ve bakımcıya bakan, her değişikliğin uyduğu kurallar.

- Tek bir SOL yan panel — içindekiler + site ağacı üst üste. Sağda içindekiler yok, kenar ortasında sekme yok.
- Görsel öncelikli yazım. Artı/eksiler → karşılaştırma kartları, ölçümler → kpi ızgarası, ödünleşimler → çipli tablo. Paragraf + madde imi varsayılan değil, geri düşülen seçenektir.
- Her düzeltme bir Playwright denetimiyle birlikte gelir. Tarayıcı düzeyindeki düzeltmeler, işleme gövdesine yazılan sayısal doğrulamalarla yayımlanır.
- Sayaç ve rozetlerde yalnızca sayı — kitin içine gömülü İngilizce sözcük yok.
- Ayrı gösteri sayfası yok. Bir bileşene ait her örnek kendi başlığının yanında durur.
- Belgelerde süreç / tur / tarihçe göndermesi yok — nasıl bu hâle geldiği değil, şu anki davranış anlatılır.
- Yerleşim değişmezleri göz kararı değil sayısaldır — kuralı bir boundingBox / hesaplanmış stil doğrulaması olarak yazın ya da henüz bir kural olmadığını kabul edin.
