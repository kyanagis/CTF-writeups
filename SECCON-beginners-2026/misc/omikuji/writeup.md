## 問題

```
名前を入れておみくじを引きましょう。結果を全部当てられますか？

nc [URL]
```

名前を入れておみくじを引く問題ですね．5回ぶんの数字を全部当てたらflagらしい．運ゲーに見えるよ！？！？！？
```
 > nc [URL]
=== Omikuji ===
Tell me your name, and I will draw your fortune.
name > test
Welcome, test!
Guess the next 5 omikuji numbers to get the flag.
guess 1 > 5
wrong
 
```

## 調査

とりあえずディレクトリを見る．

```
> tree

.
├── Dockerfile
├── compose.yaml
└── main.py
```

わかること:
- ソースは`main.py`一個だけ．`nc`で繋ぐCUI問なので，ここを読めば全部わかる．

## main.py

おみくじのコアは35〜45行目．

```python
# main.py : おみくじループ (35〜45行目)
for i in range(ROUNDS):
    x = random.randint(1, 1000000)
    try:
        guess = int(read_limited(f"guess {i + 1} > ", MAX_GUESS_LENGTH))
    except ValueError:
        print("wrong")
        exit()

    if guess != x:
        print("wrong")
        exit()
```

`x = random.randint(1, 1000000)`を`ROUNDS`回（6行目で5回）引いて，毎回こちらの`guess`と一致しないと`wrong`で即終了（43〜45行目）．全部当たれば最後にflag（47行目）．1/1000000を5連続で当てるのは無理ゲーなので，乱数そのものを予測する方向で見る．

29〜30行目．

```python
# main.py : 乱数のseed (29〜30行目)
name = read_limited("name > ", MAX_NAME_LENGTH)
random.seed(name)
```

`random.seed(name)`．seedが自分の入れた`name`そのものになっている．Pythonの`random`はMersenne Twisterで暗号用途じゃないので，種が分かれば出る数列は完全に再現できる．しかも`name`はこちらが決める値なので，同じ`name`で同じseedを張れば，サーバが出す5つの`randint`を手元で先に計算できる．

つまり「適当な`name`を送る -> 手元で`random.seed(name)`して同じ`randint(1, 1000000)`を5回回す -> その値を順に送る」で全部当たる．

## 分かったこと

- おみくじは`random.randint(1, 1000000)`を5連続で当てる問題（36行目）．素の確率では無理．
- けど種が`random.seed(name)`（30行目）で，`name`は自分が入力する値．
- Pythonの`random`は種が同じなら数列も同じなので，同じ`name`で手元再現すれば5つ全部予測できる．
- -> `name`を固定して手元で同じ数列を作り，順に送るだけ．スクリプト化する．

## 実行

上記を踏まえてスクリプトを書きました．
[solve.py](./solve.py)

やっていること:
- `NAME = "a"`（10行目）をサーバに送る（33行目）．
- 手元で別の`random.Random()`に同じ`"a"`をseedして`randint(1, 1000000)`を5回先読みし（27〜29行目），それを`guess`として順に送る（35〜37行目）．

```
> python3 solve.py
ctf4b{0m1kuj1_15_d373rm1n15t1c}
```

フラグが見えました！

## 原因とか

- 予測不能であるべき乱数の種を，攻撃者が自由に決められる入力（`name`）にそのまま使ってしまっている（30行目）．
- Pythonの`random`（Mersenne Twister）は再現可能な擬似乱数なので，種が既知なら出力列は丸ごと再現できる．seedが攻撃者制御の時点で「当てる」要素が消える．
- 当て物に使うなら`random`ではなく`secrets`／`os.urandom`のような暗号論的乱数を使い，かつ種を外部入力に依存させないべきだった．

## 参照
- [Python — random（暗号用途に使うなの注意つき）](https://docs.python.org/3/library/random.html) — `random.seed`で種を固定すると数列が再現される話．
- [Python — secrets](https://docs.python.org/3/library/secrets.html) — 当て物・トークン等に使うべき暗号論的乱数．
- [CWE-330: Use of Insufficiently Random Values](https://cwe.mitre.org/data/definitions/330.html) — 予測可能な乱数を使ってしまう脆弱性の分類．今回そのもの．
