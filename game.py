import random
import signal
import sys
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple


WALL = "#"
FLOOR = "."
PLAYER = "@"
ENEMY = "E"
ITEM = "I"
STAIRS = ">"


@dataclass
class Entity:
    x: int
    y: int
    hp: int
    atk: int
    defense: int


@dataclass
class ItemEntity:
    x: int
    y: int
    kind: str


class Game:
    def __init__(self, width: int = 10, height: int = 10, seed: Optional[int] = None):
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        self.floor = 1
        self.moves = 0
        self.max_floor = 10
        self.message_log: deque[str] = deque(maxlen=5)
        self.inventory: List[str] = []
        self.player = Entity(0, 0, hp=10, atk=3, defense=1)
        self.player_max_hp = 10

        self.board: List[List[str]] = []
        self.enemies: List[Entity] = []
        self.items: List[ItemEntity] = []
        self.stairs: Tuple[int, int] = (0, 0)

        self.generate_floor()

    @staticmethod
    def help_lines() -> List[str]:
        return [
            "Commands: w/a/s/d=move, f=attack, .=wait, i=inventory, u=use item, h=help, q=quit",
            "Icons: #=wall, .=floor, @=you, E=enemy, I=item, >=stairs",
        ]

    def log(self, msg: str) -> None:
        self.message_log.append(msg)

    def random_empty_tile(self) -> Tuple[int, int]:
        for _ in range(1000):
            x = self.rng.randint(1, self.width - 2)
            y = self.rng.randint(1, self.height - 2)
            if self.board[y][x] != FLOOR:
                continue
            if (x, y) == (self.player.x, self.player.y):
                continue
            if any(e.x == x and e.y == y for e in self.enemies):
                continue
            if any(i.x == x and i.y == y for i in self.items):
                continue
            return x, y
        raise RuntimeError("Could not find an empty tile")

    def carve_paths(self) -> None:
        # random-walk style carving
        x = self.rng.randint(1, self.width - 2)
        y = self.rng.randint(1, self.height - 2)
        self.board[y][x] = FLOOR
        target_floor_tiles = max((self.width * self.height) // 2, 25)
        carved = 1
        while carved < target_floor_tiles:
            dx, dy = self.rng.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
            x = min(max(1, x + dx), self.width - 2)
            y = min(max(1, y + dy), self.height - 2)
            if self.board[y][x] == WALL:
                self.board[y][x] = FLOOR
                carved += 1

    def is_reachable(self, start: Tuple[int, int], goal: Tuple[int, int]) -> bool:
        q = deque([start])
        visited = {start}
        while q:
            cx, cy = q.popleft()
            if (cx, cy) == goal:
                return True
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if (nx, ny) in visited:
                    continue
                if self.board[ny][nx] == WALL:
                    continue
                visited.add((nx, ny))
                q.append((nx, ny))
        return False

    def generate_floor(self) -> None:
        while True:
            self.board = [[WALL for _ in range(self.width)] for _ in range(self.height)]
            self.enemies = []
            self.items = []
            self.carve_paths()

            self.player.x, self.player.y = self.random_floor_only()
            self.stairs = self.random_floor_only(exclude={(self.player.x, self.player.y)})

            if self.is_reachable((self.player.x, self.player.y), self.stairs):
                break

        enemy_count = min(2 + self.floor, 8)
        for _ in range(enemy_count):
            ex, ey = self.random_empty_tile()
            self.enemies.append(Entity(ex, ey, hp=3 + self.floor, atk=2 + self.floor // 2, defense=0 + self.floor // 3))

        item_pool = ["Potion", "Power", "Shield"]
        item_count = min(1 + self.floor // 2, 4)
        for _ in range(item_count):
            ix, iy = self.random_empty_tile()
            self.items.append(ItemEntity(ix, iy, self.rng.choice(item_pool)))

    def random_floor_only(self, exclude: Optional[set] = None) -> Tuple[int, int]:
        exclude = exclude or set()
        floors = [
            (x, y)
            for y in range(1, self.height - 1)
            for x in range(1, self.width - 1)
            if self.board[y][x] == FLOOR and (x, y) not in exclude
        ]
        if not floors:
            raise RuntimeError("No floor tiles generated")
        return self.rng.choice(floors)

    def render(self) -> str:
        temp = [row[:] for row in self.board]
        sx, sy = self.stairs
        temp[sy][sx] = STAIRS

        for i in self.items:
            temp[i.y][i.x] = ITEM
        for e in self.enemies:
            temp[e.y][e.x] = ENEMY
        temp[self.player.y][self.player.x] = PLAYER

        return "\n".join("".join(row) for row in temp)

    def status_line(self) -> str:
        return (
            f"HP: {self.player.hp}/{self.player_max_hp}  "
            f"ATK: {self.player.atk}  DEF: {self.player.defense}  "
            f"Floor: {self.floor}  Moves: {self.moves}"
        )

    def get_enemy_at(self, x: int, y: int) -> Optional[Entity]:
        for e in self.enemies:
            if e.x == x and e.y == y:
                return e
        return None

    def get_item_at(self, x: int, y: int) -> Optional[ItemEntity]:
        for it in self.items:
            if it.x == x and it.y == y:
                return it
        return None

    @staticmethod
    def damage(attacker_atk: int, defender_def: int) -> int:
        return max(1, attacker_atk - defender_def)

    def pickup_item(self) -> None:
        item = self.get_item_at(self.player.x, self.player.y)
        if item is None:
            return
        self.items.remove(item)
        self.inventory.append(item.kind)
        self.log(f"You picked up a {item.kind}.")

    def use_item(self) -> None:
        if not self.inventory:
            self.log("Inventory is empty.")
            return

        item = self.inventory.pop(0)
        if item == "Potion":
            self.player.hp = min(self.player_max_hp, self.player.hp + 5)
            self.log("You used Potion and restored 5 HP.")
        elif item == "Power":
            self.player.atk += 1
            self.log("You used Power and gained +1 ATK.")
        elif item == "Shield":
            self.player.defense += 1
            self.log("You used Shield and gained +1 DEF.")

    def move_player(self, dx: int, dy: int) -> None:
        nx, ny = self.player.x + dx, self.player.y + dy
        if not (0 <= nx < self.width and 0 <= ny < self.height):
            self.log("You bump into the edge.")
            return

        if self.board[ny][nx] == WALL:
            self.log("A wall blocks your path.")
            return

        enemy = self.get_enemy_at(nx, ny)
        if enemy:
            self.combat(enemy)
            return

        self.player.x, self.player.y = nx, ny
        self.pickup_item()

        if (nx, ny) == self.stairs:
            self.advance_floor()

    def combat(self, enemy: Entity) -> None:
        dmg = self.damage(self.player.atk, enemy.defense)
        enemy.hp -= dmg
        self.log(f"You hit the enemy for {dmg} damage.")

        if enemy.hp <= 0:
            self.enemies.remove(enemy)
            self.log("Enemy defeated.")
            return

        retaliation = self.damage(enemy.atk, self.player.defense)
        self.player.hp -= retaliation
        self.log(f"Enemy hits you for {retaliation} damage.")

    def attack_adjacent(self) -> None:
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            enemy = self.get_enemy_at(self.player.x + dx, self.player.y + dy)
            if enemy:
                self.combat(enemy)
                return
        self.log("No enemy adjacent to attack.")

    def enemy_turn(self) -> None:
        for enemy in list(self.enemies):
            if abs(enemy.x - self.player.x) + abs(enemy.y - self.player.y) == 1:
                dmg = self.damage(enemy.atk, self.player.defense)
                self.player.hp -= dmg
                self.log(f"Enemy hits you for {dmg} damage.")
                continue

            dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
            self.rng.shuffle(dirs)
            for dx, dy in dirs:
                nx, ny = enemy.x + dx, enemy.y + dy
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if self.board[ny][nx] == WALL:
                    continue
                if (nx, ny) == (self.player.x, self.player.y):
                    continue
                if self.get_enemy_at(nx, ny):
                    continue
                enemy.x, enemy.y = nx, ny
                break

    def advance_floor(self) -> None:
        self.floor += 1
        if self.floor > self.max_floor:
            return
        self.log(f"You descend to floor {self.floor}.")
        self.generate_floor()

    def show_inventory(self) -> None:
        if not self.inventory:
            self.log("Inventory: (empty)")
            return
        self.log("Inventory: " + ", ".join(self.inventory))

    def take_turn(self, cmd: str) -> bool:
        acted = False
        if cmd == "w":
            self.move_player(0, -1)
            acted = True
        elif cmd == "s":
            self.move_player(0, 1)
            acted = True
        elif cmd == "a":
            self.move_player(-1, 0)
            acted = True
        elif cmd == "d":
            self.move_player(1, 0)
            acted = True
        elif cmd == ".":
            self.log("You wait.")
            acted = True
        elif cmd == "f":
            self.attack_adjacent()
            acted = True
        elif cmd == "i":
            self.show_inventory()
        elif cmd == "u":
            self.use_item()
            acted = True
        elif cmd == "h":
            for line in self.help_lines():
                self.log(line)
        elif cmd == "q":
            return False
        else:
            self.log("Invalid command.")

        if acted and self.floor <= self.max_floor:
            self.moves += 1
            self.enemy_turn()

        return True

    def won(self) -> bool:
        return self.floor > self.max_floor



def _handle_sigint(_sig, _frame):
    print("\nGame interrupted. Goodbye!")
    raise SystemExit(0)


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)
    game = Game()

    while True:
        print(game.render())
        print(game.status_line())
        if game.message_log:
            for line in game.message_log:
                print(line)
        game.message_log.clear()

        if game.player.hp <= 0:
            print("You died. Game Over.")
            break
        if game.won():
            print("You reached floor 10 and escaped. Victory!")
            break

        cmd = input("Command [w/a/s/d, f, ., i, u, h, q]: ").strip().lower()[:1]
        if not cmd:
            continue
        if not game.take_turn(cmd):
            print("You quit the game.")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame interrupted. Goodbye!")
        sys.exit(0)
