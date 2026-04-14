import unittest

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


if __name__ == "__main__":
    unittest.main()
