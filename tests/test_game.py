import unittest
from unittest.mock import patch

from game import FLOOR, WALL, Entity, Game


class GameTests(unittest.TestCase):
    def test_damage_formula(self):
        self.assertEqual(Game.damage(5, 2), 3)
        self.assertEqual(Game.damage(1, 10), 1)

    def test_wall_collision(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 1, 1
        g.move_player(-1, 0)
        self.assertEqual((g.player.x, g.player.y), (1, 1))

    def test_floor_has_reachable_stairs(self):
        g = Game(seed=42)
        self.assertTrue(g.is_reachable((g.player.x, g.player.y), g.stairs))

    def test_combat_removes_dead_enemy(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        enemy = Entity(3, 2, hp=1, atk=1, defense=0)
        g.enemies = [enemy]
        g.items = []
        g.move_player(1, 0)
        self.assertEqual(len(g.enemies), 0)
        self.assertGreater(g.xp, 0)

    def test_attack_command_hits_adjacent_enemy(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 3
        enemy = Entity(2, 1, hp=2, atk=1, defense=0)
        g.enemies = [enemy]
        g.items = []

        g.take_turn("f")

        self.assertEqual(len(g.enemies), 0)
        self.assertEqual(g.moves, 1)

    def test_help_command_shows_commands_and_icons(self):
        g = Game(seed=1)
        g.take_turn("h")
        log_text = "\n".join(g.message_log)
        self.assertIn("Commands:", log_text)
        self.assertIn("Icons:", log_text)

    def test_level_up_restores_hp_mp_and_grants_skill_point(self):
        g = Game(seed=1)
        g.player.hp = 1
        g.player_mp = 0
        g.gain_xp(100)

        self.assertGreater(g.level, 1)
        self.assertEqual(g.player.hp, g.player_max_hp)
        self.assertEqual(g.player_mp, g.player_max_mp)
        self.assertGreaterEqual(g.skill_points, 1)

    def test_skill_tree_upgrade_consumes_skill_point(self):
        g = Game(seed=1)
        g.skill_points = 1
        atk_before = g.player.atk

        upgraded = g.use_skill_point("s")

        self.assertTrue(upgraded)
        self.assertEqual(g.skill_points, 0)
        self.assertEqual(g.player.atk, atk_before + 1)

    def test_technique_consumes_mp_and_damages_enemy(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.skill_tree["arcane"] = 1
        g.player_mp = 5
        enemy = Entity(2, 1, hp=20, atk=1, defense=0)
        g.enemies = [enemy]

        used = g.use_technique()

        self.assertTrue(used)
        self.assertLess(g.player_mp, 5)
        self.assertLess(enemy.hp, 20)

    def test_open_skill_menu_uses_input_choice(self):
        g = Game(seed=1)
        g.skill_points = 1

        with patch("builtins.input", return_value="v"):
            opened = g.open_skill_menu()

        self.assertTrue(opened)
        self.assertEqual(g.skill_tree["vitality"], 1)

    def test_status_lines_layout_matches_expected_order(self):
        g = Game(seed=1)

        lines = g.status_lines()

        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("Floor:"))
        self.assertIn("Moves:", lines[0])
        self.assertTrue(lines[1].startswith("HP:"))
        self.assertIn("MP:", lines[1])
        self.assertIn("SP:", lines[1])
        self.assertTrue(lines[2].startswith("Lv:"))
        self.assertIn("XP:", lines[2])
        self.assertIn("ATK:", lines[2])
        self.assertIn("DEF:", lines[2])

    def test_legendary_item_is_stronger_than_common_item(self):
        g = Game(seed=1)
        g.player.hp = 1
        g.player_max_hp = 30

        g.inventory.append(("Common", "Potion"))
        g.use_item()
        common_hp = g.player.hp

        g.player.hp = 1
        g.inventory.append(("Legendary", "Potion"))
        g.use_item()
        legendary_hp = g.player.hp

        self.assertGreater(legendary_hp, common_hp)

    def test_item_rarity_distribution_favors_common(self):
        g = Game(seed=1)
        counts = {}

        for _ in range(2000):
            rarity = g.roll_item_rarity()
            counts[rarity] = counts.get(rarity, 0) + 1

        self.assertGreater(counts["Common"], counts["Uncommon"])
        self.assertGreater(counts["Uncommon"], counts["Rare"])
        self.assertGreater(counts["Rare"], counts["Epic"])
        self.assertGreater(counts["Epic"], counts["Legendary"])


if __name__ == "__main__":
    unittest.main()
