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
| TN | 0xC2 | ワード |
| CN | 0xC5 | ワード |

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

### `MCProtocol3E(host, port=1025, mode='binary', timeout=5.0)`

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `host` | — | PLC の IP アドレス |
| `port` | `1025` | TCP ポート番号 |
| `mode` | `'binary'` | `'binary'` または `'ascii'` |
| `timeout` | `5.0` | ソケットタイムアウト（秒） |

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

通信エラー時は PLC のエンドコードを含む `RuntimeError` を送出します。

## 注意事項

- ASCII モードでは、ワードデバイス（D, W など）のアドレスは10進数、ビットデバイス（X, Y など）のアドレスは16進数でエンコードされます。これは三菱電機の仕様に準拠しています。
- 1 回のリクエストで読み書きできる最大点数は PLC の機種によって異なります（バッチ読み取りは通常 960 ワード / 7168 ビットが上限）。
- リモート制御コマンド（Run / Stop / Reset）は意図的に省いています。

## テストの実行

```bash
python -m unittest test_mcprotocol -v
```

実機不要のモックテストです。29 件のテストがフレーム構築・レスポンス解析・エラー処理・接続ライフサイクルを検証します。

## ライセンス

MIT
