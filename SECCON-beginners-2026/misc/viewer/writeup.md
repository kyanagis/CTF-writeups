## 問題

```
表示できるファイルを選んでください。

nc URL
```

ファイルビューアですね．許可されたファイルだけ表示できるけど，`flag.txt`を読めればflag，という形になってるはず．
```
> nc viewer.beginners.seccon.games 33458

__     ___                        
\ \   / (_) _____      _____ _ __ 
 \ \ / /| |/ _ \ \ /\ / / _ \ '__|
  \ V / | |  __/\ V  V /  __/ |   
   \_/  |_|\___| \_/\_/ \___|_|   

available files:
- readme.txt
- hello.txt
filename > readme.txt
Welcome to viewer!
You can read listed files.
^C
```
## 調査

とりあえずディレクトリを見る．

```
> tree

.
├── Dockerfile
├── compose.yaml
├── main.py
├── readme.txt
├── hello.txt
└── flag.txt
```

わかること:
- ロジックは`main.py`一個．`Dockerfile`（8行目）で`readme.txt`/`hello.txt`/`flag.txt`が`/app/files/`に置かれる．
- `flag.txt`はサーバ側に確かに存在する．あとは「`flag.txt`を表示させる入力」を作れるか，という問題．

## main.py

ファイル名を受け取ってから表示するまでを順に追う．まず`main`（49〜71行目）．

```python
# main.py : main 内のフィルタ (55〜64行目)
    filename = read_limited("filename > ", MAX_FILENAME_LENGTH)

    if "flag" in filename:
        print("blocked")
        return

    path, error = resolve_path(filename)
    if error is not None:
        print(error)
        return
```

入力`filename`に対して，まず57行目で`if "flag" in filename`で弾く．つまり入力文字列に`flag`という部分文字列が含まれていたら`blocked`．素直に`flag.txt`と打つと当然ここで止まる．

その先の`resolve_path`（34〜46行目）．

```python
# main.py : resolve_path (34〜46行目)
def resolve_path(filename):
    normalized = unicodedata.normalize("NFKC", filename)

    if normalized != os.path.basename(normalized):
        return None, "invalid path"
    if normalized not in ALLOWED_FILES:
        return None, "file not found"

    path = os.path.normpath(os.path.join(FILES_DIR, normalized))
    if os.path.commonpath([FILES_DIR, path]) != FILES_DIR:
        return None, "invalid path"

    return path, None
```

ここで順番が問題になる．
- 35行目で`unicodedata.normalize("NFKC", filename)`して`normalized`を作り，それを`ALLOWED_FILES`（7行目 = `{readme.txt, hello.txt, flag.txt}`）と突き合わせる（39行目）．
- つまり許可判定は「NFKC正規化したあと」の文字列で行われる．
- 一方，さっきの`"flag" in filename`の禁止判定（57行目）は「正規化する前」の生の入力に対して行われている．

「禁止チェックは正規化前」「許可チェックは正規化後」でズレている．ここが穴．NFKCで正規化すると`flag`という4文字に化けるけど，正規化前は`flag`を含まない文字列を作れればいい．

Unicodeには合字（リガチャ）の`ﬂ`（U+FB02 LATIN SMALL LIGATURE FL）があって，これはNFKCで`fl`の2文字に分解されるらしい．だから入力を`ﬂag.txt`にすると:
- 57行目の生入力には`flag`という並びは無い（先頭が`ﬂ`という1文字）ので`blocked`を通過．
- 35行目のNFKC正規化で`ﬂ` -> `fl`になり，`normalized`は`flag.txt`．
- 39行目で`ALLOWED_FILES`に`flag.txt`があるので一致 -> 表示．

確認してみる．

```python
>>> import unicodedata
>>> unicodedata.normalize("NFKC", "ﬂag.txt")
'flag.txt'
>>> "flag" in "ﬂag.txt"
False
```

狙いどおり，正規化前は`flag`を含まず，正規化後は`flag.txt`になる．

## 分かったこと

- 禁止判定`"flag" in filename`は正規化前の生入力に対して（57行目），許可判定`normalized in ALLOWED_FILES`はNFKC正規化後に対して（35・39行目）行われていて，見ている文字列がズレている．
- リガチャ`ﬂ`（U+FB02）はNFKCで`fl`に展開されるので，`ﬂag.txt`は「禁止チェックは素通り・許可チェックは`flag.txt`扱い」になる．
- -> 入力に`ﬂag.txt`を送るだけでflagが読める．

## 実行

`nc`で繋いで，`filename > `のプロンプトにペイロード`ﬂag.txt`（先頭がリガチャ U+FB02）を1行打つだけ．

```
> echo 'ﬂag.txt' | nc viewer.beginners.seccon.games 33458
...
filename > ctf4b{un1C0dE_N0rMal12a710n_15_7r1CKy}
```

フラグが見えました！

## 原因とか

- 同じ`filename`に対して，禁止チェック（57行目）は正規化前・許可チェック（35・39行目）は正規化後と，別々の表現を見ている．「チェックした文字列」と「実際に使う文字列」が一致していないTOCTOU的なズレ．
- 入力を最初に1回だけ正規化して，以降の禁止チェック・許可チェック・オープンを全部その正規化済み文字列で揃えるべきだった．そうすれば`ﬂag.txt`も先に`flag.txt`になり禁止チェックで弾ける．
- そもそもブロックリスト（`"flag"`を含むかどうか）ではなく，許可リスト（`readme.txt`/`hello.txt`だけ通す）で正面から絞るべき問題．

## 参照
- [Unicode正規化（NFKC など） — Unicode Standard Annex #15](https://unicode.org/reports/tr15/) — 互換合字`ﬂ`が`fl`に分解される根拠．
- [Python — unicodedata.normalize](https://docs.python.org/3/library/unicodedata.html#unicodedata.normalize) — `NFKC`の挙動．
- [OWASP — Canonicalization, Locale and Unicode](https://owasp.org/www-community/vulnerabilities/Canonicalization,_Locale_and_Unicode) — 正規化前後でチェックがズレると検証を回避できるという定番の話．
- [CWE-178: Improper Handling of Case Sensitivity / CWE-180: Incorrect Behavior Order: Validate Before Canonicalize](https://cwe.mitre.org/data/definitions/180.html) — 「正規化より前に検証してしまう」順序バグの分類．今回そのもの．
