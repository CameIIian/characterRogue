# characterRogue

CUIで遊べるシンプルな1人用ローグライクボードゲームです。

## 実行方法

```bash
python3 game.py
```

## 操作

- `w` / `a` / `s` / `d`: 移動
- `f`: 隣接する敵へ攻撃（上下左右の順で最初に見つかった敵を攻撃）
- `.`: 待機
- `i`: インベントリ表示
- `u`: アイテム使用
- `h`: 操作/アイコンのヘルプ表示
- `q`: ゲーム終了

## アイコン一覧

- `#`: 壁（通行不可）
- `.`: 床（通行可）
- `@`: プレイヤー
- `E`: 敵
- `I`: アイテム
- `>`: 階段（次のフロアへ移動）

## ルール概要

- 初期ステータス: HP 10 / ATK 3 / DEF 1
- 敵に接触すると戦闘
- ダメージ式: `max(1, attacker_atk - defender_def)`
- 階段 `>` に到達すると次フロア
- 10階層到達で勝利、HP 0で敗北

## アイテムの種類とレアリティ

- アイテム種類: `Potion` / `Power` / `Shield` / `Ether`
  - `Potion`: HP回復
  - `Power`: ATK上昇
  - `Shield`: DEF上昇
  - `Ether`: MP回復
- レアリティ: `Common` / `Uncommon` / `Rare` / `Epic` / `Legendary`
- レアリティが高いほど出現率は低く、効果量は高くなります。

## テスト

```bash
python3 -m unittest discover -s tests -v
```
