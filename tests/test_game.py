import unittest
from unittest.mock import patch

from game import BOSS, FLOOR, MINIBOSS, WALL, Entity, Game, Spell, show_title_screen


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

    def test_stairs_and_items_do_not_overlap(self):
        g = Game(seed=42)
        stairs = g.stairs
        for item in g.items:
            self.assertNotEqual((item.x, item.y), stairs)

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

    def test_move_into_enemy_attacks_adjacent_enemy(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 3
        enemy = Entity(3, 2, hp=2, atk=1, defense=0)
        g.enemies = [enemy]
        g.items = []

        g.take_turn("d")

        self.assertEqual(len(g.enemies), 0)
        self.assertEqual(g.moves, 1)

    def test_enemy_does_not_retaliate_and_attack_again_in_same_turn(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.hp = 10
        g.player.defense = 0
        g.player.atk = 1
        enemy = Entity(3, 2, hp=10, atk=2, defense=0)
        g.enemies = [enemy]
        g.items = []

        g.take_turn("d")

        self.assertEqual(g.player.hp, 8)

    def test_help_command_shows_commands_and_icons(self):
        g = Game(seed=1)
        g.take_turn("h")
        log_text = "\n".join(g.message_log)
        self.assertIn("Commands:", log_text)
        self.assertIn("Icons:", log_text)
        self.assertNotIn("q=quit", log_text)
        self.assertNotIn("f=attack", log_text)

    def test_q_command_no_longer_quits(self):
        g = Game(seed=1)

        continue_game = g.take_turn("q")

        self.assertTrue(continue_game)
        self.assertIn("Invalid command.", "\n".join(g.message_log))

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
        self.assertEqual(g.player.atk, atk_before + 2)

    def test_technique_consumes_mp_and_damages_enemy(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.spells = [Spell("Flare Curtain", "Common")]
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

    def test_arcane_upgrade_learns_random_spell(self):
        g = Game(seed=1)
        g.skill_points = 1
        with patch.object(g.rng, "choice", return_value="Comet Missile"):
            upgraded = g.use_skill_point("a")
        self.assertTrue(upgraded)
        self.assertEqual(g.skill_tree["arcane"], 1)
        self.assertEqual(len(g.spells), 1)
        self.assertEqual(g.spells[0].name, "Comet Missile")

    def test_render_uses_miniboss_and_boss_icons(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 1, 1
        g.stairs = (3, 1)
        g.items = []
        g.enemies = [
            Entity(2, 2, hp=1, atk=1, defense=0, kind="miniboss"),
            Entity(3, 3, hp=1, atk=1, defense=0, kind="boss"),
        ]

        rendered = g.render()

        self.assertIn(MINIBOSS, rendered)
        self.assertIn(BOSS, rendered)

    def test_comet_missile_hits_straight_line_enemy(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player_mp = 10
        g.spells = [Spell("Comet Missile", "Common")]
        target = Entity(2, 4, hp=10, atk=1, defense=0)
        g.enemies = [target]

        used = g.use_technique()

        self.assertTrue(used)
        self.assertLess(target.hp, 10)
        self.assertLess(g.player_mp, 10)

    def test_gods_wrath_requires_one_turn_chant(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player_mp = 10
        g.spells = [Spell("God's Wrath", "Common")]
        g.enemies = [Entity(2, 1, hp=10, atk=1, defense=0), Entity(1, 2, hp=20, atk=1, defense=0)]

        first = g.use_technique()
        hp_before = max(e.hp for e in g.enemies)
        second = g.use_technique()
        hp_after = max(e.hp for e in g.enemies)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(hp_before, 20)
        self.assertLess(hp_after, hp_before)

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

    def test_calculate_score_reflects_floor_level_stats_and_arcana(self):
        g = Game(seed=1)
        g.floor = 8
        g.level = 4
        g.player_max_hp = 20
        g.player_max_mp = 9
        g.player.atk = 7
        g.player.defense = 5
        g.skill_tree["arcane"] = 2
        g.spells = [Spell("Comet Missile", "Rare"), Spell("Flare Curtain", "Legendary")]

        score = g.calculate_score()

        self.assertGreater(score, 0)
        self.assertEqual(score, g.calculate_score())

    def test_title_screen_allows_difficulty_selection_then_start(self):
        with patch("builtins.input", side_effect=["2", "3", "1"]):
            difficulty = show_title_screen()
        self.assertEqual(difficulty, "Hard")

    def test_floor_five_has_miniboss(self):
        g = Game(seed=1)
        g.floor = 5
        g.generate_floor()

        minibosses = [enemy for enemy in g.enemies if enemy.kind == "miniboss"]
        self.assertEqual(len(minibosses), 1)

    def test_stairs_locked_while_miniboss_is_alive(self):
        g = Game(seed=1)
        g.floor = 5
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.stairs = (3, 2)
        g.enemies = [Entity(1, 2, hp=10, atk=1, defense=0, kind="miniboss")]
        g.items = []

        g.move_player(1, 0)

        self.assertEqual(g.floor, 5)
        self.assertEqual((g.player.x, g.player.y), (3, 2))
        self.assertIn("Defeat the miniboss first", "\n".join(g.message_log))

    def test_miniboss_defeat_drops_high_rarity_item(self):
        g = Game(seed=1)
        g.floor = 5
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 20
        miniboss = Entity(3, 2, hp=1, atk=1, defense=0, kind="miniboss")
        g.enemies = [miniboss]
        g.items = []

        g.move_player(1, 0)

        self.assertEqual(len(g.enemies), 0)
        self.assertEqual(len(g.items), 1)
        self.assertIn(g.items[0].rarity, {"Rare", "Epic", "Legendary"})

    def test_floor_ten_has_boss(self):
        g = Game(seed=1)
        g.floor = 10
        g.generate_floor()

        bosses = [enemy for enemy in g.enemies if enemy.kind == "boss"]
        self.assertEqual(len(bosses), 1)

    def test_boss_defeat_drops_legendary_item(self):
        g = Game(seed=1)
        g.floor = 10
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 99
        boss = Entity(3, 2, hp=1, atk=1, defense=0, kind="boss")
        g.enemies = [boss]
        g.items = []

        g.move_player(1, 0)

        self.assertEqual(len(g.enemies), 0)
        self.assertEqual(len(g.items), 1)
        self.assertEqual(g.items[0].rarity, "Legendary")

    def test_boss_summon_spawns_two_minions_away_from_player(self):
        g = Game(seed=1, width=8, height=8)
        g.board = [[WALL for _ in range(8)] for _ in range(8)]
        for y in range(1, 7):
            for x in range(1, 7):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 3, 3
        boss = Entity(5, 5, hp=30, atk=9, defense=5, kind="boss")
        g.enemies = [boss]

        summoned = g.summon_boss_minions(2)

        self.assertEqual(summoned, 2)
        spawned = [e for e in g.enemies if e is not boss]
        self.assertEqual(len(spawned), 2)
        for minion in spawned:
            self.assertGreaterEqual(abs(minion.x - g.player.x) + abs(minion.y - g.player.y), 2)
            self.assertEqual((minion.hp, minion.atk, minion.defense), (15, 6, 3))

    def test_boss_enrage_triggers_once_and_fully_heals(self):
        g = Game(seed=1)
        boss = Entity(4, 4, hp=14, atk=9, defense=5, kind="boss")
        g.boss_laser_targets = []
        g.enemies = [boss]
        g.player.x, g.player.y = 1, 1

        with patch.object(g.rng, "choice", return_value="attack"):
            g.boss_turn(boss)
        self.assertTrue(g.boss_enraged)
        self.assertEqual(boss.hp, 33)
        self.assertEqual((boss.atk, boss.defense), (11, 6))

        previous_stats = (boss.hp, boss.atk, boss.defense)
        boss.hp = 10
        with patch.object(g.rng, "choice", return_value="attack"):
            g.boss_turn(boss)
        self.assertEqual((boss.hp, boss.atk, boss.defense), (10, previous_stats[1], previous_stats[2]))

    def test_floor_advances_beyond_ten(self):
        g = Game(seed=1)
        g.floor = 10
        g.advance_floor()

        self.assertEqual(g.floor, 11)
        self.assertFalse(g.won())

    def test_floor_fifteen_has_miniboss_and_twenty_has_boss(self):
        g = Game(seed=1)
        g.floor = 15
        g.generate_floor()
        self.assertEqual(len([e for e in g.enemies if e.kind == "miniboss"]), 1)

        g.floor = 20
        g.generate_floor()
        self.assertEqual(len([e for e in g.enemies if e.kind == "boss"]), 1)

    def test_new_loop_expands_map_width(self):
        g = Game(seed=1, width=10, height=10)
        g.floor = 10
        g.width = 10

        g.advance_floor()

        self.assertEqual(g.floor, 11)
        self.assertEqual(g.width, 12)


if __name__ == "__main__":
    unittest.main()
