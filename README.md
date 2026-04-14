# Roguelike_board_game

CUIで遊べるシンプルな1人用ローグライクボードゲームです。

## 実行方法

```bash
python3 game.py
```

## 操作

- `w` / `a` / `s` / `d`: 移動
- `.`: 待機
- `i`: インベントリ表示
- `u`: アイテム使用
- `q`: ゲーム終了

## ルール概要

- 初期ステータス: HP 10 / ATK 3 / DEF 1
- 敵に接触すると戦闘
- ダメージ式: `max(1, attacker_atk - defender_def)`
- 階段 `>` に到達すると次フロア
- 10階層到達で勝利、HP 0で敗北

## テスト

```bash
python3 -m unittest discover -s tests -v
```
