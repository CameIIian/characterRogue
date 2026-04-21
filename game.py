import random
import signal
import sys
import math
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple


WALL = "#"
FLOOR = "."
PLAYER = "@"
ENEMY = "E"
FORTIFIED_ENEMY = "e"
MINIBOSS = "M"
BOSS = "B"
ITEM = "I"
STAIRS = ">"
FRIENDLY = "F"
LASER_WARNING = ","
FRIENDLY_SYMBOL_BY_ROLE = {
    "merchant": "$",
    "technician": "$",
    "friendly demon": "%",
    "maze traveler": "?",
}


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


@dataclass
class FriendlyEntity:
    x: int
    y: int
    role: str = "merchant"
    traded: bool = False


class Game:
    CONSUMABLE_ITEM_KINDS = [
        "Potion",
        "Power",
        "Shield",
        "Ether",
        "Throwing axe",
        "Bomb",
    ]
    ACCESSORY_ITEM_KINDS = [
        "Lucky amulet",
        "Kote",
        "Vampire's Fang",
        "Dark Wizard's Staff",
        "Guardian's Armor",
        "Berserker's club",
        "Roller shoes",
        "Gunpowder box",
    ]
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
    ACCESSORY_KINDS = {
        "Lucky amulet",
        "Kote",
        "Vampire's Fang",
        "Dark Wizard's Staff",
        "Guardian's Armor",
        "Berserker's club",
        "Roller shoes",
        "Gunpowder box",
    }
    XP_MULTIPLIER_BY_RARITY = {
        "Common": 1.10,
        "Uncommon": 1.20,
        "Rare": 1.35,
        "Epic": 1.55,
        "Legendary": 1.80,
    }
    KOTE_BONUS_BY_RARITY = {
        "Common": (1, 1),
        "Uncommon": (2, 2),
        "Rare": (3, 3),
        "Epic": (5, 5),
        "Legendary": (8, 8),
    }
    OVERFLOW_CONVERSION_BY_RARITY = {
        "Common": 0.20,
        "Uncommon": 0.40,
        "Rare": 0.60,
        "Epic": 0.80,
        "Legendary": 1.00,
    }
    RARITY_RANK = {
        "Common": 0,
        "Uncommon": 1,
        "Rare": 2,
        "Epic": 3,
        "Legendary": 4,
    }
    GUARDIAN_ARMOR_MULTIPLIER_BY_RARITY = {
        "Common": 1.15,
        "Uncommon": 1.25,
        "Rare": 1.35,
        "Epic": 1.50,
        "Legendary": 1.75,
    }
    BERSERKER_ATK_MULTIPLIER_BY_RARITY = {
        "Common": 1.20,
        "Uncommon": 1.35,
        "Rare": 1.50,
        "Epic": 1.75,
        "Legendary": 2.00,
    }
    ROLLER_SHOES_STEP_LIMIT_BY_RARITY = {
        "Common": 2,
        "Uncommon": 3,
        "Rare": 5,
        "Epic": 7,
        "Legendary": 10,
    }
    GUNPOWDER_BOX_RATIO_BY_RARITY = {
        "Common": 0.50,
        "Uncommon": 0.75,
        "Rare": 1.00,
        "Epic": 1.25,
        "Legendary": 1.75,
    }
    ACCESSORY_DESCRIPTIONS = {
        "Lucky amulet": "Boosts gained XP based on rarity.",
        "Kote": "Raises ATK and DEF while equipped.",
        "Vampire's Fang": "Converts overheal HP into MP.",
        "Dark Wizard's Staff": "Converts over-restored MP into HP.",
        "Guardian's Armor": "Waiting stacks DEF, while moving resets DEF to base.",
        "Berserker's club": "Sets max MP to 0 while equipped and multiplies ATK by rarity.",
        "Roller shoes": "Allows chaining up to N movement inputs in one turn based on rarity.",
        "Gunpowder box": "On attack/arcana kill, spreads overflow damage to adjacent enemies and can chain.",
    }
    ARCANA_DESCRIPTIONS = {
        "Comet Missile": "Fires a line attack at one directional target.",
        "Flare Curtain": "Hits every enemy adjacent to you.",
        "God's Wrath": "Consumes MP to stack charges that empower your next normal attack.",
        "Healing": "Consumes MP to restore your HP.",
        "Vampire Kiss": "Damages one adjacent enemy and drains HP.",
        "Frugal soul": "Your next item may be preserved instead of consumed.",
    }


    FRIENDLY_ROLE_SPAWN_WEIGHTS = {
        "merchant": 10,
        "technician": 10,
        "maze traveler": 2,
        "friendly demon": 2,
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
        self.turn_logs: deque[str] = deque(maxlen=10)
        self._turn_event_buffer: List[str] = []
        self._is_capturing_turn_events = False
        self.inventory: List[Tuple[str, str]] = []
        self.equipped_accessory: Optional[Tuple[str, str]] = None
        self.player = Entity(0, 0, hp=10, atk=3, defense=1)
        self.guardian_armor_base_defense: Optional[int] = None
        self.guardian_armor_multiplier: float = 1.0
        self.berserker_stored_max_mp: Optional[int] = None
        self.berserker_stored_mp: Optional[int] = None
        self.player_max_hp = 10
        self.player_max_mp = 5
        self.player_mp = 5

        self.level = 1
        self.xp = 0
        self.next_level_xp = 10
        self.skill_points = 0
        self.spells: List[Spell] = []
        self.pending_chant_spell: Optional[Spell] = None
        self.gods_wrath_charge_count = 0
        self.gods_wrath_charge_multiplier = 1.0
        self.next_floor_destination: Optional[int] = None
        self.active_floor_event: Optional[str] = None
        self.friendly_spawn_cycle_index = self.current_cycle()
        self.spawned_friendly_roles_in_cycle: set[str] = set()
        self.fortified_spawn_cycle_index = self.current_cycle()
        self.fortified_spawned_in_cycle = False

        self.skill_tree = {
            "vitality": 0,
            "strength": 0,
            "guard": 0,
            "arcane": 0,
        }

        self.board: List[List[str]] = []
        self.enemies: List[Entity] = []
        self.items: List[ItemEntity] = []
        self.friendlies: List[FriendlyEntity] = []
        self.stairs: Tuple[int, int] = (0, 0)
        self.boss_laser_targets: List[Tuple[int, int]] = []
        self.boss_enraged = False
        self.floor_clear_bonus_granted = False
        self.next_item_preserve_chance: Optional[float] = None

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
            "Move Commands: w/a/s/d=move, .=wait, i=inventory, u=use item (u 3=use slot 3),",
            "Battle Commands: moving into enemies attacks, t=magic, k=skill,",
            "Skill command: k, then choose v=vitality, s=strength, g=guard, a=arcane (or use kv/ks/kg/ka, k v etc.)",
            "System Commands: h=help, l=turn log, p=status details",
            "Icons: #=wall, .=floor, ,=boss laser warning, @=you, E=enemy, e=fortified, M=miniboss, B=boss, I=item, $=merchant/technician, %=friendly demon, ?=maze traveler, >=stairs",
        ]

    def log(self, msg: str) -> None:
        self.message_log.append(msg)
        if self._is_capturing_turn_events:
            self._turn_event_buffer.append(msg)

    def start_turn_capture(self) -> None:
        self._turn_event_buffer = []
        self._is_capturing_turn_events = True

    def finalize_turn_capture(self, cmd: str) -> None:
        self._is_capturing_turn_events = False
        if cmd and all(ch in {"w", "a", "s", "d"} for ch in cmd) and not self._turn_event_buffer:
            return
        if not self._turn_event_buffer:
            return
        self.turn_logs.append(" / ".join(self._turn_event_buffer))

    def show_turn_logs(self) -> None:
        if not self.turn_logs:
            self.log("Turn log: (empty)")
            return
        self.log("Turn log (oldest -> newest):")
        for idx, entry in enumerate(self.turn_logs, start=1):
            self.log(f"{idx}: {entry}")

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
            if any(f.x == x and f.y == y for f in self.friendlies):
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
        self.roll_floor_event()
        while True:
            self.board = [[WALL for _ in range(self.width)] for _ in range(self.height)]
            self.enemies = []
            self.items = []
            self.friendlies = []
            self.carve_paths()

            self.player.x, self.player.y = self.random_floor_only()
            self.stairs = self.random_floor_only(exclude={(self.player.x, self.player.y)})

            if self.is_reachable((self.player.x, self.player.y), self.stairs):
                break

        cycle = self.current_cycle()
        enemy_count = min(2 + self.floor + cycle, 12)
        if self.active_floor_event == "trap":
            enemy_count = max(enemy_count, int(math.ceil(enemy_count * 1.5)))
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
                    hp=max(1, int((45 + (self.floor * 4) + (cycle * 12)) * self.enemy_power_multiplier)),
                    atk=max(
                        1,
                        int(
                            (9 + (self.floor // 2) + (cycle * 3))
                            * self.enemy_power_multiplier
                            * self.enemy_attack_boost
                        ),
                    ),
                    defense=max(0, int((8 + (self.floor // 3) + (cycle * 2)) * self.enemy_power_multiplier)),
                    kind="boss",
                )
            )
            self.log("The Great Boss awaits. Defeat it to unlock the stairs.")
        self.maybe_spawn_fortified_enemy(enemy_atk)

        item_count = min(1 + self.floor // 2, 4)
        if self.active_floor_event == "trap":
            item_count = max(item_count, int(math.ceil(item_count * 1.5)))
        self.floor_clear_bonus_granted = False
        for _ in range(item_count):
            ix, iy = self.random_empty_tile()
            self.items.append(ItemEntity(ix, iy, self.random_item_kind(), self.roll_item_rarity()))
        self.maybe_spawn_friendly()

    def roll_floor_event(self) -> None:
        self.active_floor_event = None
        roll = self.rng.random()
        if roll < 0.02:
            self.active_floor_event = "lucky_day"
            self.log("Random Event - Lucky Day! XP gained on this floor is doubled.")
            return
        if roll < 0.03:
            self.active_floor_event = "full_moon_night"
            self.log("Random Event - Full Moon Night! At turn start, HP/MP recover by 5%.")
            return
        if roll < 0.04:
            self.active_floor_event = "trap"
            self.log("Random Event - TRAP! Enemy and item counts are multiplied by 1.5x.")

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
        for f in self.friendlies:
            temp[f.y][f.x] = FRIENDLY_SYMBOL_BY_ROLE.get(f.role, FRIENDLY)
        for e in self.enemies:
            if e.kind == "miniboss":
                temp[e.y][e.x] = MINIBOSS
            elif e.kind == "boss":
                temp[e.y][e.x] = BOSS
            elif e.kind == "fortified":
                temp[e.y][e.x] = FORTIFIED_ENEMY
            else:
                temp[e.y][e.x] = ENEMY
        temp[self.player.y][self.player.x] = PLAYER

        return "\n".join("".join(row) for row in temp)

    def status_line(self) -> str:
        return " | ".join(self.status_lines())

    def status_lines(self) -> List[str]:
        accessory_text = (
            f"Accessory: {self.equipped_accessory[0]} {self.equipped_accessory[1]}"
            if self.equipped_accessory
            else "Accessory: None"
        )
        return [
            f"Floor: {self.floor}  Moves: {self.moves}",
            f"HP: {self.player.hp}/{self.player_max_hp}  MP: {self.player_mp}/{self.player_max_mp}  SP: {self.skill_points}",
            f"Lv: {self.level}  XP: {self.xp}/{self.next_level_xp}  ATK: {self.player.atk}  DEF: {self.player.defense}  {accessory_text}",
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


    def random_item_kind(self) -> str:
        # Accessories should appear around one-third as often as consumables
        # when rolling from generic item drops.
        roll = self.rng.randint(1, 4)
        if roll <= 3:
            return self.rng.choice(self.CONSUMABLE_ITEM_KINDS)
        return self.rng.choice(self.ACCESSORY_ITEM_KINDS)

    def is_guardian_armor_equipped(self) -> bool:
        return self.equipped_accessory is not None and self.equipped_accessory[1] == "Guardian's Armor"

    def refresh_guardian_armor_defense(self) -> None:
        if self.guardian_armor_base_defense is None:
            return
        self.player.defense = max(0, int(self.guardian_armor_base_defense * self.guardian_armor_multiplier))

    def add_player_defense(self, amount: int) -> None:
        if amount == 0:
            return
        if self.is_guardian_armor_equipped() and self.guardian_armor_base_defense is not None:
            self.guardian_armor_base_defense = max(0, self.guardian_armor_base_defense + amount)
            self.refresh_guardian_armor_defense()
            return
        self.player.defense = max(0, self.player.defense + amount)

    def reset_guardian_armor_defense(self) -> None:
        if not self.is_guardian_armor_equipped() or self.guardian_armor_base_defense is None:
            return
        self.guardian_armor_multiplier = 1.0
        self.refresh_guardian_armor_defense()
        self.log("Guardian's Armor reset: DEF returned to base after moving.")

    def stack_guardian_armor_defense(self) -> None:
        if not self.is_guardian_armor_equipped() or self.guardian_armor_base_defense is None:
            return
        rarity, _ = self.equipped_accessory
        multiplier = self.GUARDIAN_ARMOR_MULTIPLIER_BY_RARITY.get(rarity, 1.15)
        self.guardian_armor_multiplier *= multiplier
        self.refresh_guardian_armor_defense()
        self.log(
            f"Guardian's Armor activated: DEF scaled by x{multiplier:.2f} (current {self.player.defense})."
        )

    def accessory_overflow_ratio(self, accessory_kind: str, rarity: str) -> float:
        if accessory_kind not in {"Vampire's Fang", "Dark Wizard's Staff"}:
            return 0.0
        return self.OVERFLOW_CONVERSION_BY_RARITY.get(rarity, 0.20)

    @staticmethod
    def _split_restoration(raw_amount: int, current: int, maximum: int) -> Tuple[int, int]:
        if raw_amount <= 0:
            return 0, 0
        effective = min(raw_amount, max(0, maximum - current))
        overflow = raw_amount - effective
        return effective, overflow

    def restore_hp(self, amount: int) -> Tuple[int, int]:
        healed, overflow = self._split_restoration(amount, self.player.hp, self.player_max_hp)
        self.player.hp += healed
        converted_mp = 0
        if (
            overflow > 0
            and self.equipped_accessory is not None
            and self.equipped_accessory[1] == "Vampire's Fang"
        ):
            rarity, kind = self.equipped_accessory
            ratio = self.accessory_overflow_ratio(kind, rarity)
            mp_raw = int(overflow * ratio)
            converted_mp, _ = self._split_restoration(mp_raw, self.player_mp, self.player_max_mp)
            self.player_mp += converted_mp
            if converted_mp > 0:
                self.log(
                    f"{rarity} Vampire's Fang converted {overflow} overflow HP into {converted_mp} MP."
                )
        return healed, converted_mp

    def restore_mp(self, amount: int) -> Tuple[int, int]:
        restored, overflow = self._split_restoration(amount, self.player_mp, self.player_max_mp)
        self.player_mp += restored
        converted_hp = 0
        if (
            overflow > 0
            and self.equipped_accessory is not None
            and self.equipped_accessory[1] == "Dark Wizard's Staff"
        ):
            rarity, kind = self.equipped_accessory
            ratio = self.accessory_overflow_ratio(kind, rarity)
            hp_raw = int(overflow * ratio)
            converted_hp, _ = self._split_restoration(hp_raw, self.player.hp, self.player_max_hp)
            self.player.hp += converted_hp
            if converted_hp > 0:
                self.log(
                    f"{rarity} Dark Wizard's Staff converted {overflow} overflow MP into {converted_hp} HP."
                )
        return restored, converted_hp

    def apply_accessory_effect(self, rarity: str, kind: str) -> None:
        if kind == "Kote":
            atk_bonus, def_bonus = self.KOTE_BONUS_BY_RARITY.get(rarity, (1, 1))
            self.player.atk += atk_bonus
            self.add_player_defense(def_bonus)
        elif kind == "Guardian's Armor":
            self.guardian_armor_base_defense = max(0, self.player.defense)
            self.guardian_armor_multiplier = 1.0
            self.refresh_guardian_armor_defense()
        elif kind == "Berserker's club":
            self.berserker_stored_max_mp = self.player_max_mp
            self.berserker_stored_mp = self.player_mp
            self.player_max_mp = 0
            self.player_mp = 0
            multiplier = self.BERSERKER_ATK_MULTIPLIER_BY_RARITY.get(rarity, 1.20)
            self.log(f"Berserker's club active: Max MP set to 0, ATK damage now x{multiplier:.2f}.")

    def remove_accessory_effect(self, rarity: str, kind: str) -> None:
        if kind == "Kote":
            atk_bonus, def_bonus = self.KOTE_BONUS_BY_RARITY.get(rarity, (1, 1))
            self.player.atk = max(1, self.player.atk - atk_bonus)
            self.add_player_defense(-def_bonus)
        elif kind == "Guardian's Armor":
            if self.guardian_armor_base_defense is not None:
                self.player.defense = max(0, self.guardian_armor_base_defense)
            self.guardian_armor_base_defense = None
            self.guardian_armor_multiplier = 1.0
        elif kind == "Berserker's club":
            restored_max_mp = self.berserker_stored_max_mp if self.berserker_stored_max_mp is not None else 5
            restored_mp = self.berserker_stored_mp if self.berserker_stored_mp is not None else 0
            self.player_max_mp = max(0, restored_max_mp)
            self.player_mp = min(self.player_max_mp, max(0, restored_mp))
            self.berserker_stored_max_mp = None
            self.berserker_stored_mp = None

    def equip_accessory(self, rarity: str, kind: str) -> None:
        if self.equipped_accessory is not None:
            equipped_rarity, equipped_kind = self.equipped_accessory
            self.remove_accessory_effect(equipped_rarity, equipped_kind)
            self.inventory.append((equipped_rarity, equipped_kind))
            self.log(f"Removed {equipped_rarity} {equipped_kind} and returned it to inventory.")

        self.equipped_accessory = (rarity, kind)
        self.apply_accessory_effect(rarity, kind)
        self.log(f"Equipped {rarity} {kind}.")

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

    def get_friendly_at(self, x: int, y: int) -> Optional[FriendlyEntity]:
        for friendly in self.friendlies:
            if friendly.x == x and friendly.y == y:
                return friendly
        return None

    def refresh_friendly_spawn_cycle(self) -> None:
        current_cycle = self.current_cycle()
        if self.friendly_spawn_cycle_index != current_cycle:
            self.friendly_spawn_cycle_index = current_cycle
            self.spawned_friendly_roles_in_cycle = set()

    def refresh_fortified_spawn_cycle(self) -> None:
        current_cycle = self.current_cycle()
        if self.fortified_spawn_cycle_index != current_cycle:
            self.fortified_spawn_cycle_index = current_cycle
            self.fortified_spawned_in_cycle = False

    def maybe_spawn_fortified_enemy(self, baseline_atk: int) -> None:
        self.refresh_fortified_spawn_cycle()
        if self.fortified_spawned_in_cycle:
            return
        if self.rng.randint(1, 100) != 1:
            return
        ex, ey = self.random_empty_tile()
        cycle = self.current_cycle()
        self.enemies.append(
            Entity(
                ex,
                ey,
                hp=max(10, 8 + self.floor + (cycle * 3)),
                atk=0,
                defense=max(20, baseline_atk * 3),
                kind="fortified",
            )
        )
        self.fortified_spawned_in_cycle = True
        self.log("A fortified enemy appears. It hardly takes damage but gives massive XP.")

    def maybe_spawn_friendly(self) -> None:
        self.refresh_friendly_spawn_cycle()

        available_roles = [
            role
            for role in self.FRIENDLY_ROLE_SPAWN_WEIGHTS
            if role not in self.spawned_friendly_roles_in_cycle
        ]
        if not available_roles:
            return

        spawn_roll = self.rng.randint(1, 100)
        cumulative = 0
        selected_role: Optional[str] = None
        for role in available_roles:
            cumulative += self.FRIENDLY_ROLE_SPAWN_WEIGHTS[role]
            if spawn_roll <= cumulative:
                selected_role = role
                break

        if selected_role is None:
            return

        fx, fy = self.random_empty_tile()
        self.friendlies.append(FriendlyEntity(fx, fy, role=selected_role))
        self.spawned_friendly_roles_in_cycle.add(selected_role)

    def roll_trade_rarity(self) -> str:
        trade_tiers = [("Common", 25), ("Uncommon", 20), ("Rare", 32), ("Epic", 18), ("Legendary", 5)]
        total_weight = sum(weight for _, weight in trade_tiers)
        pick = self.rng.randint(1, total_weight)
        cumulative = 0
        for rarity, weight in trade_tiers:
            cumulative += weight
            if pick <= cumulative:
                return rarity
        return "Rare"

    def random_arcana(self) -> Spell:
        return Spell(
            self.rng.choice(
                ["Comet Missile", "Flare Curtain", "God's Wrath", "Healing", "Vampire Kiss", "Frugal soul"]
            ),
            self.roll_item_rarity(),
        )

    def random_arcana_with_rarity(self, rarity: str) -> Spell:
        return Spell(
            self.rng.choice(
                ["Comet Missile", "Flare Curtain", "God's Wrath", "Healing", "Vampire Kiss", "Frugal soul"]
            ),
            rarity,
        )

    def roll_trade_rarity_by_offer_count(self, offered_count: int) -> str:
        if offered_count <= 0:
            return "Common"

        trade_tiers_by_offer_count = {
            1: [("Common", 20), ("Uncommon", 30), ("Rare", 30), ("Epic", 15), ("Legendary", 5)],
            2: [("Common", 12), ("Uncommon", 25), ("Rare", 35), ("Epic", 20), ("Legendary", 8)],
            3: [("Common", 8), ("Uncommon", 18), ("Rare", 36), ("Epic", 26), ("Legendary", 12)],
            4: [("Common", 4), ("Uncommon", 12), ("Rare", 34), ("Epic", 32), ("Legendary", 18)],
            5: [("Common", 2), ("Uncommon", 8), ("Rare", 28), ("Epic", 36), ("Legendary", 26)],
        }
        trade_tiers = trade_tiers_by_offer_count[min(5, offered_count)]
        total_weight = sum(weight for _, weight in trade_tiers)
        pick = self.rng.randint(1, total_weight)
        cumulative = 0
        for rarity, weight in trade_tiers:
            cumulative += weight
            if pick <= cumulative:
                return rarity
        return "Rare"

    def trade_with_friendly(self, friendly: FriendlyEntity) -> None:
        if friendly.role == "merchant":
            self.trade_with_merchant(friendly)
            return
        if friendly.role == "technician":
            self.trade_with_technician(friendly)
            return
        if friendly.role == "maze traveler":
            self.trade_with_maze_traveler(friendly)
            return
        if friendly.role == "friendly demon":
            self.trade_with_friendly_demon(friendly)
            return
        self.log("The traveler does not respond.")

    def trade_with_merchant(self, friendly: FriendlyEntity) -> None:
        if friendly.traded:
            self.log("Merchant: We've already traded on this floor.")
            return
        if not self.inventory:
            gift_kind = self.random_item_kind()
            self.inventory.append(("Common", gift_kind))
            friendly.traded = True
            self.log("Merchant: You're empty-handed? I'll invest in your journey this once.")
            self.log(f"Merchant gift: Common {gift_kind}.")
            return
        offered_indices = self.choose_trade_item_indices(max_items=5)
        if offered_indices is None:
            return

        offered_items = [self.inventory[idx] for idx in offered_indices]
        for idx in sorted(offered_indices, reverse=True):
            self.inventory.pop(idx)

        new_kind = self.random_item_kind()
        new_rarity = self.roll_trade_rarity_by_offer_count(len(offered_items))
        self.inventory.append((new_rarity, new_kind))
        friendly.traded = True
        offered_text = ", ".join([f"{rarity} {kind}" for rarity, kind in offered_items])
        self.log(f"Merchant trade ({len(offered_items)} offered): {offered_text} -> {new_rarity} {new_kind}.")

    def trade_with_technician(self, friendly: FriendlyEntity) -> None:
        if friendly.traded:
            self.log("Technician: I already calibrated your gear on this floor.")
            return
        if not self.inventory:
            gift_spell = self.random_arcana_with_rarity("Common")
            self.acquire_arcana(gift_spell)
            friendly.traded = True
            self.log("Technician: No materials? I'll provide a starter Arcana sample.")
            return
        offered_indices = self.choose_trade_item_indices(max_items=5)
        if offered_indices is None:
            return

        offered_items = [self.inventory[idx] for idx in offered_indices]
        for idx in sorted(offered_indices, reverse=True):
            self.inventory.pop(idx)

        trade_rarity = self.roll_trade_rarity_by_offer_count(len(offered_items))
        new_spell = self.random_arcana_with_rarity(trade_rarity)
        offered_text = ", ".join([f"{rarity} {kind}" for rarity, kind in offered_items])
        self.log(
            f"Technician trade ({len(offered_items)} offered): {offered_text} -> {new_spell.rarity} {new_spell.name} Arcana."
        )
        self.acquire_arcana(new_spell)
        friendly.traded = True

    def trade_with_maze_traveler(self, friendly: FriendlyEntity) -> None:
        if friendly.traded:
            self.log("Maze traveler: My route advice was already given.")
            return
        doubled_floor = max(1, self.floor * 2)
        halved_floor = max(1, self.floor // 2)
        destination = self.rng.choice([doubled_floor, halved_floor])
        self.next_floor_destination = destination
        friendly.traded = True
        self.log(f"Maze traveler marks your map. Next stairs will send you to floor {destination}.")

    def trade_with_friendly_demon(self, friendly: FriendlyEntity) -> None:
        if friendly.traded:
            self.log("Friendly demon: We already made our pact on this floor.")
            return
        if self.player.hp <= 1:
            self.log("Friendly demon: Return when you have more than 1 HP to offer.")
            return

        offered_text = input(
            f"Friendly demon pact - offer HP [1-{self.player.hp - 1}, other=cancel]: "
        ).strip()
        if not offered_text.isdigit():
            self.log("Friendly demon pact cancelled.")
            return

        offered_hp = int(offered_text)
        if offered_hp < 1 or offered_hp >= self.player.hp:
            self.log("Friendly demon: Offer must leave you with at least 1 HP.")
            return

        atk_text = input(f"Allocate to ATK [0-{offered_hp}]: ").strip()
        if not atk_text.isdigit():
            self.log("Friendly demon pact cancelled.")
            return

        atk_gain = int(atk_text)
        if atk_gain < 0 or atk_gain > offered_hp:
            self.log("Friendly demon: Invalid ATK allocation.")
            return

        def_gain = offered_hp - atk_gain
        self.player.hp -= offered_hp
        self.player.atk += atk_gain
        self.player.defense += def_gain
        friendly.traded = True
        self.log(
            f"Friendly demon pact complete: HP -{offered_hp}, ATK +{atk_gain}, DEF +{def_gain}."
        )

    def maybe_grant_floor_clear_bonus(self) -> None:
        if self.floor_clear_bonus_granted or self.enemies:
            return
        bonus = 5 + (self.floor * 2)
        self.floor_clear_bonus_granted = True
        self.log(f"Floor clear bonus! +{bonus} XP for clearing floor depth {self.floor}.")
        self.gain_xp(bonus)

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

        print("Choose item to use:")
        for idx, (rarity, kind) in enumerate(self.inventory, start=1):
            print(f"{idx}: {rarity} {kind}")
        choice = input("Use which item [number, other=cancel]: ").strip()
        if not choice.isdigit():
            self.log("Item use cancelled.")
            return None
        item_index = int(choice) - 1
        if not (0 <= item_index < len(self.inventory)):
            self.log("Invalid item choice.")
            return None
        return item_index

    def choose_trade_item_indices(self, max_items: int = 5) -> Optional[List[int]]:
        if not self.inventory:
            return []
        upper_bound = min(max_items, len(self.inventory))
        if upper_bound == 1:
            return [0]

        print("Choose items to offer:")
        for idx, (rarity, kind) in enumerate(self.inventory, start=1):
            print(f"{idx}: {rarity} {kind}")

        offered_count_text = input(f"Offer how many items [1-{upper_bound}, other=cancel]: ").strip()
        if not offered_count_text.isdigit():
            self.log("Trade cancelled.")
            return None
        offered_count = int(offered_count_text)
        if offered_count < 1 or offered_count > upper_bound:
            self.log("Invalid offered item count.")
            return None

        selected_indices: List[int] = []
        for offer_index in range(offered_count):
            choice = input(f"Select offer item {offer_index + 1}/{offered_count} [number, other=cancel]: ").strip()
            if not choice.isdigit():
                self.log("Trade cancelled.")
                return None
            item_index = int(choice) - 1
            if not (0 <= item_index < len(self.inventory)) or item_index in selected_indices:
                self.log("Invalid item choice.")
                return None
            selected_indices.append(item_index)
        return selected_indices

    def find_prioritized_item_index(self) -> Optional[int]:
        for idx, (_, kind) in enumerate(self.inventory):
            if kind in {"Power", "Shield"}:
                return idx

        recovery_kinds = []
        if self.player.hp < self.player_max_hp:
            recovery_kinds.append("Potion")
        if self.player_mp < self.player_max_mp:
            recovery_kinds.append("Ether")
        for idx, (_, kind) in enumerate(self.inventory):
            if kind in recovery_kinds:
                return idx

        equipped_rank = -1
        if self.equipped_accessory:
            equipped_rank = self.RARITY_RANK.get(self.equipped_accessory[0], -1)
        for idx, (rarity, kind) in enumerate(self.inventory):
            if kind in self.ACCESSORY_KINDS and self.RARITY_RANK.get(rarity, -1) > equipped_rank:
                return idx

        return None

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
                chest_kind = self.random_item_kind()
                self.items.append(ItemEntity(enemy.x, enemy.y, chest_kind, self.roll_high_rarity()))
                self.log("A treasure chest drops a high-rarity item.")
                xp_gain = 12 + self.floor
            elif enemy.kind == "boss":
                self.log("Great Boss defeated! The stairs are now unsealed.")
                chest_kind = self.random_item_kind()
                self.items.append(ItemEntity(enemy.x, enemy.y, chest_kind, "Legendary"))
                self.log("A legendary treasure chest drops where the boss fell.")
                self.boss_laser_targets = []
                xp_gain = 24 + self.floor
            else:
                self.log("Enemy defeated.")
                xp_gain = 3 + self.floor
            self.gain_xp(xp_gain)
            self.maybe_grant_floor_clear_bonus()
        return dmg

    def use_item(self, selected_index: Optional[int] = None, auto_select: bool = False) -> bool:
        if not self.inventory:
            self.log("Inventory is empty.")
            return False

        if selected_index is None and auto_select:
            prioritized_index = self.find_prioritized_item_index()
            if prioritized_index is not None:
                selected_index = prioritized_index
        if selected_index is None:
            selected_index = self.choose_inventory_index()
            if selected_index is None:
                return False
        elif not (0 <= selected_index < len(self.inventory)):
            self.log("Invalid item choice.")
            return False

        rarity, kind = self.inventory[selected_index]
        consumed = True
        used_successfully = True
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
            healed, _ = self.restore_hp(restore)
            self.log(f"You used {rarity} Potion and restored {healed} HP.")
        elif kind == "Power":
            gain = power_shield_gain.get(rarity, 1)
            self.player.atk += gain
            self.log(f"You used {rarity} Power and gained +{gain} ATK.")
        elif kind == "Shield":
            gain = power_shield_gain.get(rarity, 1)
            self.add_player_defense(gain)
            self.log(f"You used {rarity} Shield and gained +{gain} DEF.")
        elif kind == "Ether":
            ratio, minimum = ether_scaling.get(rarity, (0.20, 3))
            restore = max(minimum, int(self.player_max_mp * ratio))
            restored, _ = self.restore_mp(restore)
            self.log(f"You used {rarity} Ether and restored {restored} MP.")
        elif kind in self.ACCESSORY_KINDS:
            self.equip_accessory(rarity, kind)
        elif kind == "Throwing axe":
            direction = self.choose_direction("Throw direction [w/a/s/d, other=cancel]: ")
            if direction is None:
                used_successfully = False
            if used_successfully:
                dx, dy, dir_label = direction
                x, y = self.player.x + dx, self.player.y + dy
                while 0 <= x < self.width and 0 <= y < self.height and self.board[y][x] != WALL:
                    enemy = self.get_enemy_at(x, y)
                    if enemy:
                        dmg = self.apply_attack_item_damage(enemy, rarity, "Throwing axe")
                        self.log(f"You threw a {rarity} Throwing axe {dir_label}, dealing {dmg} damage.")
                        break
                    x += dx
                    y += dy
                else:
                    self.log("No enemy in the selected line for Throwing axe.")
        elif kind == "Bomb":
            if not self.enemies:
                self.log("No enemies on this floor. Bomb had no effect.")
                used_successfully = False
            else:
                total_dmg = 0
                for enemy in list(self.enemies):
                    total_dmg += self.apply_attack_item_damage(enemy, rarity, "Bomb")
                self.log(f"You used {rarity} Bomb and dealt {total_dmg} total damage to all enemies.")

        if used_successfully:
            if self.next_item_preserve_chance is not None:
                chance = self.next_item_preserve_chance
                self.next_item_preserve_chance = None
                if self.rng.random() < chance:
                    consumed = False
                    self.log("Frugal soul activated! The item was not consumed.")
                else:
                    self.log("Frugal soul failed to preserve the item.")
            if consumed:
                self.inventory.pop(selected_index)
        return used_successfully

    def gain_xp(self, amount: int) -> None:
        gained = amount
        if self.equipped_accessory and self.equipped_accessory[1] == "Lucky amulet":
            multiplier = self.XP_MULTIPLIER_BY_RARITY.get(self.equipped_accessory[0], 1.10)
            gained = max(1, int(amount * multiplier))
            self.log(
                f"Lucky amulet boosted XP gain: {amount} -> {gained} (x{multiplier:.2f})."
            )
        if self.active_floor_event == "lucky_day":
            boosted = max(1, gained * 2)
            self.log(f"Lucky Day doubles XP gain: {gained} -> {boosted}.")
            gained = boosted
        self.xp += gained
        self.log(f"You gained {gained} XP.")
        while self.xp >= self.next_level_xp:
            self.xp -= self.next_level_xp
            self.level_up()

    def apply_turn_start_effects(self) -> None:
        if self.active_floor_event != "full_moon_night":
            return
        hp_restore = max(1, int(math.ceil(self.player_max_hp * 0.05)))
        mp_restore = 0
        if self.player_max_mp > 0:
            mp_restore = max(1, int(math.ceil(self.player_max_mp * 0.05)))
        healed, _ = self.restore_hp(hp_restore)
        restored, _ = self.restore_mp(mp_restore)
        self.log(f"Full Moon Night restores {healed} HP and {restored} MP at turn start.")

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
        if self.equipped_accessory and self.equipped_accessory[1] == "Berserker's club":
            if self.berserker_stored_max_mp is None:
                self.berserker_stored_max_mp = self.player_max_mp
            self.berserker_stored_max_mp += mp_gain
            self.player_max_mp = 0
            self.player_mp = 0
        else:
            self.player_max_mp += mp_gain
        self.player.atk += atk_gain
        self.add_player_defense(def_gain)
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
            self.add_player_defense(2)
            self.log("Guard upgraded: DEF +2.")
        elif skill == "a":
            self.skill_tree["arcane"] += 1
            spell = Spell(
                self.rng.choice(["Comet Missile", "Flare Curtain", "God's Wrath", "Healing", "Vampire Kiss", "Frugal soul"]),
                self.roll_item_rarity(),
            )
            self.acquire_arcana(spell)
        else:
            self.log("Unknown skill.")
            return False

        self.skill_points -= 1
        return True

    def acquire_arcana(self, spell: Spell) -> None:
        if not self.spells:
            self.spells.append(spell)
            self.log(f"Arcane upgraded: Learned {spell.rarity} {spell.name}.")
            return

        current_spell = self.spells[0]
        self.log(
            f"Current Arcana: {current_spell.rarity} {current_spell.name} | "
            f"New Arcana: {spell.rarity} {spell.name}"
        )
        self.log(
            "You can only hold 1 Arcana. Choose: "
            "1=Keep current, discard new / 2=Take new, remove current."
        )
        choice = input("Arcana choice [1/2, other=1]: ").strip()
        if choice == "2":
            self.spells = [spell]
            self.pending_chant_spell = None
            self.log(
                f"Arcana replaced: {current_spell.rarity} {current_spell.name} -> "
                f"{spell.rarity} {spell.name}."
            )
            return

        self.log(f"Kept {current_spell.rarity} {current_spell.name}. Discarded {spell.rarity} {spell.name}.")

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
        self.move_player_step(dx, dy)

    def move_player_step(self, dx: int, dy: int) -> str:
        nx, ny = self.player.x + dx, self.player.y + dy
        if not (0 <= nx < self.width and 0 <= ny < self.height):
            self.log("You bump into the edge.")
            return "blocked"

        if self.board[ny][nx] == WALL:
            self.log("A wall blocks your path.")
            return "blocked"

        enemy = self.get_enemy_at(nx, ny)
        if enemy:
            self.combat(enemy)
            return "attacked"

        self.player.x, self.player.y = nx, ny
        self.pickup_item()
        friendly = self.get_friendly_at(nx, ny)
        if friendly:
            self.trade_with_friendly(friendly)

        if (nx, ny) == self.stairs:
            if self.is_miniboss_floor(self.floor) and self.miniboss_alive():
                self.log("A mysterious seal blocks the stairs. Defeat the miniboss first.")
                return "moved"
            if self.is_boss_floor(self.floor) and self.boss_alive():
                self.log("A tyrant's seal blocks the stairs. Defeat the Great Boss first.")
                return "moved"
            self.advance_floor()
            return "advanced"
        return "moved"

    def execute_move_command(self, cmd: str) -> bool:
        direction_map = {
            "w": (0, -1),
            "a": (-1, 0),
            "s": (0, 1),
            "d": (1, 0),
        }
        if any(ch not in direction_map for ch in cmd):
            self.log("Invalid command.")
            return False

        step_limit = self.movement_step_limit()
        steps = cmd[:step_limit]
        for idx, ch in enumerate(steps):
            dx, dy = direction_map[ch]
            outcome = self.move_player_step(dx, dy)
            if outcome in {"attacked", "blocked", "advanced"}:
                if outcome == "attacked" and idx < len(steps) - 1:
                    self.log("Movement stopped after attacking an enemy.")
                break
        return True

    def combat(self, enemy: Entity) -> None:
        base_dmg = self.damage(self.player_attack_value(), enemy.defense)
        if self.gods_wrath_charge_count > 0:
            charged_multiplier = self.gods_wrath_charge_multiplier ** self.gods_wrath_charge_count
            dmg = max(1, int(base_dmg * charged_multiplier))
            self.log(
                "God's Wrath empowers your attack! "
                f"x{charged_multiplier:.2f} ({self.gods_wrath_charge_count} charge)."
            )
            self.gods_wrath_charge_count = 0
            self.gods_wrath_charge_multiplier = 1.0
        else:
            dmg = base_dmg
        self.log(f"You hit the enemy for {dmg} damage.")
        self.apply_damage_with_chain(enemy, dmg, allow_gunpowder=True)
        return

    def spell_power_multiplier(self, rarity: str) -> float:
        return {
            "Common": 1.00,
            "Uncommon": 1.33,
            "Rare": 1.66,
            "Epic": 2.25,
            "Legendary": 3.00,
        }.get(rarity, 1.0)

    def player_attack_value(self) -> int:
        attack = self.player.atk
        if self.equipped_accessory and self.equipped_accessory[1] == "Berserker's club":
            rarity = self.equipped_accessory[0]
            multiplier = self.BERSERKER_ATK_MULTIPLIER_BY_RARITY.get(rarity, 1.20)
            attack = max(1, int(attack * multiplier))
        return max(1, attack)

    def movement_step_limit(self) -> int:
        if self.equipped_accessory and self.equipped_accessory[1] == "Roller shoes":
            rarity = self.equipped_accessory[0]
            return self.ROLLER_SHOES_STEP_LIMIT_BY_RARITY.get(rarity, 2)
        return 1

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

        spell = self.choose_spell()
        if spell is None:
            return False
        if spell.name == "Comet Missile":
            return self.cast_comet_missile(spell)
        if spell.name == "Flare Curtain":
            return self.cast_flare_curtain(spell)
        if spell.name == "God's Wrath":
            return self.cast_gods_wrath()
        if spell.name == "Healing":
            return self.cast_healing(spell)
        if spell.name == "Vampire Kiss":
            return self.cast_vampire_kiss(spell)
        if spell.name == "Frugal soul":
            return self.cast_frugal_soul(spell)

        self.log("Unknown spell.")
        return False

    def apply_spell_damage(self, enemy: Entity, dmg: int, spell_label: str) -> None:
        self.log(f"{spell_label} deals {dmg} damage.")
        self.apply_damage_with_chain(enemy, dmg, allow_gunpowder=True, defeat_log="Enemy defeated by magic.")

    def gunpowder_box_ratio(self) -> float:
        if not self.equipped_accessory or self.equipped_accessory[1] != "Gunpowder box":
            return 0.0
        rarity = self.equipped_accessory[0]
        return self.GUNPOWDER_BOX_RATIO_BY_RARITY.get(rarity, 0.50)

    def adjacent_enemies(self, x: int, y: int) -> List[Entity]:
        adjacent: List[Entity] = []
        for enemy in self.enemies:
            if abs(enemy.x - x) <= 1 and abs(enemy.y - y) <= 1 and not (enemy.x == x and enemy.y == y):
                adjacent.append(enemy)
        return adjacent

    def handle_enemy_defeat(self, enemy: Entity, defeat_log: Optional[str] = None) -> None:
        defeat_x, defeat_y = enemy.x, enemy.y
        self.enemies.remove(enemy)
        if enemy.kind == "miniboss":
            self.log("Miniboss defeated! The stairs are now unsealed.")
            chest_kind = self.random_item_kind()
            self.items.append(ItemEntity(defeat_x, defeat_y, chest_kind, self.roll_high_rarity()))
            self.log("A treasure chest drops a high-rarity item.")
            xp_gain = 12 + self.floor
        elif enemy.kind == "boss":
            self.log("Great Boss defeated! The stairs are now unsealed.")
            chest_kind = self.random_item_kind()
            self.items.append(ItemEntity(defeat_x, defeat_y, chest_kind, "Legendary"))
            self.log("A legendary treasure chest drops where the boss fell.")
            self.boss_laser_targets = []
            xp_gain = 24 + self.floor
        elif enemy.kind == "fortified":
            self.log(defeat_log or "Fortified enemy defeated.")
            xp_gain = 40 + (self.floor * 2)
        else:
            self.log(defeat_log or "Enemy defeated.")
            xp_gain = 3 + self.floor
        self.gain_xp(xp_gain)
        self.maybe_grant_floor_clear_bonus()

    def apply_damage_with_chain(
        self,
        enemy: Entity,
        dmg: int,
        allow_gunpowder: bool = False,
        defeat_log: Optional[str] = None,
    ) -> None:
        if enemy not in self.enemies:
            return

        hp_before = enemy.hp
        enemy.hp -= dmg
        if enemy.hp > 0:
            return

        overflow = max(0, dmg - hp_before)
        self.handle_enemy_defeat(enemy, defeat_log=defeat_log)
        if not allow_gunpowder:
            return

        ratio = self.gunpowder_box_ratio()
        if ratio <= 0 or overflow <= 0:
            return

        splash_damage = int(overflow * ratio)
        if splash_damage <= 0:
            return
        self.log(f"Gunpowder box triggers! Overflow {overflow} -> splash {splash_damage}.")

        for nearby_enemy in list(self.adjacent_enemies(enemy.x, enemy.y)):
            self.log(f"Gunpowder blast hits enemy for {splash_damage} damage.")
            self.apply_damage_with_chain(nearby_enemy, splash_damage, allow_gunpowder=True)

    def frugal_soul_stats(self, rarity: str) -> Tuple[float, int]:
        chance_by_rarity = {
            "Common": 0.20,
            "Uncommon": 0.30,
            "Rare": 0.50,
            "Epic": 0.70,
            "Legendary": 0.85,
        }
        mp_cost_by_rarity = {
            "Common": 2,
            "Uncommon": 3,
            "Rare": 4,
            "Epic": 5,
            "Legendary": 6,
        }
        return chance_by_rarity.get(rarity, 0.20), mp_cost_by_rarity.get(rarity, 2)

    def cast_frugal_soul(self, spell: Spell) -> bool:
        preserve_chance, mp_cost = self.frugal_soul_stats(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False
        self.player_mp -= mp_cost
        self.next_item_preserve_chance = preserve_chance
        self.log(f"{spell.rarity} Frugal soul is active. Next item has {int(preserve_chance * 100)}% chance to not be consumed.")
        self.log(f"MP -{mp_cost}.")
        return True

    def cast_comet_missile(self, spell: Spell) -> bool:
        base_cost = 2
        mp_cost = base_cost + self.spell_mp_bonus(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False

        targets = []
        for dx, dy, dir_label, dir_key in [
            (0, -1, "up", "w"),
            (0, 1, "down", "s"),
            (-1, 0, "left", "a"),
            (1, 0, "right", "d"),
        ]:
            x, y = self.player.x + dx, self.player.y + dy
            while 0 <= x < self.width and 0 <= y < self.height and self.board[y][x] != WALL:
                enemy = self.get_enemy_at(x, y)
                if enemy:
                    targets.append((enemy, dir_label, dir_key))
                    break
                x += dx
                y += dy

        if not targets:
            self.log("No enemy in a straight line for Comet Missile.")
            return False

        if len(targets) == 1:
            target_enemy = targets[0][0]
            direction_name = targets[0][1]
        else:
            self.log("Multiple targets detected for Comet Missile.")
            direction = self.choose_direction("Cast direction [w/a/s/d, other=cancel]: ")
            if direction is None:
                return False
            _, _, direction_name = direction
            direction_key = {"up": "w", "down": "s", "left": "a", "right": "d"}[direction_name]
            target_enemy = next((enemy for enemy, _, key in targets if key == direction_key), None)
            if target_enemy is None:
                self.log("No enemy in the selected direction for Comet Missile.")
                return False

        self.player_mp -= mp_cost
        base = self.damage(self.player_attack_value(), target_enemy.defense)
        dmg = max(1, int(base * self.spell_power_multiplier(spell.rarity)))
        self.apply_spell_damage(target_enemy, dmg, f"{spell.rarity} Comet Missile")
        self.log(f"Comet Missile strikes {direction_name}.")
        self.log(f"MP -{mp_cost}.")
        return True

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
            base = self.damage(self.player_attack_value(), enemy.defense)
            dmg = max(1, int(base * self.spell_power_multiplier(spell.rarity)))
            self.apply_spell_damage(enemy, dmg, f"{spell.rarity} Flare Curtain")
        self.log(f"MP -{mp_cost}.")
        return True

    def cast_healing(self, spell: Spell) -> bool:
        base_cost = 2
        mp_cost = base_cost + self.spell_mp_bonus(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False

        healing_amount = {
            "Common": 4,
            "Uncommon": 8,
            "Rare": 12,
            "Epic": 18,
            "Legendary": 80,
        }.get(spell.rarity, 4)
        self.player_mp -= mp_cost
        healed, _ = self.restore_hp(healing_amount)
        self.log(f"{spell.rarity} Healing restores {healed} HP.")
        self.log(f"MP -{mp_cost}.")
        return True

    def cast_vampire_kiss(self, spell: Spell) -> bool:
        base_cost = 3
        mp_cost = base_cost + self.spell_mp_bonus(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False

        targets = []
        for dx, dy, dir_label, dir_key in [
            (0, -1, "up", "w"),
            (0, 1, "down", "s"),
            (-1, 0, "left", "a"),
            (1, 0, "right", "d"),
        ]:
            enemy = self.get_enemy_at(self.player.x + dx, self.player.y + dy)
            if enemy:
                targets.append((enemy, dir_label, dir_key))
        if not targets:
            self.log("No adjacent enemy for Vampire Kiss.")
            return False

        if len(targets) == 1:
            target_enemy = targets[0][0]
            direction_name = targets[0][1]
        else:
            self.log("Multiple adjacent targets detected for Vampire Kiss.")
            direction = self.choose_direction("Cast direction [w/a/s/d, other=cancel]: ")
            if direction is None:
                return False
            _, _, direction_name = direction
            direction_key = {"up": "w", "down": "s", "left": "a", "right": "d"}[direction_name]
            target_enemy = next((enemy for enemy, _, key in targets if key == direction_key), None)
            if target_enemy is None:
                self.log("No adjacent enemy in the selected direction for Vampire Kiss.")
                return False

        self.player_mp -= mp_cost
        dmg = max(1, int((self.player_attack_value() * (2 / 3)) * self.spell_power_multiplier(spell.rarity)))
        self.apply_spell_damage(target_enemy, dmg, f"{spell.rarity} Vampire Kiss")
        drain = max(1, dmg // 3)
        healed, _ = self.restore_hp(drain)
        self.log(f"Vampire Kiss strikes {direction_name} and drains {healed} HP.")
        self.log(f"MP -{mp_cost}.")
        return True

    def cast_gods_wrath(self) -> bool:
        spell = next((s for s in reversed(self.spells) if s.name == "God's Wrath"), None)
        if spell is None:
            self.log("You do not know God's Wrath.")
            return False

        base_cost = 4
        mp_cost = base_cost + self.spell_mp_bonus(spell.rarity)
        if self.player_mp < mp_cost:
            self.log(f"Not enough MP. Need {mp_cost} MP.")
            return False
        self.player_mp -= mp_cost
        self.gods_wrath_charge_count += 1
        self.gods_wrath_charge_multiplier = 1.5 * self.spell_power_multiplier(spell.rarity)
        boosted = self.gods_wrath_charge_multiplier ** self.gods_wrath_charge_count
        self.log(
            f"{spell.rarity} God's Wrath charge +1 "
            f"(total {self.gods_wrath_charge_count}, next normal attack x{boosted:.2f})."
        )
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
            if enemy.kind == "fortified":
                self.move_fortified_away_from_player(enemy)
                continue
            if abs(enemy.x - self.player.x) + abs(enemy.y - self.player.y) == 1:
                dmg = self.damage(enemy.atk, self.player.defense)
                self.player.hp -= dmg
                self.log(f"Enemy hits you for {dmg} damage.")
                continue

            self.move_enemy_randomly(enemy)

    def move_enemy_randomly(self, enemy: Entity) -> None:
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

    def move_fortified_away_from_player(self, enemy: Entity) -> None:
        current_dist = abs(enemy.x - self.player.x) + abs(enemy.y - self.player.y)
        best_tiles: List[Tuple[int, int]] = []
        best_dist = current_dist
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = enemy.x + dx, enemy.y + dy
            if not (0 <= nx < self.width and 0 <= ny < self.height):
                continue
            if self.board[ny][nx] == WALL:
                continue
            if (nx, ny) == (self.player.x, self.player.y):
                continue
            if self.get_enemy_at(nx, ny):
                continue
            dist = abs(nx - self.player.x) + abs(ny - self.player.y)
            if dist > best_dist:
                best_dist = dist
                best_tiles = [(nx, ny)]
            elif dist == best_dist and dist > current_dist:
                best_tiles.append((nx, ny))
        if best_tiles:
            enemy.x, enemy.y = self.rng.choice(best_tiles)

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
            self.log("The Great Boss marks cardinal lines for a laser strike!")

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
        if self.next_floor_destination is not None:
            destination = max(1, self.next_floor_destination)
            self.next_floor_destination = None
            self.floor = destination
            self.log(f"You take warped stairs to floor {self.floor}.")
        else:
            self.floor += 1
            self.log(f"You descend to floor {self.floor}.")
        if self.current_cycle() > previous_cycle:
            self.log("A new loop begins: enemies are empowered and the map grows wider.")
        self.generate_floor()

    def show_inventory(self) -> None:
        if not self.inventory:
            self.log("Inventory: (empty)")
            return
        self.log("Inventory:")
        for idx, (rarity, kind) in enumerate(self.inventory, start=1):
            self.log(f"{idx}: {rarity} {kind}")

    def show_status_details(self) -> None:
        self.log("=== Status Details ===")
        if self.equipped_accessory:
            rarity, kind = self.equipped_accessory
            description = self.ACCESSORY_DESCRIPTIONS.get(kind, "No description.")
            self.log(f"Accessory: {rarity} {kind} - {description}")
        else:
            self.log("Accessory: None")
        if self.spells:
            for spell in self.spells:
                description = self.ARCANA_DESCRIPTIONS.get(spell.name, "No description.")
                self.log(f"Arcana: {spell.rarity} {spell.name} - {description}")
        else:
            self.log("Arcana: None")

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
        cmd = cmd.strip().lower()
        use_item_by_index = None
        if cmd.startswith("u"):
            parts = cmd.split()
            if len(parts) == 2 and parts[0] == "u" and parts[1].isdigit():
                use_item_by_index = int(parts[1]) - 1
            elif cmd != "u":
                self.log("Invalid command.")
                return True
        move_input = bool(cmd) and all(ch in {"w", "a", "s", "d"} for ch in cmd)
        skill_shortcut = self.parse_skill_shortcut(cmd)
        actionable_command = move_input or cmd in {".", "t", "u"} or use_item_by_index is not None
        if actionable_command:
            self.start_turn_capture()
            self.apply_turn_start_effects()
        if move_input:
            self.reset_guardian_armor_defense()
            acted = self.execute_move_command(cmd)
        elif cmd == ".":
            self.log("You wait.")
            self.stack_guardian_armor_defense()
            acted = True
        elif cmd == "t":
            acted = self.use_technique()
        elif cmd == "i":
            self.show_inventory()
        elif cmd == "u" or use_item_by_index is not None:
            acted = self.use_item(use_item_by_index, auto_select=(cmd == "u"))
        elif cmd == "k":
            self.open_skill_menu()
        elif skill_shortcut is not None:
            self.use_skill_point(skill_shortcut)
        elif cmd == "h":
            for line in self.help_lines():
                self.log(line)
        elif cmd == "l":
            self.show_turn_logs()
        elif cmd == "p":
            self.show_status_details()
        else:
            self.log("Invalid command.")

        if acted:
            self.moves += 1
            self.enemy_turn()
            self.finalize_turn_capture(cmd)
        else:
            self._is_capturing_turn_events = False

        return True

    @staticmethod
    def parse_skill_shortcut(cmd: str) -> Optional[str]:
        compact = cmd.replace(" ", "")
        if len(compact) == 2 and compact[0] == "k" and compact[1] in {"v", "s", "g", "a"}:
            return compact[1]
        return None

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
        print("\n========================================================================================================================================")
        print("   ####   ##   ##    ##     ######     ##       ####   ######   #######  ######    ##      ######    #####     ####   ##   ##  #######")
        print("  ##  ##  ##   ##   ####     ##  ##   ####     ##  ##  # ## #    ##   #   ##  ##   ##       ##  ##  ##   ##   ##  ##  ##   ##   ##   #")
        print(" ##       ##   ##  ##  ##    ##  ##  ##  ##   ##         ##      ## #     ##  ##    ##      ##  ##  ##   ##  ##       ##   ##   ## #")
        print(" ##       #######  ##  ##    #####   ##  ##   ##         ##      ####     #####             #####   ##   ##  ##       ##   ##   ####")
        print(" ##       ##   ##  ######    ## ##   ######   ##         ##      ## #     ## ##             ## ##   ##   ##  ##  ###  ##   ##   ## #")
        print("  ##  ##  ##   ##  ##  ##    ##  ##  ##  ##    ##  ##    ##      ##   #   ##  ##            ##  ##  ##   ##   ##  ##  ##   ##   ##   #")
        print("   ####   ##   ##  ##  ##   #### ##  ##  ##     ####    ####    #######  #### ##           #### ##   #####     #####   #####   #######")
        print("========================================================================================================================================")
        print(f"Difficulty: {difficulty}")
        print("1) Start")
        print("2) Change Difficulty")
        print("3) Quit")
        print("========================================================================================================================================")
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
    print("\n=================================================================================")
    print("  ### ##   ####    ##  ##    ####              ####    ##  ##    ####    ######")
    print(" ##  ##       ##   #######  ##  ##            ##  ##   ##  ##   ##  ##    ##  ##")
    print(" ##  ##    #####   ## # ##  ######            ##  ##   ##  ##   ######    ##")
    print("  #####   ##  ##   ##   ##  ##                ##  ##    ####    ##        ##")
    print("     ##    #####   ##   ##   #####             ####      ##      #####   ####")
    print(" #####")
    print("=================================================================================")
    print(f"Reached Floor : {game.floor}")
    print(f"Player Level  : {game.level}")
    print(f"Final Status  : HP {game.player_max_hp} / MP {game.player_max_mp} / ATK {game.player.atk} / DEF {game.player.defense}")
    print(f"Arcana Count  : {len(game.spells)}")
    print(f"Score         : {score}")
    print("=================================================================================")

def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)
    difficulty = show_title_screen()
    if difficulty is None:
        print("Goodbye!")
        return
    game = Game(difficulty=difficulty)
    game.log(f"Game started on {difficulty} difficulty.")

    while True:
        clear_screen()
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
        cmd = input("Command [w/a/s/d chain, t, ., i, u, u <n>, k, kv/ks/kg/ka, h, l, p]: ").strip().lower()
        if not cmd:
            continue
        game.take_turn(cmd)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame interrupted. Goodbye!")
        sys.exit(0)
