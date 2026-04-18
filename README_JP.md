# micromcprotocol

> **⚠ 試作版 / 開発中**
> 本ライブラリは現在開発中です。**実機での動作確認は今後実施予定です。**
> API は予告なく変更される可能性があります。本番環境での使用は自己責任でお願いします。

ESP32 および Raspberry Pi Pico W 向けの軽量 MC プロトコル（3Eフレーム）クライアントです。MicroPython で動作します。

[pymcprotocol](https://github.com/senrust/pymcprotocol) にインスパイアされて制作しました。

## 特徴

- 3Eフレーム TCP のみ対応（軽量）
- Binary / ASCII モード切り替え対応
- ワードデバイス・ビットデバイスのバッチ読み書き
- 1ファイル構成・外部依存なし（`socket` + `struct` のみ）
- MicroPython 対応（`usocket` 自動フォールバック）

## 対応デバイス

| デバイス | コード | 種別 |
|----------|--------|------|
| D | 0xA8 | ワード |
| W | 0xB4 | ワード |
| R | 0xAF | ワード |
| ZR | 0xB0 | ワード |
| X | 0x9C | ビット |
| Y | 0x9D | ビット |
| M | 0x90 | ビット |
| L | 0x92 | ビット |
| B | 0xA0 | ビット |
| F | 0x93 | ビット |
| SB | 0xA1 | ビット |
| SW | 0xB5 | ワード |
| TN | 0xC2 | ワード |
| CN | 0xC5 | ワード |
| Z | 0xCC | ワード |

## 動作要件

- MicroPython（ESP32 / Pico W）または CPython 3.x
- MC プロトコル 3Eフレーム（TCP）が有効な三菱電機 PLC

## インストール

`mcprotocol.py` をデバイスにコピーするだけです。

```bash
# mpremote を使う場合
mpremote cp mcprotocol.py :mcprotocol.py
```

## 使い方

### 基本（Binary モード）

```python
from mcprotocol import MCProtocol3E

with MCProtocol3E('192.168.1.10', port=1025) as plc:
    # D100〜D109 を読む（10ワード）
    values = plc.read_words('D', 100, 10)
    print(values)  # [0, 0, 123, ...]

    # D200〜D202 に書く
    plc.write_words('D', 200, [1, 2, 3])

    # M0〜M7 を読む（8ビット）
    bits = plc.read_bits('M', 0, 8)
    print(bits)  # [1, 0, 1, 0, ...]

    # Y0〜Y2 に書く
    plc.write_bits('Y', 0, [1, 0, 1])
```

### ASCII モード

```python
plc = MCProtocol3E('192.168.1.10', port=1025, mode='ascii')
plc.connect()
values = plc.read_words('D', 0, 5)
plc.close()
```

### ESP32 + WiFi

```python
import network
from mcprotocol import MCProtocol3E

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect('SSID', 'PASSWORD')
while not wlan.isconnected():
    pass

with MCProtocol3E('192.168.1.10') as plc:
    print(plc.read_words('D', 0, 1))
```

### Pico W + WiFi

```python
import network
import time
from mcprotocol import MCProtocol3E

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect('SSID', 'PASSWORD')
while not wlan.isconnected():
    time.sleep(0.5)

with MCProtocol3E('192.168.1.10') as plc:
    print(plc.read_words('D', 0, 1))
```

## API リファレンス

### `MCProtocol3E(host, port=1025, mode='binary', timeout=5.0, timer=0x0010)`

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `host` | — | PLC の IP アドレス |
| `port` | `1025` | TCP ポート番号 |
| `mode` | `'binary'` | `'binary'` または `'ascii'` |
| `timeout` | `5.0` | ソケットタイムアウト（秒） |
| `timer` | `0x0010` | モニタリングタイマー（250 ms 単位） |

### メソッド

| メソッド | 説明 |
|---------|------|
| `connect()` | TCP 接続を開く |
| `close()` | TCP 接続を閉じる |
| `read_words(device, start, count)` | `start` 番地から `count` ワード読み取る |
| `write_words(device, start, values)` | `start` 番地からワードリストを書き込む |
| `read_bits(device, start, count)` | `start` 番地から `count` ビット読み取る（0/1 のリストを返す） |
| `write_bits(device, start, values)` | `start` 番地からビットリスト（0/1）を書き込む |

`with` 文を使うとコンテキストマネージャが `connect()` / `close()` を自動で呼び出します。

通信エラー時は `MCProtocolError`（`end_code` 属性付き）、ネットワークエラー時は `MCProtocolConnectionError`（`OSError` のサブクラス）を送出します。

## メモリ使用量（MicroPython）

本ライブラリは各操作に必要な分だけメモリを確保します。固定の大バッファは持ちません。
1 回の呼び出しあたりのヒープ使用量は通常 1 KB 未満であり、起動後に 150〜250 KB 程度のヒープが
使える ESP32 系デバイス（M5Stamp など）でも問題なく動作することを想定しています。

**メモリが制約されるデバイスでの推奨事項：**

| 指針 | 詳細 |
|------|------|
| Binary モードを使う | ASCII モードは文字列の中間オブジェクトが多く、ヒープ消費が大きい |
| バッチ点数は控えめに | 500 ワード以上を一度に読むと結果リストが大きくなる。小分けにすることを推奨 |
| 実用的な安全範囲 | 1リクエストあたり 10〜100 ワード / 8〜256 ビット程度が目安 |

## スコープ

**対応:**
- 3Eフレーム TCP
- Binary / ASCII エンコーディング
- ワードデバイス・ビットデバイスのバッチ読み書き

**非対応（設計上）:**
- UDP トランスポート
- ランダム読み書き（複数デバイス混在アクセス）
- モニタモード
- 拡張フレーム（4E など）
- リモート制御コマンド（Run / Stop / Reset）

## 注意事項

- Binary モードのビット読み書きでは、1バイトに2ビット分が格納されます（偶数番目は下位ニブル、奇数番目は上位ニブル）。
- ASCII モードでは、ワードデバイス（D, W など）のアドレスは10進数、ビットデバイス（X, Y など）のアドレスは16進数でエンコードされます。これは三菱電機の仕様に準拠しています。
- 1 回のリクエストで読み書きできる最大点数は PLC の機種によって異なります（バッチ読み取りは通常 960 ワード / 7168 ビットが上限）。

## テストの実行

```bash
python -m unittest test_mcprotocol -v
```

実機不要のモックテストです。39 件のテストがフレーム構築・レスポンス解析・エラー処理・入力バリデーション・接続ライフサイクルを検証します。

## ライセンス

MIT
