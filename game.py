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
MINIBOSS = "M"
BOSS = "B"
ITEM = "I"
STAIRS = ">"
LASER_WARNING = ","


@dataclass
class Entity:
    x: int
    y: int
    hp: int
    atk: int
    defense: int
    kind: str = "normal"


@dataclass
class ItemEntity:
    x: int
    y: int
    kind: str
    rarity: str


@dataclass
class Spell:
    name: str
    rarity: str


class Game:
    ITEM_DAMAGE_RATIOS = {
        "Throwing axe": {
            "Common": 0.20,
            "Uncommon": 0.30,
            "Rare": 0.45,
            "Epic": 0.65,
            "Legendary": 0.80,
        },
        "Bomb": {
            "Common": 0.10,
            "Uncommon": 0.20,
            "Rare": 0.30,
            "Epic": 0.40,
            "Legendary": 0.50,
        },
    }

    def __init__(
        self,
        width: int = 10,
        height: int = 10,
        seed: Optional[int] = None,
        difficulty: str = "Normal",
    ):
        self.base_width = width
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        self.difficulty = difficulty
        self.enemy_power_multiplier = {
            "Easy": 0.5,
            "Normal": 1.0,
            "Hard": 1.5,
            "Lunatic": 2.0,
        }.get(difficulty, 1.0)
        self.enemy_attack_boost = 2.0
        self.floor = 1
        self.moves = 0
        self.message_log: deque[str] = deque(maxlen=7)
        self.inventory: List[Tuple[str, str]] = []
        self.player = Entity(0, 0, hp=10, atk=3, defense=1)
        self.player_max_hp = 10
        self.player_max_mp = 5
        self.player_mp = 5

        self.level = 1
        self.xp = 0
        self.next_level_xp = 10
        self.skill_points = 0
        self.spells: List[Spell] = []
        self.pending_chant_spell: Optional[Spell] = None

        self.skill_tree = {
            "vitality": 0,
            "strength": 0,
            "guard": 0,
            "arcane": 0,
        }

        self.board: List[List[str]] = []
        self.enemies: List[Entity] = []
        self.items: List[ItemEntity] = []
        self.stairs: Tuple[int, int] = (0, 0)
        self.boss_laser_targets: List[Tuple[int, int]] = []
        self.boss_enraged = False

        self.generate_floor()

    def current_cycle(self) -> int:
        # 1 cycle = 10 floors. floor 1-10 => cycle 0, 11-20 => cycle 1 ...
        return (self.floor - 1) // 10

    def apply_cycle_growth(self) -> None:
        cycle = self.current_cycle()
        self.width = self.base_width + (cycle * 2)

    @staticmethod
    def is_miniboss_floor(floor: int) -> bool:
        return floor % 10 == 5

    @staticmethod
    def is_boss_floor(floor: int) -> bool:
        return floor % 10 == 0

    @staticmethod
    def rarity_tiers() -> List[Tuple[str, int]]:
        return [
            ("Common", 60),
            ("Uncommon", 30),
            ("Rare", 7),
            ("Epic", 2),
            ("Legendary", 1),
        ]

    @staticmethod
    def help_lines() -> List[str]:
        return [
            "Move Commands: w/a/s/d=move, .=wait, i=inventory, u=use item,",
            "Battle Commands: moving into enemies attacks, t=magic, k=skill,",
            "Skill command: k, then choose v=vitality, s=strength, g=guard, a=arcane",
            "System Commands: h=help",
            "Icons: #=wall, .=floor, ,=boss laser warning, @=you, E=enemy, M=miniboss, B=boss, I=item, >=stairs",
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
            if (x, y) == self.stairs:
                continue
            return x, y
        raise RuntimeError("Could not find an empty tile")

    def carve_paths(self) -> None:
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
        self.apply_cycle_growth()
        self.boss_laser_targets = []
        self.boss_enraged = False
        while True:
            self.board = [[WALL for _ in range(self.width)] for _ in range(self.height)]
            self.enemies = []
            self.items = []
            self.carve_paths()

            self.player.x, self.player.y = self.random_floor_only()
            self.stairs = self.random_floor_only(exclude={(self.player.x, self.player.y)})

            if self.is_reachable((self.player.x, self.player.y), self.stairs):
                break

        cycle = self.current_cycle()
        enemy_count = min(2 + self.floor + cycle, 12)
        enemy_hp = int((4 + (self.floor * 2) + (cycle * 4)) * self.enemy_power_multiplier)
        enemy_atk = int(
            (2 + (self.floor // 3) + (cycle * 2) + (self.floor // 2))
            * self.enemy_power_multiplier
            * self.enemy_attack_boost
        )
        enemy_def = int(((self.floor // 4) + cycle) * self.enemy_power_multiplier)
        for _ in range(enemy_count):
            ex, ey = self.random_empty_tile()
            self.enemies.append(
                Entity(
                    ex,
                    ey,
                    hp=enemy_hp,
                    atk=enemy_atk,
                    defense=enemy_def,
                )
            )

        if self.is_miniboss_floor(self.floor):
            bx, by = self.random_empty_tile()
            self.enemies.append(
                Entity(
                    bx,
                    by,
                    hp=16 + (self.floor * 2) + (cycle * 6),
                    atk=max(
                        1,
                        int(
                            (6 + (self.floor // 2) + (cycle * 2))
                            * self.enemy_power_multiplier
                            * self.enemy_attack_boost
                        ),
                    ),
                    defense=max(0, int((3 + (self.floor // 4) + cycle) * self.enemy_power_multiplier)),
                    kind="miniboss",
                )
            )
            self.log("A miniboss lurks on this floor. Defeat it to unlock the stairs.")
        elif self.is_boss_floor(self.floor):
            bx, by = self.random_empty_tile()
            self.enemies.append(
                Entity(
                    bx,
                    by,
                    hp=max(1, int((30 + (self.floor * 3) + (cycle * 8)) * self.enemy_power_multiplier)),
                    atk=max(
                        1,
                        int(
                            (9 + (self.floor // 2) + (cycle * 3))
                            * self.enemy_power_multiplier
                            * self.enemy_attack_boost
                        ),
                    ),
                    defense=max(0, int((5 + (self.floor // 4) + cycle) * self.enemy_power_multiplier)),
                    kind="boss",
                )
            )
            self.log("The Great Boss awaits. Defeat it to unlock the stairs.")

        item_pool = ["Potion", "Power", "Shield", "Ether", "Throwing axe", "Bomb"]
        item_count = min(1 + self.floor // 2, 4)
        for _ in range(item_count):
            ix, iy = self.random_empty_tile()
            self.items.append(ItemEntity(ix, iy, self.rng.choice(item_pool), self.roll_item_rarity()))

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

        for tx, ty in self.boss_laser_targets:
            if 0 <= tx < self.width and 0 <= ty < self.height and temp[ty][tx] == FLOOR:
                temp[ty][tx] = LASER_WARNING

        sx, sy = self.stairs
        temp[sy][sx] = STAIRS

        for i in self.items:
            temp[i.y][i.x] = ITEM
        for e in self.enemies:
            if e.kind == "miniboss":
                temp[e.y][e.x] = MINIBOSS
            elif e.kind == "boss":
                temp[e.y][e.x] = BOSS
            else:
                temp[e.y][e.x] = ENEMY
        temp[self.player.y][self.player.x] = PLAYER

        return "\n".join("".join(row) for row in temp)

    def status_line(self) -> str:
        return " | ".join(self.status_lines())

    def status_lines(self) -> List[str]:
        return [
            f"Floor: {self.floor}  Moves: {self.moves}",
            f"HP: {self.player.hp}/{self.player_max_hp}  MP: {self.player_mp}/{self.player_max_mp}  SP: {self.skill_points}",
            f"Lv: {self.level}  XP: {self.xp}/{self.next_level_xp}  ATK: {self.player.atk}  DEF: {self.player.defense}",
        ]

    def roll_item_rarity(self) -> str:
        tiers = self.rarity_tiers()
        total_weight = sum(weight for _, weight in tiers)
        pick = self.rng.randint(1, total_weight)
        cumulative = 0
        for rarity, weight in tiers:
            cumulative += weight
            if pick <= cumulative:
                return rarity
        return "Common"

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

    def miniboss_alive(self) -> bool:
        return any(enemy.kind == "miniboss" for enemy in self.enemies)

    def boss_alive(self) -> bool:
        return any(enemy.kind == "boss" for enemy in self.enemies)

    def roll_high_rarity(self) -> str:
        high_tiers = [("Rare", 45), ("Epic", 35), ("Legendary", 20)]
        total_weight = sum(weight for _, weight in high_tiers)
        pick = self.rng.randint(1, total_weight)
        cumulative = 0
        for rarity, weight in high_tiers:
            cumulative += weight
            if pick <= cumulative:
                return rarity
        return "Rare"

    @staticmethod
    def damage(attacker_atk: int, defender_def: int) -> int:
        return max(1, attacker_atk - defender_def)

    def pickup_item(self) -> None:
        item = self.get_item_at(self.player.x, self.player.y)
        if item is None:
            return
        self.items.remove(item)
        self.inventory.append((item.rarity, item.kind))
        self.log(f"You picked up a {item.rarity} {item.kind}.")

    def choose_inventory_index(self) -> Optional[int]:
        if len(self.inventory) == 1:
            return 0

        self.log("Choose item to use:")
        for idx, (rarity, kind) in enumerate(self.inventory, start=1):
            self.log(f"{idx}: {rarity} {kind}")
        choice = input("Use which item [number, other=cancel]: ").strip()
        if not choice.isdigit():
            self.log("Item use cancelled.")
            return None
        item_index = int(choice) - 1
        if not (0 <= item_index < len(self.inventory)):
            self.log("Invalid item choice.")
            return None
        return item_index

    def choose_direction(self, prompt: str) -> Optional[Tuple[int, int, str]]:
        direction_map = {
            "w": (0, -1, "up"),
            "s": (0, 1, "down"),
            "a": (-1, 0, "left"),
            "d": (1, 0, "right"),
        }
        choice = input(prompt).strip().lower()[:1]
        if choice not in direction_map:
            self.log("Direction selection cancelled.")
            return None
        return direction_map[choice]

    def apply_attack_item_damage(self, enemy: Entity, rarity: str, kind: str) -> int:
        ratio = self.ITEM_DAMAGE_RATIOS.get(kind, {}).get(rarity, 0.10)
        dmg = max(1, int(enemy.hp * ratio))
        enemy.hp -= dmg
        if enemy.hp <= 0:
            self.enemies.remove(enemy)
            if enemy.kind == "miniboss":
                self.log("Miniboss defeated! The stairs are now unsealed.")
                chest_kind = self.rng.choice(["Potion", "Power", "Shield", "Ether", "Throwing axe", "Bomb"])
                self.items.append(ItemEntity(enemy.x, enemy.y, chest_kind, self.roll_high_rarity()))
                self.log("A treasure chest drops a high-rarity item.")
                xp_gain = 12 + self.floor
            elif enemy.kind == "boss":
                self.log("Great Boss defeated! The stairs are now unsealed.")
                chest_kind = self.rng.choice(["Potion", "Power", "Shield", "Ether", "Throwing axe", "Bomb"])
                self.items.append(ItemEntity(enemy.x, enemy.y, chest_kind, "Legendary"))
                self.log("A legendary treasure chest drops where the boss fell.")
                self.boss_laser_targets = []
                xp_gain = 24 + self.floor
            else:
                self.log("Enemy defeated.")
                xp_gain = 3 + self.floor
            self.gain_xp(xp_gain)
        return dmg

    def use_item(self) -> None:
        if not self.inventory:
            self.log("Inventory is empty.")
            return

        selected_index = self.choose_inventory_index()
        if selected_index is None:
            return

        rarity, kind = self.inventory.pop(selected_index)
        potion_scaling = {
            "Common": (0.20, 5),
            "Uncommon": (0.40, 10),
            "Rare": (0.60, 15),
            "Epic": (0.80, 20),
            "Legendary": (2.00, 100),
        }
        ether_scaling = {
            "Common": (0.20, 3),
            "Uncommon": (0.40, 6),
            "Rare": (0.60, 12),
            "Epic": (0.80, 24),
            "Legendary": (2.00, 50),
        }
        power_shield_gain = {
            "Common": 1,
            "Uncommon": 2,
            "Rare": 4,
            "Epic": 8,
            "Legendary": 16,
        }

        if kind == "Potion":
            ratio, minimum = potion_scaling.get(rarity, (0.20, 5))
            restore = max(minimum, int(self.player_max_hp * ratio))
            self.player.hp = min(self.player_max_hp, self.player.hp + restore)
            self.log(f"You used {rarity} Potion and restored {restore} HP.")
        elif kind == "Power":
            gain = power_shield_gain.get(rarity, 1)
            self.player.atk += gain
            self.log(f"You used {rarity} Power and gained +{gain} ATK.")
        elif kind == "Shield":
            gain = power_shield_gain.get(rarity, 1)
            self.player.defense += gain
            self.log(f"You used {rarity} Shield and gained +{gain} DEF.")
        elif kind == "Ether":
            ratio, minimum = ether_scaling.get(rarity, (0.20, 3))
            restore = max(minimum, int(self.player_max_mp * ratio))
            self.player_mp = min(self.player_max_mp, self.player_mp + restore)
            self.log(f"You used {rarity} Ether and restored {restore} MP.")
        elif kind == "Throwing axe":
            direction = self.choose_direction("Throw direction [w/a/s/d, other=cancel]: ")
            if direction is None:
                self.inventory.insert(selected_index, (rarity, kind))
                return
            dx, dy, dir_label = direction
            x, y = self.player.x + dx, self.player.y + dy
            while 0 <= x < self.width and 0 <= y < self.height and self.board[y][x] != WALL:
                enemy = self.get_enemy_at(x, y)
                if enemy:
                    dmg = self.apply_attack_item_damage(enemy, rarity, "Throwing axe")
                    self.log(f"You threw a {rarity} Throwing axe {dir_label}, dealing {dmg} damage.")
                    return
                x += dx
                y += dy
            self.log("No enemy in the selected line for Throwing axe.")
        elif kind == "Bomb":
            if not self.enemies:
                self.log("No enemies on this floor. Bomb had no effect.")
                return
            total_dmg = 0
            for enemy in list(self.enemies):
                total_dmg += self.apply_attack_item_damage(enemy, rarity, "Bomb")
            self.log(f"You used {rarity} Bomb and dealt {total_dmg} total damage to all enemies.")

    def gain_xp(self, amount: int) -> None:
        self.xp += amount
        self.log(f"You gained {amount} XP.")
        while self.xp >= self.next_level_xp:
            self.xp -= self.next_level_xp
            self.level_up()

    def _stat_growth(self, low: int, high: int) -> int:
        chance = min(0.35 + (self.level * 0.05), 0.95)
        gain = 0
        for _ in range(low):
            gain += 1
        for _ in range(high - low):
            if self.rng.random() < chance:
                gain += 1
        return max(0, gain)

    def level_up(self) -> None:
        self.level += 1
        hp_gain = self._stat_growth(1, 2)
        mp_gain = self._stat_growth(0, 1)
        atk_gain = self._stat_growth(0, 1)
        def_gain = self._stat_growth(0, 1)

        self.player_max_hp += hp_gain
        self.player_max_mp += mp_gain
        self.player.atk += atk_gain
        self.player.defense += def_gain
        self.player.hp = self.player_max_hp
        self.player_mp = self.player_max_mp
        self.skill_points += 1

        self.next_level_xp = int(self.next_level_xp * 1.35)
        self.log(
            f"Level up! Lv {self.level} (+HP {hp_gain}, +MP {mp_gain}, +ATK {atk_gain}, +DEF {def_gain}). HP/MP fully restored."
        )
        self.log("You gained 1 skill point.")

    def use_skill_point(self, skill: str) -> bool:
        if self.skill_points <= 0:
            self.log("No skill points available.")
            return False

        if skill == "v":
            self.skill_tree["vitality"] += 1
            self.player_max_hp += 3
            self.player.hp = self.player_max_hp
            self.log("Vitality upgraded: Max HP +3.")
        elif skill == "s":
            self.skill_tree["strength"] += 1
            self.player.atk += 2
            self.log("Strength upgraded: ATK +2.")
        elif skill == "g":
            self.skill_tree["guard"] += 1
            self.player.defense += 2
            self.log("Guard upgraded: DEF +2.")
        elif skill == "a":
            self.skill_tree["arcane"] += 1
            spell = Spell(self.rng.choice(["Comet Missile", "Flare Curtain", "God's Wrath"]), self.roll_item_rarity())
            self.spells.append(spell)
            self.log(f"Arcane upgraded: Learned {spell.rarity} {spell.name}.")
        else:
            self.log("Unknown skill.")
            return False

        self.skill_points -= 1
        return True

    def open_skill_menu(self) -> bool:
        if self.skill_points <= 0:
            self.log("No skill points. Defeat enemies and level up.")
            return False

        self.log(
            f"Skill Tree | SP:{self.skill_points} VIT:{self.skill_tree['vitality']} STR:{self.skill_tree['strength']} "
            f"GRD:{self.skill_tree['guard']} ARC:{self.skill_tree['arcane']}"
        )
        choice = input("Spend point [v/s/g/a, other=cancel]: ").strip().lower()[:1]
        if not choice:
            self.log("Skill upgrade cancelled.")
            return False
        return self.use_skill_point(choice)

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
            if self.is_miniboss_floor(self.floor) and self.miniboss_alive():
                self.log("A mysterious seal blocks the stairs. Defeat the miniboss first.")
                return
            if self.is_boss_floor(self.floor) and self.boss_alive():
                self.log("A tyrant's seal blocks the stairs. Defeat the Great Boss first.")
                return
            self.advance_floor()

    def combat(self, enemy: Entity) -> None:
        dmg = self.damage(self.player.atk, enemy.defense)
        enemy.hp -= dmg
        self.log(f"You hit the enemy for {dmg} damage.")

        if enemy.hp <= 0:
            defeat_x, defeat_y = enemy.x, enemy.y
            self.enemies.remove(enemy)
            if enemy.kind == "miniboss":
                self.log("Miniboss defeated! The stairs are now unsealed.")
                chest_kind = self.rng.choice(["Potion", "Power", "Shield", "Ether", "Throwing axe", "Bomb"])
                self.items.append(ItemEntity(defeat_x, defeat_y, chest_kind, self.roll_high_rarity()))
                self.log("A treasure chest drops a high-rarity item.")
                xp_gain = 12 + self.floor
            elif enemy.kind == "boss":
                self.log("Great Boss defeated! The stairs are now unsealed.")
                chest_kind = self.rng.choice(["Potion", "Power", "Shield", "Ether", "Throwing axe", "Bomb"])
                self.items.append(ItemEntity(defeat_x, defeat_y, chest_kind, "Legendary"))
                self.log("A legendary treasure chest drops where the boss fell.")
                self.boss_laser_targets = []
                xp_gain = 24 + self.floor
            else:
                self.log("Enemy defeated.")
                xp_gain = 3 + self.floor
            self.gain_xp(xp_gain)
            return

    def spell_power_multiplier(self, rarity: str) -> float:
        return {
            "Common": 1.00,
            "Uncommon": 1.33,
            "Rare": 1.66,
            "Epic": 2.25,
            "Legendary": 3.00,
        }.get(rarity, 1.0)

    def spell_mp_bonus(self, rarity: str) -> int:
        return {
            "Common": 0,
            "Uncommon": 1,
            "Rare": 1,
            "Epic": 2,
            "Legendary": 2,
        }.get(rarity, 0)

    def choose_spell(self) -> Optional[Spell]:
        if not self.spells:
            return None
        if len(self.spells) == 1:
            return self.spells[0]
        self.log("Spellbook:")
        for idx, spell in enumerate(self.spells, start=1):
            self.log(f"{idx}: {spell.rarity} {spell.name}")
        choice = input("Cast which spell [number, other=cancel]: ").strip()
        if not choice.isdigit():
            self.log("Spell cast cancelled.")
            return None
        spell_index = int(choice) - 1
        if not (0 <= spell_index < len(self.spells)):
            self.log("Invalid spell choice.")
            return None
        return self.spells[spell_index]

    def use_technique(self) -> bool:
        if not self.spells:
            self.log("Magic locked. Learn Arcane in skill tree.")
            return False

        if self.pending_chant_spell and self.pending_chant_spell.name == "God's Wrath":
            self.pending_chant_spell = None
            return self.cast_gods_wrath(ready=True)

        spell = self.choose_spell()
        if spell is None:
            return False
        if spell.name == "Comet Missile":
            return self.cast_comet_missile(spell)
        if spell.name == "Flare Curtain":
            return self.cast_flare_curtain(spell)
        if spell.name == "God's Wrath":
            self.pending_chant_spell = spell
            self.log(f"You begin chanting {spell.rarity} God's Wrath...")
            return True

        self.log("Unknown spell.")
        return False

    def apply_spell_damage(self, enemy: Entity, dmg: int, spell_label: str) -> None:
        enemy.hp -= dmg
        self.log(f"{spell_label} deals {dmg} damage.")
        if enemy.hp <= 0:
            self.enemies.remove(enemy)
            self.log("Enemy defeated by magic.")
            xp_gain = 3 + self.floor
            self.gain_xp(xp_gain)

    def cast_comet_missile(self, spell: Spell) -> bool:
        base_cost = 2
        mp_cost = base_cost + self.spell_mp_bonus(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False

        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            x, y = self.player.x + dx, self.player.y + dy
            while 0 <= x < self.width and 0 <= y < self.height and self.board[y][x] != WALL:
                enemy = self.get_enemy_at(x, y)
                if enemy:
                    self.player_mp -= mp_cost
                    base = self.damage(self.player.atk, enemy.defense)
                    dmg = max(1, int(base * self.spell_power_multiplier(spell.rarity)))
                    self.apply_spell_damage(enemy, dmg, f"{spell.rarity} Comet Missile")
                    self.log(f"MP -{mp_cost}.")
                    return True
                x += dx
                y += dy

        self.log("No enemy in a straight line for Comet Missile.")
        return False

    def cast_flare_curtain(self, spell: Spell) -> bool:
        base_cost = 3
        mp_cost = base_cost + self.spell_mp_bonus(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False

        targets = []
        for enemy in self.enemies:
            if max(abs(enemy.x - self.player.x), abs(enemy.y - self.player.y)) <= 1:
                targets.append(enemy)
        if not targets:
            self.log("No enemies around you for Flare Curtain.")
            return False

        self.player_mp -= mp_cost
        for enemy in list(targets):
            base = self.damage(self.player.atk, enemy.defense)
            dmg = max(1, int(base * self.spell_power_multiplier(spell.rarity)))
            self.apply_spell_damage(enemy, dmg, f"{spell.rarity} Flare Curtain")
        self.log(f"MP -{mp_cost}.")
        return True

    def cast_gods_wrath(self, ready: bool = False) -> bool:
        spell = next((s for s in reversed(self.spells) if s.name == "God's Wrath"), None)
        if spell is None:
            self.log("You do not know God's Wrath.")
            return False

        base_cost = 4
        mp_cost = base_cost + self.spell_mp_bonus(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False
        if not self.enemies:
            self.log("No target for God's Wrath.")
            return False

        if not ready:
            self.pending_chant_spell = spell
            self.log(f"You begin chanting {spell.rarity} God's Wrath...")
            return True

        target = max(self.enemies, key=lambda e: (e.hp, -abs(e.x - self.player.x) - abs(e.y - self.player.y)))
        self.player_mp -= mp_cost
        base = self.damage(self.player.atk, target.defense)
        dmg = max(1, int(base * 1.5 * self.spell_power_multiplier(spell.rarity)))
        self.apply_spell_damage(target, dmg, f"{spell.rarity} God's Wrath")
        self.log(f"MP -{mp_cost}.")
        return True

    def attack_adjacent(self) -> None:
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            enemy = self.get_enemy_at(self.player.x + dx, self.player.y + dy)
            if enemy:
                self.combat(enemy)
                return
        self.log("No enemy adjacent to attack.")

    def enemy_turn(self) -> None:
        for enemy in list(self.enemies):
            if enemy.kind == "boss":
                self.boss_turn(enemy)
                continue
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

    def boss_turn(self, boss: Entity) -> None:
        if boss.hp < 15 and not self.boss_enraged:
            self.boss_enraged = True
            enraged_hp = 30 + (self.floor * 3) + (self.current_cycle() * 8)
            boss.hp = max(boss.hp, enraged_hp)
            boss.atk += 2
            boss.defense += 1
            self.log("The Great Boss powers up and fully regenerates!")

        if self.boss_laser_targets:
            self.resolve_boss_laser()
            self.boss_laser_targets = []
            return

        action = self.rng.choice(["attack", "summon", "telegraph"])
        if action == "attack":
            self.boss_attack_or_move(boss)
        elif action == "summon":
            summoned = self.summon_boss_minions(2)
            if summoned == 0:
                self.boss_attack_or_move(boss)
            else:
                self.log(f"The Great Boss summons {summoned} elite minions!")
        else:
            self.boss_laser_targets = self.collect_boss_laser_tiles(boss)
            self.log("The Great Boss marks cardinal and diagonal lines for a laser strike!")

    def boss_attack_or_move(self, boss: Entity) -> None:
        if abs(boss.x - self.player.x) + abs(boss.y - self.player.y) == 1:
            dmg = self.damage(boss.atk, self.player.defense)
            self.player.hp -= dmg
            self.log(f"The Great Boss crushes you for {dmg} damage!")
            return

        best = self.step_toward_player(boss)
        if best:
            boss.x, boss.y = best

    def step_toward_player(self, enemy: Entity) -> Optional[Tuple[int, int]]:
        best_tile = None
        best_dist = abs(enemy.x - self.player.x) + abs(enemy.y - self.player.y)
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = enemy.x + dx, enemy.y + dy
            if not (0 <= nx < self.width and 0 <= ny < self.height):
                continue
            if self.board[ny][nx] == WALL or (nx, ny) == (self.player.x, self.player.y):
                continue
            if self.get_enemy_at(nx, ny):
                continue
            dist = abs(nx - self.player.x) + abs(ny - self.player.y)
            if dist < best_dist:
                best_dist = dist
                best_tile = (nx, ny)
        return best_tile

    def summon_boss_minions(self, count: int) -> int:
        candidates = []
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                if self.board[y][x] != FLOOR:
                    continue
                if (x, y) == (self.player.x, self.player.y):
                    continue
                if any(e.x == x and e.y == y for e in self.enemies):
                    continue
                if abs(x - self.player.x) + abs(y - self.player.y) < 2:
                    continue
                candidates.append((x, y))
        self.rng.shuffle(candidates)
        summoned = 0
        cycle = self.current_cycle()
        for x, y in candidates[:count]:
            self.enemies.append(
                Entity(
                    x,
                    y,
                    hp=14 + self.floor + (cycle * 3),
                    atk=max(
                        1,
                        int((6 + (self.floor // 3) + cycle) * self.enemy_power_multiplier * self.enemy_attack_boost),
                    ),
                    defense=3 + (self.floor // 5) + cycle,
                )
            )
            summoned += 1
        return summoned

    def collect_boss_laser_tiles(self, boss: Entity) -> List[Tuple[int, int]]:
        targets: List[Tuple[int, int]] = []
        for dx, dy in [
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
            (-1, -1),
            (1, -1),
            (-1, 1),
            (1, 1),
        ]:
            x, y = boss.x + dx, boss.y + dy
            while 0 <= x < self.width and 0 <= y < self.height and self.board[y][x] != WALL:
                targets.append((x, y))
                x += dx
                y += dy
        return targets

    def resolve_boss_laser(self) -> None:
        if (self.player.x, self.player.y) in self.boss_laser_targets:
            boss = next((e for e in self.enemies if e.kind == "boss"), None)
            base_atk = boss.atk if boss else 14
            dmg = self.damage(base_atk * 3, self.player.defense)
            self.player.hp -= dmg
            self.log(f"The Great Boss's laser blasts you for {dmg} damage!")
        else:
            self.log("The Great Boss fires a devastating laser through the marked lines!")

    def advance_floor(self) -> None:
        previous_cycle = self.current_cycle()
        self.floor += 1
        self.log(f"You descend to floor {self.floor}.")
        if self.current_cycle() > previous_cycle:
            self.log("A new loop begins: enemies are empowered and the map grows wider.")
        self.generate_floor()

    def show_inventory(self) -> None:
        if not self.inventory:
            self.log("Inventory: (empty)")
            return
        self.log("Inventory: " + ", ".join(f"{rarity} {kind}" for rarity, kind in self.inventory))

    def calculate_score(self) -> int:
        rarity_points = {
            "Common": 40,
            "Uncommon": 80,
            "Rare": 140,
            "Epic": 220,
            "Legendary": 320,
        }
        floor_score = max(0, self.floor - 1) * 120
        level_score = max(0, self.level - 1) * 80
        status_score = (
            (self.player_max_hp * 2)
            + (self.player_max_mp * 10)
            + (self.player.atk * 25)
            + (self.player.defense * 25)
            + (sum(self.skill_tree.values()) * 30)
        )
        arcana_score = sum(rarity_points.get(spell.rarity, 0) for spell in self.spells)
        return floor_score + level_score + status_score + arcana_score

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
        elif cmd == "t":
            acted = self.use_technique()
        elif cmd == "i":
            self.show_inventory()
        elif cmd == "u":
            self.use_item()
            acted = True
        elif cmd == "k":
            self.open_skill_menu()
        elif cmd == "h":
            for line in self.help_lines():
                self.log(line)
        else:
            self.log("Invalid command.")

        if acted:
            self.moves += 1
            self.enemy_turn()

        return True

    def won(self) -> bool:
        return False


def _handle_sigint(_sig, _frame):
    print("\nGame interrupted. Goodbye!")
    raise SystemExit(0)


def choose_difficulty() -> str:
    print("\nSelect difficulty:")
    print("1) Easy")
    print("2) Normal")
    print("3) Hard")
    print("4) Lunatic")
    choice = input("Choice [1-4]: ").strip()
    return {"1": "Easy", "2": "Normal", "3": "Hard", "4": "Lunatic"}.get(choice, "Normal")


def show_title_screen() -> Optional[str]:
    difficulty = "Normal"
    while True:
        print("\n==============================")
        print("      CHARACTER ROGUE")
        print("==============================")
        print(f"Difficulty: {difficulty}")
        print("1) Start")
        print("2) Change Difficulty")
        print("3) Quit")
        choice = input("Select [1-3]: ").strip()
        if choice == "1":
            return difficulty
        if choice == "2":
            difficulty = choose_difficulty()
            continue
        if choice == "3":
            return None
        print("Invalid selection.")


def show_game_over_screen(game: Game) -> None:
    score = game.calculate_score()
    print("\n==============================")
    print("          GAME OVER")
    print("==============================")
    print(f"Reached Floor : {game.floor}")
    print(f"Player Level  : {game.level}")
    print(f"Final Status  : HP {game.player_max_hp} / MP {game.player_max_mp} / ATK {game.player.atk} / DEF {game.player.defense}")
    print(f"Arcana Count  : {len(game.spells)}")
    print(f"Score         : {score}")


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)
    difficulty = show_title_screen()
    if difficulty is None:
        print("Goodbye!")
        return
    game = Game(difficulty=difficulty)
    game.log(f"Game started on {difficulty} difficulty.")

    while True:
        print(game.render())
        for line in game.status_lines():
            print(line)
        if game.message_log:
            for line in game.message_log:
                print(line)
        game.message_log.clear()

        if game.player.hp <= 0:
            show_game_over_screen(game)
            break
        cmd = input("Command [w/a/s/d, t, ., i, u, k, h]: ").strip().lower()[:1]
        if not cmd:
            continue
        game.take_turn(cmd)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame interrupted. Goodbye!")
        sys.exit(0)
