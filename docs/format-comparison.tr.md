---
title: Kaynak biçimi neden markdown
accent: amber
eyebrow: Başvuru
date: 2026-06-13
order: 95
summary: Beş kaynak biçimi belirteç sayısı, dönüştürücü yükü ve ekosisteme
  uyum üzerinden ölçüldü. Markdown kazandı, diğer üçü silindi. Ölçümün
  söylediği şey, karar bir daha hafızadan tartışılmasın diye burada duruyor.
---

> [!TLDR]
> **Çıktı HTML'dir.** Kaynağı ne olursa olsun her sayfa HTML olarak
> teslim edilir — soru hiçbir zaman bu değildi. Soru, yazarın ne
> *yazacağıydı* ve beş yanıt aynı iki sayfa üzerinde ölçüldü. Markdown,
> AsciiDoc ve djot belirteç sayısında birbirinin %1,2 yakınında kaldı;
> JSON %6 fazla tuttu; kaynağı HTML olarak yazmak %52 fazla tuttu.
> Markdown, yakın olmayan eksenlerde kazandı: yapay zekânın doğal olarak
> yazdığı biçim odur ve GitHub'da, Obsidian'da ve her düzenleyicide kit
> olmadan işlenir.

## Ne teslim edildi {#shipped}

İki kaynak biçimi; ikincisi yalnızca birincisinden eski sayfalar için var.

| Biçim | Nedir | Durum |
|---|---|---|
| `.md` | Ön bilgi bloğu + katı GFM gövdesi. Yazarın yazdığı şey. | Biçimin kendisi |
| `.json` | `.md` var olmadan önce yazılmış v1 / v2 sayfa sözlükleri | Süresiz işlenir; `oku migrate` istendiğinde çevirir |
| `.src.html` | *Kaynağı* HTML olarak yazmak | Silindi |
| `.adoc` | AsciiDoc alt kümesi | Silindi |
| `.dj` | djot alt kümesi | Silindi |

Bu üçünün silinmesi ~820 satır dönüştürücüyü, üç derlem dizinini ve
bunların gidiş dönüş sınamalarını ortadan kaldırdı. Başka hiçbir şey
değişmedi: her biçim zaten aynı v2 sözlüğüne dönüşüyordu ve denetleyici,
derleme, sunucu ve işleyici yalnızca v2 görüyordu.

**Sayfanın içinde ham HTML istemek başka bir istektir** ve bu istek
zaten karşılanıyor — sıfırıncı sütundaki blok düzeyi bir HTML etiketi
hiçbir kısıtlama olmadan olduğu gibi geçer. Kaçış kapısı budur ve
yazarların bütün bir sayfayı HTML yazmak yerine uzandığı şey de budur.

## Ölçüm ne söyledi {#measured}

Derlem elle yazılmak yerine üretildi: tek bir örnek v2 sayfa sözlüğü her
biçime yazıldı ve geri ayrıştırıldı, gidiş dönüş eşitliği sınamalarla
güvence altına alındı; böylece tek değişken biçimin kendisi oldu.
Belirteçler `cl100k_base` ile sayıldı.

```oku-chart
{"type":"bar","title":"Kaynak belirteçleri — iki sayfalık derlem (cl100k)","rows":[{"label":"markdown","value":679},{"label":"asciidoc","value":682},{"label":"djot","value":688},{"label":"json (v2)","value":720},{"label":"html-first","value":1034}]}
```

| Biçim | Toplam belirteç | markdown'a göre | Bayt |
|---|---|---|---|
| markdown (v3) | 679 | %100,0 | 2396 |
| asciidoc | 682 | %100,4 | 2429 |
| djot | 688 | %101,3 | 2410 |
| json (v2) | 720 | %106,0 | 2475 |
| html-first | 1034 | %152,3 | 3539 |

Kararı belirteçler vermedi — üç biçim %1,2'lik bir aralıkta berabere
kaldı. Kararı veren eksenler, aralarında geniş fark bulunanlardı.

| Eksen | markdown | asciidoc / djot | html-first |
|---|---|---|---|
| Yapay zekânın düzenleme isabeti | doğal yazım biçimi | eğitim verisinde az yer alıyor | etiket disiplini, şişkin farklar |
| Kit olmadan işlenme | GitHub, Obsidian, düzenleyiciler; mermaid yerleşik | GitHub'da kısmen ya da hiç | yalnızca tarayıcı |
| Python ayrıştırıcısı | var | yok — yalnızca alt küme | stdlib |

> [!NOTE] Alt kümeler ne demekti
> AsciiDoc ve djot dönüştürücüleri yalnızca derlemdeki yapıları
> kapsıyordu — başlıklar, paragraflar, listeler, tablolar, çitler,
> bilgi kutuları. Tam belirtim desteği, Python'da bulunmayan
> ayrıştırıcılar gerektiriyordu; araç boşluğunun kendisi de bir
> veriydi.

## İşlenmiş hâllerini görün {#rendered}

Ayakta kalan iki biçim, aynı içerik, aynı hat:

- Kılavuz: [markdown](../examples/format-comparison/markdown/sample-guide.html) · [json](../examples/format-comparison/json/sample-guide.html)
- Gösterge tablosu: [markdown](../examples/format-comparison/markdown/sample-viz.html) · [json](../examples/format-comparison/json/sample-viz.html)
