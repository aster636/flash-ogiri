# フラッシュ大喜利 / FLASH OGIRI

1対多の即答型大喜利ゲーム。PCやスマホで同じURLを開き、ルームコードで参加します。

## 仕様

- 2〜16人のWebSocketマルチプレイ。回答者は常に1人、残りが出題者。
- **回答者1人につき60秒間**。60秒になると自動で次の人に交代（交代演出3秒）。
- 回答者には新しいお題が次々に表示され、**それぞれ5秒以内**に口頭で回答。
- **5秒以内の回答 +10点、時間切れ／パス -5点**。ホストも回答を判定可能。
- 自分が投稿したお題が出題されると **出題者に+5点**（AI候補からの選択も同じ）。
- 観客が投稿したお題を優先。お題が足りなければ内蔵の候補から補充。
- 全員が回答者を1回ずつ担当すると1周終了。合計点数でランキング発表。
- プレイヤーが60秒終了直前に5秒の回答時間を確保できない場合は、その時点で新しいお題を出さず交代を待機。

### 遊び方

1. 1人がルームを作成し、表示された招待URLを共有する。
2. 他の参加者はリンク先から名前を入力してルームに参加する。
3. 回答者以外がお題を投稿する。ジャンルを選んで「3つ提案」を押せばAI案や内蔵案からも投稿できる。
4. ホストが開始ボタンを押す。最初の回答者に60秒の持ち時間が与えられる。
5. 回答者は5秒以内に**口頭**で答え、成功したら「回答した！」を押す。ホストも成功／失敗を判定できる。
6. 60秒経過後、**操作不要で**次の回答者へ交代する。全員が終わると順位を表示。

**注意:** 音声認識や回答の自動判定は未実装です。5秒以内に回答できたかは、回答者またはホストがボタンで判定します。

## GitHubから無料公開（GitHub + Render）

GitHub PagesはHTMLやJavaScriptなどの静的ファイルだけを配信する仕組みで、
このゲームに必要なPythonサーバーやWebSocketルーム管理をGitHub Pagesだけで動かすことはできません。
**GitHubをコードの置き場、Renderをゲームのサーバー兼公開URL**として利用します。

### ステップ1：GitHubにアップロード

1. [GitHub](https://github.com/new) で新規リポジトリを作成する。例: `flash-ogiri`。
2. このパッケージをZIP展開し、**`server.py` や `render.yaml` がリポジトリの最上位に来るように**アップロードする。
   - GitHub画面の **Add file → Upload files** を選び、展開したファイル・フォルダの中身を追加する。
   - ZIPファイルそのものを置くのではありません。
3. **Commit changes** で確定。ファイル一覧に `server.py` / `requirements.txt` / `render.yaml` / `public/` があるか確認。

### ステップ2：RenderでURLを公開

1. [Render](https://dashboard.render.com/) にGitHubアカウントでログインする。
2. **New → Web Service** → GitHubの `flash-ogiri` リポジトリを接続する。
3. 設定を以下にする：
   - Runtime: **Python**
   - Build Command: **`pip install -r requirements.txt`**
   - Start Command: **`python server.py`**
   - Instance Type: **Free**
4. **Deploy Web Service** を選んでデプロイする。
5. `https://＜サービス名＞.onrender.com` のような**実際にRenderが表示するURL**が完成。開いてルーム作成 → 招待リンクを送る。

`render.yaml` も付属しているので、Renderの **New → Blueprint** から同じリポジトリを指定する方法でも公開できます。

> Render無料枠は一定時間アクセスがないと休止します。またサーバーを再起動すると、保存中のルームと点数は消えます。
> 複数台での同時プレイは単一インスタンスで運用してください。

### ステップ3：ゲームを更新

GitHubリポジトリのファイルを書き換えてコミットすると、RenderのGit連携設定に応じて公開版へ更新されます。

### 本物のAI生成を有効化したい場合（任意）

RenderのWeb Serviceに環境変数 `OPENAI_API_KEY` を追加すると、ジャンル別のお題候補をAPIで生成できます。
`OPENAI_MODEL` の指定は任意です。API使用料が別途発生する場合があります。
**APIキーはGitHubのコードやHTMLに絶対に書かないでください。**
設定がない場合も内蔵のお題候補で遊べます。

## ローカルで遊ぶ

Python 3.10以上をインストールし、Windowsでは `start_windows.bat` をダブルクリックします。
または、以下を実行します。

```bash
python -m pip install -r requirements.txt
python server.py
```

ブラウザで `http://localhost:8080` にアクセス。同じWi-FiのスマホはPCのIPv4アドレスでアクセス可能です。

## ファイル構成

- `server.py`: Python aiohttpとWebSocketによるルーム・サーバー・採点・60秒自動交代
- `public/`: Web画面のHTML・CSS・JavaScript
- `render.yaml`: Render自動デプロイ設定
- `tests/server_test.py`: 出題・回答・交代・ランキングの統合テスト
- `.github/workflows/test.yml`: GitHub Actionsでの自動テスト

## 制限と注意

- ゲーム状態はメモリに保存され、サーバー再起動で消失します。
- ゲーム開始後に新規参加することはできませんが、一時切断した参加者は同じブラウザから復帰できます。
- 出題が足りない場合は内蔵候補を使用します。無制限の自動AI API呼び出しはしません。
- 想定用途は友人同士の試作プレイです。多数の公開利用を想定した認証・荒らし対策や持続的なデータ保存は未実装です。
