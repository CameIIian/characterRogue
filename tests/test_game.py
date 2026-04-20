import unittest
from unittest.mock import patch

from game import BOSS, FLOOR, FORTIFIED_ENEMY, FRIENDLY, MINIBOSS, WALL, Entity, FriendlyEntity, Game, Spell, show_title_screen


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

    def test_flare_curtain_hits_all_8_surrounding_tiles(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 3, 3
        g.player.atk = 5
        g.player_mp = 10
        g.spells = [Spell("Flare Curtain", "Common")]
        targets = [
            Entity(2, 2, hp=10, atk=1, defense=0),
            Entity(3, 2, hp=10, atk=1, defense=0),
            Entity(4, 2, hp=10, atk=1, defense=0),
            Entity(2, 3, hp=10, atk=1, defense=0),
            Entity(4, 3, hp=10, atk=1, defense=0),
            Entity(2, 4, hp=10, atk=1, defense=0),
            Entity(3, 4, hp=10, atk=1, defense=0),
            Entity(4, 4, hp=10, atk=1, defense=0),
            Entity(1, 1, hp=10, atk=1, defense=0),
        ]
        g.enemies = targets

        used = g.use_technique()

        self.assertTrue(used)
        for enemy in targets[:-1]:
            self.assertLess(enemy.hp, 10)
        self.assertEqual(targets[-1].hp, 10)

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

    def test_arcane_upgrade_can_keep_existing_and_discard_new(self):
        g = Game(seed=1)
        g.skill_points = 1
        g.spells = [Spell("Flare Curtain", "Rare")]

        with patch.object(g.rng, "choice", return_value="Comet Missile"), patch("builtins.input", return_value="1"):
            upgraded = g.use_skill_point("a")

        self.assertTrue(upgraded)
        self.assertEqual(len(g.spells), 1)
        self.assertEqual(g.spells[0].name, "Flare Curtain")

    def test_arcane_upgrade_can_replace_existing_with_new(self):
        g = Game(seed=1)
        g.skill_points = 1
        g.spells = [Spell("Flare Curtain", "Rare")]

        with patch.object(g.rng, "choice", return_value="Comet Missile"), patch("builtins.input", return_value="2"):
            upgraded = g.use_skill_point("a")

        self.assertTrue(upgraded)
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
        g.friendlies = []
        g.enemies = [
            Entity(2, 2, hp=1, atk=1, defense=0, kind="miniboss"),
            Entity(3, 3, hp=1, atk=1, defense=0, kind="boss"),
        ]

        rendered = g.render()

        self.assertIn(MINIBOSS, rendered)
        self.assertIn(BOSS, rendered)

    def test_render_shows_fortified_enemy_icon(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 1, 1
        g.stairs = (3, 1)
        g.items = []
        g.friendlies = []
        g.enemies = [Entity(2, 2, hp=30, atk=0, defense=99, kind="fortified")]

        rendered = g.render()

        self.assertIn(FORTIFIED_ENEMY, rendered)

    def test_render_shows_friendly_icon(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 1, 1
        g.stairs = (3, 1)
        g.items = []
        g.enemies = []
        g.friendlies = [FriendlyEntity(2, 2)]

        rendered = g.render()

        self.assertIn(FRIENDLY, rendered)

    def test_generate_floor_spawns_at_most_one_friendly(self):
        g = Game(seed=1)

        self.assertLessEqual(len(g.friendlies), 1)

    def test_fortified_enemy_does_not_attack(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.hp = 10
        g.enemies = [Entity(3, 2, hp=20, atk=999, defense=99, kind="fortified")]
        g.enemy_turn()

        self.assertEqual(g.player.hp, 10)

    def test_boss_laser_marks_only_cardinal_lines(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        boss = Entity(3, 3, hp=20, atk=10, defense=3, kind="boss")
        targets = g.collect_boss_laser_tiles(boss)

        self.assertIn((3, 1), targets)
        self.assertIn((1, 3), targets)
        self.assertNotIn((1, 1), targets)

    def test_turn_log_skips_move_only_turn(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.enemies = []
        g.items = []
        g.friendlies = []

        g.take_turn("d")

        self.assertEqual(len(g.turn_logs), 0)

    def test_turn_log_collects_non_move_events(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.enemies = [Entity(3, 2, hp=2, atk=1, defense=0)]
        g.items = []
        g.friendlies = []

        g.take_turn("d")

        self.assertEqual(len(g.turn_logs), 1)
        self.assertIn("You hit the enemy", g.turn_logs[-1])

    def test_turn_log_keeps_latest_ten_entries(self):
        g = Game(seed=1)

        for _ in range(11):
            g.take_turn(".")

        self.assertEqual(len(g.turn_logs), 10)

    def test_show_inventory_displays_numbered_entries(self):
        g = Game(seed=1)
        g.inventory = [("Common", "Potion"), ("Rare", "Shield")]

        g.show_inventory()

        log_text = "\n".join(g.message_log)
        self.assertIn("Inventory:", log_text)
        self.assertIn("1: Common Potion", log_text)
        self.assertIn("2: Rare Shield", log_text)

    def test_u_with_number_uses_specific_inventory_slot(self):
        g = Game(seed=1)
        g.inventory = [("Common", "Potion"), ("Rare", "Shield")]
        g.player.defense = 1
        g.enemies = []

        g.take_turn("u 2")

        self.assertEqual(g.player.defense, 5)
        self.assertEqual(len(g.inventory), 1)
        self.assertEqual(g.inventory[0], ("Common", "Potion"))

    def test_u_prioritizes_stat_boost_over_recovery_and_accessory(self):
        g = Game(seed=1)
        g.inventory = [
            ("Common", "Potion"),
            ("Common", "Shield"),
            ("Rare", "Lucky amulet"),
        ]
        g.player.hp = 1
        g.player_max_hp = 10
        g.equipped_accessory = None
        g.enemies = []
        base_defense = g.player.defense

        g.take_turn("u")

        self.assertEqual(g.player.defense, base_defense + 1)
        self.assertNotIn(("Common", "Shield"), g.inventory)

    def test_u_prioritizes_recovery_when_no_stat_boost_item(self):
        g = Game(seed=1)
        g.inventory = [
            ("Common", "Potion"),
            ("Rare", "Lucky amulet"),
        ]
        g.player.hp = 3
        g.player_max_hp = 10
        g.equipped_accessory = None
        g.enemies = []

        g.take_turn("u")

        self.assertGreater(g.player.hp, 3)
        self.assertNotIn(("Common", "Potion"), g.inventory)

    def test_u_prioritizes_rarer_accessory_when_no_other_priority(self):
        g = Game(seed=1)
        g.inventory = [("Rare", "Lucky amulet")]
        g.player.hp = g.player_max_hp
        g.player_mp = g.player_max_mp
        g.equipped_accessory = ("Common", "Kote")
        g.enemies = []

        g.take_turn("u")

        self.assertEqual(g.equipped_accessory, ("Rare", "Lucky amulet"))
        self.assertEqual(g.inventory, [("Common", "Kote")])

    def test_u_without_priority_falls_back_to_number_selection(self):
        g = Game(seed=1)
        g.inventory = [("Common", "Throwing axe"), ("Common", "Bomb")]
        g.enemies = []

        with patch("builtins.input", return_value="2"):
            g.take_turn("u")

        self.assertEqual(g.inventory, [("Common", "Throwing axe"), ("Common", "Bomb")])
        self.assertIn("Bomb had no effect", "\n".join(g.message_log))

    def test_vampires_fang_converts_hp_overflow_to_mp(self):
        g = Game(seed=1)
        g.player_max_hp = 20
        g.player.hp = 18
        g.player_max_mp = 10
        g.player_mp = 4
        g.equipped_accessory = ("Rare", "Vampire's Fang")

        healed, converted_mp = g.restore_hp(10)

        self.assertEqual(healed, 2)
        self.assertEqual(converted_mp, 4)  # (10 - 2) * 0.60 = 4.8 -> 4
        self.assertEqual(g.player.hp, 20)
        self.assertEqual(g.player_mp, 8)

    def test_dark_wizards_staff_converts_mp_overflow_to_hp(self):
        g = Game(seed=1)
        g.player_max_mp = 10
        g.player_mp = 9
        g.player_max_hp = 25
        g.player.hp = 10
        g.equipped_accessory = ("Epic", "Dark Wizard's Staff")

        restored, converted_hp = g.restore_mp(6)

        self.assertEqual(restored, 1)
        self.assertEqual(converted_hp, 4)  # (6 - 1) * 0.80 = 4
        self.assertEqual(g.player_mp, 10)
        self.assertEqual(g.player.hp, 14)

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

    def test_gunpowder_box_chains_overflow_on_normal_attack(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 10
        g.equipped_accessory = ("Legendary", "Gunpowder box")
        front_enemy = Entity(3, 2, hp=2, atk=1, defense=0)
        splash_enemy = Entity(4, 2, hp=4, atk=1, defense=0)
        g.enemies = [front_enemy, splash_enemy]
        g.items = []

        g.take_turn("d")

        self.assertEqual(len(g.enemies), 0)
        self.assertTrue(any("Gunpowder box triggers!" in msg for msg in g.message_log))

    def test_gunpowder_box_chains_overflow_on_arcana(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 10
        g.player_mp = 10
        g.spells = [Spell("Comet Missile", "Common")]
        g.equipped_accessory = ("Legendary", "Gunpowder box")
        line_enemy = Entity(2, 4, hp=2, atk=1, defense=0)
        adjacent_enemy = Entity(3, 4, hp=4, atk=1, defense=0)
        g.enemies = [line_enemy, adjacent_enemy]

        used = g.use_technique()

        self.assertTrue(used)
        self.assertEqual(len(g.enemies), 0)
        self.assertLess(g.player_mp, 10)

    def test_comet_missile_can_choose_direction_when_multiple_lines_have_targets(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 3, 3
        g.player.atk = 6
        g.player_mp = 10
        g.spells = [Spell("Comet Missile", "Common")]
        down_target = Entity(3, 4, hp=10, atk=1, defense=0)
        right_target = Entity(4, 3, hp=10, atk=1, defense=0)
        g.enemies = [down_target, right_target]

        with patch("builtins.input", return_value="d"):
            used = g.use_technique()

        self.assertTrue(used)
        self.assertLess(right_target.hp, 10)
        self.assertEqual(down_target.hp, 10)

    def test_healing_spell_restores_hp_and_consumes_mp(self):
        g = Game(seed=1)
        g.player_max_hp = 50
        g.player.hp = 10
        g.player_mp = 10
        g.spells = [Spell("Healing", "Rare")]

        used = g.use_technique()

        self.assertTrue(used)
        self.assertEqual(g.player.hp, 22)
        self.assertEqual(g.player_mp, 7)

    def test_vampires_fang_converts_hp_overflow_to_mp(self):
        g = Game(seed=1)
        g.player_max_hp = 20
        g.player.hp = 19
        g.player_max_mp = 20
        g.player_mp = 1
        g.equipped_accessory = ("Epic", "Vampire's Fang")

        healed, converted_mp = g.restore_hp(10)

        self.assertEqual(healed, 1)
        self.assertEqual(converted_mp, 7)
        self.assertEqual(g.player.hp, 20)
        self.assertEqual(g.player_mp, 8)

    def test_dark_wizards_staff_converts_mp_overflow_to_hp(self):
        g = Game(seed=1)
        g.player_max_mp = 10
        g.player_mp = 9
        g.player_max_hp = 30
        g.player.hp = 1
        g.equipped_accessory = ("Rare", "Dark Wizard's Staff")

        restored, converted_hp = g.restore_mp(10)

        self.assertEqual(restored, 1)
        self.assertEqual(converted_hp, 5)
        self.assertEqual(g.player_mp, 10)
        self.assertEqual(g.player.hp, 6)

    def test_overflow_conversion_ratio_scales_with_rarity(self):
        g = Game(seed=1)
        self.assertEqual(g.accessory_overflow_ratio("Vampire's Fang", "Common"), 0.20)
        self.assertEqual(g.accessory_overflow_ratio("Vampire's Fang", "Uncommon"), 0.40)
        self.assertEqual(g.accessory_overflow_ratio("Vampire's Fang", "Rare"), 0.60)
        self.assertEqual(g.accessory_overflow_ratio("Vampire's Fang", "Epic"), 0.80)
        self.assertEqual(g.accessory_overflow_ratio("Vampire's Fang", "Legendary"), 1.00)
        self.assertEqual(g.accessory_overflow_ratio("Dark Wizard's Staff", "Common"), 0.20)
        self.assertEqual(g.accessory_overflow_ratio("Dark Wizard's Staff", "Legendary"), 1.00)

    def test_vampire_kiss_uses_rarity_damage_and_drains_hp(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 9
        g.player.hp = 5
        g.player_max_hp = 20
        g.player_mp = 10
        g.spells = [Spell("Vampire Kiss", "Rare")]
        enemy = Entity(2, 1, hp=30, atk=1, defense=0)
        g.enemies = [enemy]

        used = g.use_technique()

        self.assertTrue(used)
        self.assertEqual(enemy.hp, 21)
        self.assertEqual(g.player.hp, 8)
        self.assertEqual(g.player_mp, 6)

    def test_vampire_kiss_can_choose_direction_for_adjacent_target(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 6
        g.player_mp = 10
        g.spells = [Spell("Vampire Kiss", "Common")]
        up_enemy = Entity(2, 1, hp=10, atk=1, defense=0)
        right_enemy = Entity(3, 2, hp=10, atk=1, defense=0)
        g.enemies = [up_enemy, right_enemy]

        with patch("builtins.input", return_value="d"):
            used = g.use_technique()

        self.assertTrue(used)
        self.assertLess(right_enemy.hp, 10)
        self.assertEqual(up_enemy.hp, 10)

    def test_gods_wrath_can_charge_multiple_times_and_empowers_next_normal_attack(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 6
        g.player_mp = 10
        g.spells = [Spell("God's Wrath", "Common")]
        target = Entity(2, 1, hp=200, atk=1, defense=0)
        g.enemies = [target]

        first_charge = g.use_technique()
        second_charge = g.use_technique()
        hp_before_attack = target.hp
        g.attack_adjacent()
        hp_after_attack = target.hp

        expected_damage = int(g.damage(g.player.atk, target.defense) * ((1.5 * 1.0) ** 2))
        self.assertTrue(first_charge)
        self.assertTrue(second_charge)
        self.assertEqual(g.player_mp, 2)
        self.assertEqual(g.gods_wrath_charge_count, 0)
        self.assertEqual(hp_before_attack - hp_after_attack, expected_damage)

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

    def test_guardians_armor_stacks_on_wait_and_resets_on_move(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.defense = 10
        g.enemies = []
        g.items = []
        g.friendlies = []
        g.equip_accessory("Rare", "Guardian's Armor")

        g.take_turn(".")
        first_wait_def = g.player.defense
        g.take_turn(".")
        second_wait_def = g.player.defense
        g.take_turn("d")

        self.assertEqual(first_wait_def, 13)
        self.assertEqual(second_wait_def, 18)
        self.assertEqual(g.player.defense, 10)

    def test_guardians_armor_uses_rarity_multiplier_table(self):
        g = Game(seed=1)
        g.player.defense = 20
        g.equip_accessory("Legendary", "Guardian's Armor")

        g.stack_guardian_armor_defense()

        self.assertEqual(g.player.defense, 35)

    def test_status_screen_shows_accessory_and_arcana_descriptions(self):
        g = Game(seed=1)
        g.equip_accessory("Epic", "Kote")
        g.spells = [Spell("Healing", "Rare")]

        g.show_status_details()
        text = "\n".join(g.message_log)

        self.assertIn("=== Status Details ===", text)
        self.assertIn("Accessory: Epic Kote", text)
        self.assertIn("Raises ATK and DEF while equipped.", text)
        self.assertIn("Arcana: Rare Healing", text)
        self.assertIn("Consumes MP to restore your HP.", text)

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

    def test_can_use_non_first_inventory_item(self):
        g = Game(seed=1)
        g.player.atk = 3
        g.inventory = [("Common", "Shield"), ("Common", "Power")]

        with patch("builtins.input", return_value="2"):
            g.use_item()

        self.assertEqual(g.player.atk, 4)
        self.assertEqual(g.inventory, [("Common", "Shield")])

    def test_throwing_axe_hits_enemy_in_selected_direction(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        target = Entity(2, 4, hp=20, atk=1, defense=0)
        g.enemies = [target]
        g.inventory = [("Rare", "Throwing axe")]

        with patch("builtins.input", return_value="s"):
            g.use_item()

        self.assertEqual(target.hp, 11)

    def test_bomb_damages_all_enemies(self):
        g = Game(seed=1)
        enemy1 = Entity(1, 1, hp=20, atk=1, defense=0)
        enemy2 = Entity(2, 1, hp=10, atk=1, defense=0)
        g.enemies = [enemy1, enemy2]
        g.inventory = [("Epic", "Bomb")]

        g.use_item()

        self.assertEqual(enemy1.hp, 12)
        self.assertEqual(enemy2.hp, 6)

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

    def test_trade_rarity_distribution_is_better_than_normal_pickups(self):
        g = Game(seed=1)
        normal_counts = {}
        trade_counts = {}

        for _ in range(4000):
            normal = g.roll_item_rarity()
            trade = g.roll_trade_rarity()
            normal_counts[normal] = normal_counts.get(normal, 0) + 1
            trade_counts[trade] = trade_counts.get(trade, 0) + 1

        normal_high = normal_counts["Rare"] + normal_counts["Epic"]
        trade_high = trade_counts["Rare"] + trade_counts["Epic"]
        normal_low = normal_counts["Common"] + normal_counts["Uncommon"]
        trade_low = trade_counts["Common"] + trade_counts["Uncommon"]

        self.assertGreater(trade_high, normal_high)
        self.assertLess(trade_low, normal_low)

    def test_friendly_trade_is_once_per_friendly(self):
        g = Game(seed=1)
        g.inventory = [("Common", "Potion")]
        f = FriendlyEntity(1, 1, traded=False)
        g.friendlies = [f]

        with patch("builtins.input", return_value="1"), patch.object(g.rng, "choice", return_value="Bomb"), patch.object(
            g, "roll_trade_rarity", return_value="Rare"
        ):
            g.trade_with_friendly(f)

        inventory_after_first_trade = list(g.inventory)
        g.trade_with_friendly(f)

        self.assertTrue(f.traded)
        self.assertEqual(g.inventory, inventory_after_first_trade)

    def test_friendly_demon_trade_sacrifices_hp_and_splits_stats(self):
        g = Game(seed=1)
        demon = FriendlyEntity(1, 1, role="friendly demon", traded=False)
        g.friendlies = [demon]
        g.player.hp = 10
        g.player.atk = 3
        g.player.defense = 2

        with patch("builtins.input", side_effect=["4", "1"]):
            g.trade_with_friendly(demon)

        self.assertTrue(demon.traded)
        self.assertEqual(g.player.hp, 6)
        self.assertEqual(g.player.atk, 4)
        self.assertEqual(g.player.defense, 5)

    def test_friendly_roles_spawn_only_once_per_10_floor_cycle(self):
        g = Game(seed=1)
        g.friendlies = []

        spawn_rolls = [5, 5, 1, 1]
        with patch.object(g, "random_empty_tile", return_value=(1, 1)), patch.object(g.rng, "randint", side_effect=spawn_rolls):
            for floor in range(1, 11):
                g.floor = floor
                g.friendlies = []
                g.maybe_spawn_friendly()

        spawned_roles = sorted(g.spawned_friendly_roles_in_cycle)
        self.assertEqual(spawned_roles, ["friendly demon", "maze traveler", "merchant", "technician"])

    def test_technician_trades_item_for_arcana(self):
        g = Game(seed=1)
        g.inventory = [("Common", "Potion")]
        technician = FriendlyEntity(1, 1, role="technician", traded=False)
        g.friendlies = [technician]

        with patch.object(g.rng, "choice", return_value="Healing"), patch.object(
            g, "roll_trade_rarity_by_offer_count", return_value="Epic"
        ):
            g.trade_with_friendly(technician)

        self.assertTrue(technician.traded)
        self.assertEqual(g.inventory, [])
        self.assertEqual(len(g.spells), 1)
        self.assertEqual((g.spells[0].name, g.spells[0].rarity), ("Healing", "Epic"))

    def test_maze_traveler_sets_next_floor_destination(self):
        g = Game(seed=1)
        g.floor = 6
        traveler = FriendlyEntity(1, 1, role="maze traveler", traded=False)
        g.friendlies = [traveler]

        with patch.object(g.rng, "choice", return_value=12):
            g.trade_with_friendly(traveler)

        self.assertTrue(traveler.traded)
        self.assertEqual(g.next_floor_destination, 12)

    def test_advance_floor_uses_maze_traveler_destination(self):
        g = Game(seed=1)
        g.floor = 6
        g.next_floor_destination = 3

        g.advance_floor()

        self.assertEqual(g.floor, 3)
        self.assertIsNone(g.next_floor_destination)

    def test_floor_clear_bonus_scales_with_floor_depth(self):
        g = Game(seed=1)
        g.floor = 7
        g.enemies = []

        g.maybe_grant_floor_clear_bonus()

        self.assertTrue(g.floor_clear_bonus_granted)
        self.assertIn("Floor clear bonus! +19 XP", "\n".join(g.message_log))

    def test_frugal_soul_can_preserve_next_item(self):
        g = Game(seed=1)
        g.spells = [Spell("Frugal soul", "Rare")]
        g.player_mp = 10
        g.inventory = [("Common", "Potion")]

        used = g.use_technique()
        with patch.object(g.rng, "random", return_value=0.1):
            g.use_item()

        self.assertTrue(used)
        self.assertEqual(g.player_mp, 6)
        self.assertEqual(len(g.inventory), 1)

    def test_frugal_soul_consumes_buff_after_one_item_use(self):
        g = Game(seed=1)
        g.spells = [Spell("Frugal soul", "Legendary")]
        g.player_mp = 10
        g.inventory = [("Common", "Potion"), ("Common", "Potion")]

        g.use_technique()
        with patch("builtins.input", return_value="1"), patch.object(g.rng, "random", return_value=0.0):
            g.use_item()
        with patch("builtins.input", return_value="1"), patch.object(g.rng, "random", return_value=0.0):
            g.use_item()

        self.assertEqual(len(g.inventory), 1)

    def test_calculate_score_reflects_floor_level_stats_and_arcana(self):
        g = Game(seed=1)
        g.floor = 8
        g.level = 4
        g.player_max_hp = 20
        g.player_max_mp = 9
        g.player.atk = 7
        g.player.defense = 5
        g.skill_tree["arcane"] = 2
        g.spells = [Spell("Flare Curtain", "Legendary")]

        score = g.calculate_score()

        self.assertGreater(score, 0)
        self.assertEqual(score, g.calculate_score())

    def test_title_screen_allows_difficulty_selection_then_start(self):
        with patch("builtins.input", side_effect=["2", "3", "1"]):
            difficulty = show_title_screen()
        self.assertEqual(difficulty, "Hard")

    def test_difficulty_enemy_power_multiplier_values(self):
        self.assertEqual(Game(seed=1, difficulty="Easy").enemy_power_multiplier, 0.5)
        self.assertEqual(Game(seed=1, difficulty="Normal").enemy_power_multiplier, 1.0)
        self.assertEqual(Game(seed=1, difficulty="Hard").enemy_power_multiplier, 1.5)
        self.assertEqual(Game(seed=1, difficulty="Lunatic").enemy_power_multiplier, 2.0)


    def test_boss_stats_are_scaled_higher(self):
        g = Game(seed=1)
        g.floor = 10
        g.generate_floor()

        boss = next(enemy for enemy in g.enemies if enemy.kind == "boss")

        self.assertGreaterEqual(boss.hp, 70)
        self.assertGreaterEqual(boss.defense, 11)

    def test_using_accessory_equips_it_and_applies_kote_bonus(self):
        g = Game(seed=1)
        base_atk = g.player.atk
        base_def = g.player.defense
        g.inventory = [("Rare", "Kote")]

        g.use_item()

        self.assertEqual(g.equipped_accessory, ("Rare", "Kote"))
        self.assertEqual(g.player.atk, base_atk + 3)
        self.assertEqual(g.player.defense, base_def + 3)
        self.assertEqual(g.inventory, [])

    def test_equipping_new_accessory_returns_previous_to_inventory(self):
        g = Game(seed=1)
        g.inventory = [("Common", "Lucky amulet"), ("Epic", "Kote")]

        with patch("builtins.input", side_effect=["1", "1"]):
            g.use_item()
            g.use_item()

        self.assertEqual(g.equipped_accessory, ("Epic", "Kote"))
        self.assertIn(("Common", "Lucky amulet"), g.inventory)
        self.assertNotIn(("Epic", "Kote"), g.inventory)

    def test_lucky_amulet_boosts_xp_by_rarity(self):
        g = Game(seed=1)
        g.equipped_accessory = ("Legendary", "Lucky amulet")
        g.next_level_xp = 999

        g.gain_xp(10)

        self.assertEqual(g.xp, 18)

    def test_merchant_trade_can_grant_accessory(self):
        g = Game(seed=1)
        g.inventory = [("Common", "Potion")]
        merchant = FriendlyEntity(1, 1, role="merchant", traded=False)

        with patch("builtins.input", return_value="1"), patch.object(g, "random_item_kind", return_value="Kote"), patch.object(
            g, "roll_trade_rarity_by_offer_count", return_value="Epic"
        ):
            g.trade_with_friendly(merchant)

        self.assertIn(("Epic", "Kote"), g.inventory)

    def test_merchant_trade_accepts_up_to_five_items(self):
        g = Game(seed=1)
        g.inventory = [
            ("Common", "Potion"),
            ("Uncommon", "Shield"),
            ("Rare", "Power"),
            ("Epic", "Ether"),
            ("Legendary", "Bomb"),
            ("Common", "Throwing axe"),
        ]
        merchant = FriendlyEntity(1, 1, role="merchant", traded=False)

        with patch("builtins.input", side_effect=["5", "1", "2", "3", "4", "5"]), patch.object(
            g, "random_item_kind", return_value="Kote"
        ), patch.object(g, "roll_trade_rarity_by_offer_count", return_value="Legendary") as rarity_mock:
            g.trade_with_friendly(merchant)

        self.assertTrue(merchant.traded)
        rarity_mock.assert_called_once_with(5)
        self.assertEqual(len(g.inventory), 2)
        self.assertIn(("Common", "Throwing axe"), g.inventory)
        self.assertIn(("Legendary", "Kote"), g.inventory)

    def test_technician_trade_without_inventory_grants_common_arcana(self):
        g = Game(seed=1)
        g.inventory = []
        technician = FriendlyEntity(1, 1, role="technician", traded=False)

        with patch.object(g.rng, "choice", return_value="Healing"):
            g.trade_with_friendly(technician)

        self.assertTrue(technician.traded)
        self.assertEqual(len(g.spells), 1)
        self.assertEqual((g.spells[0].name, g.spells[0].rarity), ("Healing", "Common"))
        self.assertIn("starter Arcana sample", "\n".join(g.message_log))

    def test_merchant_trade_without_inventory_grants_common_item(self):
        g = Game(seed=1)
        g.inventory = []
        merchant = FriendlyEntity(1, 1, role="merchant", traded=False)

        with patch.object(g, "random_item_kind", return_value="Potion"):
            g.trade_with_friendly(merchant)

        self.assertTrue(merchant.traded)
        self.assertEqual(g.inventory, [("Common", "Potion")])
        self.assertIn("empty-handed", "\n".join(g.message_log))

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
            self.assertEqual((minion.hp, minion.atk, minion.defense), (15, 12, 3))

    def test_boss_laser_damage_is_three_times_boss_attack(self):
        g = Game(seed=1)
        g.board = [[WALL for _ in range(5)] for _ in range(5)]
        for y in range(1, 4):
            for x in range(1, 4):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.hp = 100
        g.player.defense = 5
        boss = Entity(3, 2, hp=30, atk=10, defense=5, kind="boss")
        g.enemies = [boss]
        g.boss_laser_targets = [(2, 2)]

        g.resolve_boss_laser()

        self.assertEqual(g.player.hp, 75)

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

    def test_berserkers_club_sets_mp_zero_and_boosts_attack_by_rarity(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 10
        g.player_max_mp = 12
        g.player_mp = 7
        g.inventory = [("Rare", "Berserker's club")]
        enemy = Entity(3, 2, hp=20, atk=1, defense=0)
        g.enemies = [enemy]

        g.use_item()

        self.assertEqual(g.player_max_mp, 0)
        self.assertEqual(g.player_mp, 0)
        g.take_turn("d")
        self.assertEqual(enemy.hp, 5)

    def test_removing_berserkers_club_restores_mp_pool(self):
        g = Game(seed=1)
        g.player_max_mp = 8
        g.player_mp = 6

        g.equip_accessory("Common", "Berserker's club")
        g.equip_accessory("Common", "Lucky amulet")

        self.assertEqual(g.player_max_mp, 8)
        self.assertEqual(g.player_mp, 6)
        self.assertEqual(g.equipped_accessory, ("Common", "Lucky amulet"))

    def test_item_drop_accessory_pool_includes_berserkers_club(self):
        g = Game(seed=1)

        self.assertIn("Berserker's club", g.ACCESSORY_ITEM_KINDS)

    def test_item_drop_accessory_rate_is_about_one_third_of_consumables(self):
        g = Game(seed=123)
        rolls = 20000
        accessory_count = 0
        consumable_count = 0

        for _ in range(rolls):
            kind = g.random_item_kind()
            if kind in g.ACCESSORY_ITEM_KINDS:
                accessory_count += 1
            elif kind in g.CONSUMABLE_ITEM_KINDS:
                consumable_count += 1

        self.assertGreater(consumable_count, 0)
        ratio = accessory_count / consumable_count
        self.assertAlmostEqual(ratio, 1 / 3, delta=0.05)

    def test_roller_shoes_can_chain_two_steps(self):
        g = Game(seed=1, width=7, height=7)
        g.board = [[WALL for _ in range(7)] for _ in range(7)]
        for y in range(1, 6):
            for x in range(1, 6):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.equip_accessory("Common", "Roller shoes")

        g.take_turn("dd")

        self.assertEqual((g.player.x, g.player.y), (4, 2))

    def test_roller_shoes_stops_after_first_attack_in_chain(self):
        g = Game(seed=1, width=8, height=8)
        g.board = [[WALL for _ in range(8)] for _ in range(8)]
        for y in range(1, 7):
            for x in range(1, 7):
                g.board[y][x] = FLOOR
        g.player.x, g.player.y = 2, 2
        g.player.atk = 3
        g.equip_accessory("Legendary", "Roller shoes")
        enemy = Entity(3, 3, hp=2, atk=1, defense=0)
        g.enemies = [enemy]

        g.take_turn("ds")

        self.assertEqual((g.player.x, g.player.y), (3, 2))
        self.assertEqual(len(g.enemies), 0)


if __name__ == "__main__":
    unittest.main()
