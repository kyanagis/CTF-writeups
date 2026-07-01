## 問題

```
My teacher told me to do this assignment. I’d like to use AI to make it easier, but I have a feeling there’s something hidden here...
```

配布されるのは`Homework.pdf`一個だけ．「課題のPDFをAIに投げたいけど，なにか隠れてる気がする」というフレーバー．nc接続は無くて，配布ファイルそのものを調べる問題．

## 調査

PDFを普通に開くと，C言語のメモリ管理とポインタ演算についてのレポート課題が書いてあるだけ．メタ情報を見ても，

```
> strings files/Homework.pdf | grep -iE 'title|subject|producer'

/Producer (ReportLab PDF Library - \(opensource\))
/Subject (Introduction to Systems Programming - Assignment)
/Title (Report: Memory Management and Pointer Arithmetic in C)
```

ReportLabで作った普通の課題PDFっぽい．見た目には何も無いので，「PDFとして見えてる部分」じゃなくて「ファイルの中身そのもの」を疑う．

まず`file`コマンドで素性を確認する．

```
> file files/Homework.pdf
files/Homework.pdf: PDF document, version 1.4, 1 page(s)
```

ただのPDFとしか言わない．でも`file`が見ているのは先頭のマジックバイト（`%PDF`）だけで，末尾に何が足されていようと気づかない．なので末尾は自分で確認する．

PDFは`%%EOF`で終わる形式なので，それが本当にファイルの最後にあるのか，後ろにバイトが続いていないかを見る．

```
> xxd files/Homework.pdf | tail -13
00000b20: 6664 3830 3062 3336 3934 3535 6366 3e5d  fd800b369455cf>]
00000b30: 203e 3e0a 7374 6172 7478 7265 660a 3235   >>.startxref.25
00000b40: 3538 0a25 2545 4f46 0a0a 504b 0304 1400  58.%%EOF..PK....
00000b50: 0000 0800 e980 ca5c 91cb 8435 2500 0000  .......\...5%...
00000b60: 2300 0000 0800 0000 464c 4147 2e74 7874  #.......FLAG.txt
00000b70: 4b2e 4933 49aa f6cc 8db7 3434 4989 af34  K.I3I.....44I..4
00000b80: 288d 4f33 28cd 4b89 2fc9 c834 8d4f 3334  (.O3(.K./..4.O34
00000b90: b1ac e502 0050 4b01 0214 0014 0000 0008  .....PK.........
00000ba0: 00e9 80ca 5c91 cb84 3525 0000 0023 0000  ....\...5%...#..
00000bb0: 0008 0000 0000 0000 0000 0000 0080 0100  ................
00000bc0: 0000 0046 4c41 472e 7478 7450 4b05 0600  ...FLAG.txtPK...
00000bd0: 0000 0001 0001 0036 0000 004b 0000 0000  .......6...K....
00000be0: 00                                       .
```

`%%EOF`（PDFの終端）の直後（`0a0a`＝改行2つ）に`504b 0304`＝`PK\x03\x04`がそのまま並んでいる．ZIPのローカルファイルヘッダの先頭で，続けて`464c 4147 2e74 7874`＝`FLAG.txt`というファイル名まで見えている．さらにファイル末尾には`504b 0506`＝`PK\x05\x06`（ZIPのEnd of Central Directory）もあって，PDFの終わりにZIPアーカイブが丸ごと追記されているのがそのまま読める．

`binwalk`でも一発でわかる．

```
> binwalk files/Homework.pdf

DECIMAL     HEXADECIMAL   DESCRIPTION
-------------------------------------------------------------
0           0x0           PDF document, version 1.4
2890        0xB4A         ZIP archive, file count: 1, total size: 151 bytes
```

なぜこれが成立するかというと:
- PDFは先頭から読む形式で，ファイルの頭が`%PDF`なら後ろに何がくっついていても有効なPDFとして開ける．
- ZIPは逆に末尾のセントラルディレクトリから読む形式なので，アーカイブの前にゴミ（＝PDF本体）が付いていても有効なZIPとして開ける．
- だから「PDF＋ZIP」をくっつけると，1つのファイルが同時に正しいPDFかつ正しいZIPになる（ポリグロット）．

追記されたZIPの中身を見る．

```
> unzip -l files/Homework.pdf

  Length      Date    Time    Name
---------  ---------- -----   ----
       35  06-10-2026 16:07   FLAG.txt
```

`FLAG.txt`が入っている．これを取り出せばflag．

## 分かったこと

- `Homework.pdf`は普通の課題PDFに見えるが，`%%EOF`（2883バイト目）の直後にZIPアーカイブが追記されたポリグロット．
- ZIPは末尾から読まれるので，PDFファイルをそのままZIPとして開ける．中に`FLAG.txt`が1個入っている．
- -> PDFをZIPとして展開して`FLAG.txt`を読むだけ．

## 実行

PDFをそのままZIPとして展開するだけ．

```
> unzip files/Homework.pdf
Archive:  files/Homework.pdf
warning [files/Homework.pdf]:  2890 extra bytes at beginning or within zipfile
  (attempting to process anyway)
  inflating: FLAG.txt

> cat FLAG.txt
ctf4b{Im_914d_y0u_f0und_thi5_f149}
```

フラグが見えました！

## 原因とか

- PDFのレンダリング結果（見えるテキスト）だけ見ても気づけないが，ファイル末尾に別フォーマット（ZIP）が丸ごと追記されていた．
- PDFは先頭から・ZIPは末尾から読むという「読み始める端」の違いを利用したポリグロットで，1ファイルが両方の性質をもつ．
- AIに投げて中身を要約させるだけだと本文しか見ないので隠しデータに気づかない，というひっかけ的な感じなのかな？バイナリは`file`/`binwalk`/末尾バイトまで自分で確認します

## 参照
- [PDF 32000-1:2008 — File Structure（%PDF ヘッダと %%EOF トレーラ）](https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf) — PDFが先頭から読まれ，末尾に余計なバイトが付いても開ける根拠．
- [ZIP File Format Specification（End of Central Directory）](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT) — ZIPが末尾のセントラルディレクトリから読まれる仕様．ポリグロットが成立する理由．
- [binwalk](https://github.com/ReFirmLabs/binwalk) — ファイルに埋め込まれた別フォーマットを検出するツール．
- [CTF Field Guide / Forensics — File polyglots](https://trailofbits.github.io/ctf/forensics/) — 追記・ポリグロットを使った隠蔽の定番パターン．
