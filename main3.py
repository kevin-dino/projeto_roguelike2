import math
import random
import pygame

# Meu Roguelike - prototipo jogavel (versao 2)
#
# CONTROLES
#   WASD ........ movimenta
#   Setas ....... atiram
#   E / ESPACO .. coloca uma bomba
#   P / ESC ..... pausa (ou clique no botao de pausa no topo da tela)
#   Segurar R ... reinicia o jogo apos 1 segundo (funciona a qualquer momento)
#
# REGRAS
#   - A horda de cada sala nasce uma unica vez; so abre as portas quando todos morrem.
#   - Sala do tesouro (porta dourada): precisa de uma chave e tem uma melhoria.
#   - Bau de madeira abre de graca (itens); bau dourado gasta uma chave (melhoria).
#   - A sala mais distante e a sala do BOSS. Derrote-o para pegar uma melhoria e
#     descer a escada para o proximo andar (inimigos ficam mais fortes).

pygame.init()

WIDTH, HEIGHT = 960, 640
FPS = 60
SCALE = 2
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = WIDTH // SCALE, HEIGHT // SCALE

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Meu Roguelike")
clock = pygame.time.Clock()

# Desenhamos em uma resolucao menor e ampliamos sem suavizacao para um visual pixel art.
canvas = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))

FONT_SMALL = pygame.font.Font(None, 14)
FONT_BIG = pygame.font.Font(None, 34)
FONT_HINT = pygame.font.Font(None, 17)

COLORS = {
    "background": (25, 22, 34),
    "floor": (54, 47, 61),
    "floor_alt": (58, 50, 65),
    "shadow": (40, 35, 48),
    "wall": (26, 24, 34),
    "wall_edge": (104, 83, 103),
    "player": (90, 174, 235),
    "player_light": (183, 229, 255),
    "enemy": (185, 75, 91),
    "enemy_light": (255, 151, 145),
    "fly": (120, 140, 80),
    "fly_wing": (205, 225, 245),
    "tank": (110, 72, 140),
    "tank_light": (166, 128, 196),
    "boss_king": (150, 60, 160),
    "boss_king_light": (206, 120, 214),
    "boss_bull": (170, 110, 70),
    "boss_bull_light": (222, 170, 120),
    "tear": (115, 220, 255),
    "bullet": (255, 120, 110),
    "white": (245, 239, 225),
    "red": (220, 66, 83),
    "dark_red": (86, 34, 49),
    "gold": (246, 201, 91),
    "rock": (78, 70, 86),
    "rock_light": (112, 102, 120),
    "rock_dark": (44, 39, 52),
    "door_closed": (96, 58, 66),
    "door_bar": (50, 30, 38),
    "door_open": (12, 10, 18),
    "door_locked": (200, 160, 60),
    "chest": (128, 82, 46),
    "chest_light": (166, 112, 64),
    "chest_dark": (70, 44, 26),
    "gold_chest": (214, 164, 52),
    "gold_chest_light": (255, 226, 130),
    "bomb": (36, 34, 44),
    "bomb_light": (100, 98, 120),
    "fuse": (255, 170, 70),
    "panel": (10, 8, 15),
    "grey": (130, 120, 140),
    "dim": (62, 56, 72),
}

ROOM = pygame.Rect(25, 25, VIRTUAL_WIDTH - 50, VIRTUAL_HEIGHT - 50)
PLAYER_SIZE = 13
PLAYER_SPEED = 2.25
PLAYER_MAX_HP = 6
TEAR_SPEED = 5.0
TEAR_COOLDOWN = 13
TEAR_LIFE = 105
INVULN_FRAMES = 51            # ~850 ms a 60 FPS
DOOR_W = 24
BOMB_RADIUS = 36
BOMB_FUSE = 75                # frames ate explodir
RESTART_HOLD_MS = 1000

DIRECTIONS = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}

# Atributos de cada tipo de inimigo comum.
ENEMY_TYPES = {
    "fly": {"health": 2, "speed": 1.05, "damage": 1, "size": 10, "flying": True},
    "chaser": {"health": 3, "speed": 0.72, "damage": 1, "size": 13, "flying": False},
    "tank": {"health": 8, "speed": 0.40, "damage": 2, "size": 18, "flying": False},
}

# Melhorias do personagem. "stats" soma valores aos atributos do Player.
ITEMS = {
    "boots": {"name": "BOTAS VELOZES", "desc": "+ velocidade de movimento",
              "glyph": "B", "color": (90, 200, 120), "stats": {"speed": 0.5}},
    "container": {"name": "CONTEINER DE VIDA", "desc": "+1 coracao e cura 1",
                  "glyph": "V", "color": (220, 66, 83), "stats": {"max_hp": 2}, "heal": 2},
    "lens": {"name": "LENTE POTENTE", "desc": "+ dano dos tiros",
             "glyph": "D", "color": (255, 140, 70), "stats": {"damage": 1}},
    "trigger": {"name": "GATILHO RAPIDO", "desc": "+ cadencia de tiro",
                "glyph": "G", "color": (255, 230, 100), "stats": {"cooldown": -4}},
    "double": {"name": "TIRO DUPLO", "desc": "dispara mais uma lagrima",
               "glyph": "2", "color": (115, 220, 255), "stats": {"shots": 1}},
    "range": {"name": "ALCANCE LONGO", "desc": "+ alcance e velocidade do tiro",
              "glyph": "A", "color": (180, 150, 255), "stats": {"tear_life": 45, "tear_speed": 1.0}},
    "bombbag": {"name": "MOCHILA DE BOMBAS", "desc": "+3 bombas e bombas mais fortes",
                "glyph": "M", "color": (150, 150, 170), "stats": {"bombs": 3, "bomb_damage": 2}},
    "amulet": {"name": "AMULETO", "desc": "mais tempo invulneravel ao tomar dano",
               "glyph": "U", "color": (255, 255, 255), "stats": {"invuln_frames": 30}},
    "goldheart": {"name": "CORACAO DOURADO", "desc": "+1 coracao e cura total",
                  "glyph": "C", "color": (246, 201, 91), "stats": {"max_hp": 2}, "heal": 99},
}

SPREADS = {1: [0.0], 2: [-0.10, 0.10], 3: [-0.20, 0.0, 0.20]}


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def clamp(value, low, high):
    return max(low, min(high, value))


def circle_rect_collision(cx, cy, radius, rect):
    closest_x = clamp(cx, rect.left, rect.right)
    closest_y = clamp(cy, rect.top, rect.bottom)
    return (cx - closest_x) ** 2 + (cy - closest_y) ** 2 < radius ** 2


def move_with_rocks(entity, dx, dy, rocks):
    """Move um corpo terrestre eixo por eixo, desfazendo o passo se bater numa pedra."""
    entity.x += dx
    if any(entity.rect.colliderect(rock) for rock in rocks):
        entity.x -= dx
    entity.y += dy
    if any(entity.rect.colliderect(rock) for rock in rocks):
        entity.y -= dy


def door_trigger(direction):
    """Retangulo da porta (tambem usado como area de passagem)."""
    cx, cy = ROOM.center
    if direction == "N":
        return pygame.Rect(cx - DOOR_W // 2, ROOM.top, DOOR_W, 8)
    if direction == "S":
        return pygame.Rect(cx - DOOR_W // 2, ROOM.bottom - 8, DOOR_W, 8)
    if direction == "W":
        return pygame.Rect(ROOM.left, cy - DOOR_W // 2, 8, DOOR_W)
    return pygame.Rect(ROOM.right - 8, cy - DOOR_W // 2, 8, DOOR_W)  # "E"


def entry_position(direction):
    """Onde o jogador aparece ao atravessar uma porta (lado oposto da nova sala)."""
    cx, cy = ROOM.center
    if direction == "N":
        return cx, ROOM.bottom - 18
    if direction == "S":
        return cx, ROOM.top + 18
    if direction == "E":
        return ROOM.left + 18, cy
    return ROOM.right - 18, cy  # "W"


def find_free_spot(rocks, w, h, taken=()):
    """Acha um retangulo livre (longe do centro, das portas, de pedras e de outros objetos)."""
    center = pygame.Vector2(ROOM.center)
    for _ in range(80):
        x = random.randint(ROOM.left + 14, ROOM.right - 14 - w)
        y = random.randint(ROOM.top + 14, ROOM.bottom - 14 - h)
        rect = pygame.Rect(x, y, w, h)
        if pygame.Vector2(rect.center).distance_to(center) < 45:
            continue
        if any(door_trigger(d).inflate(40, 40).colliderect(rect) for d in DIRECTIONS):
            continue
        if any(rect.colliderect(o.inflate(10, 10)) for o in list(rocks) + list(taken)):
            continue
        return rect
    return None


# ----------------------------------------------------------------------------
# Geracao da dungeon
# ----------------------------------------------------------------------------
def generate_dungeon(total_rooms=9):
    rooms = {(0, 0)}
    while len(rooms) < total_rooms:
        current = random.choice(list(rooms))
        dx, dy = random.choice(list(DIRECTIONS.values()))
        new_room = (current[0] + dx, current[1] + dy)
        if abs(new_room[0]) <= 3 and abs(new_room[1]) <= 3:
            rooms.add(new_room)
    return rooms


def get_neighbors(rooms, position):
    x, y = position
    neighbors = {}
    for direction, (dx, dy) in DIRECTIONS.items():
        target = (x + dx, y + dy)
        if target in rooms:
            neighbors[direction] = target
    return neighbors


def bfs_distances(layout):
    """Distancia (em salas) de cada sala ate a sala inicial."""
    dist = {(0, 0): 0}
    queue = [(0, 0)]
    while queue:
        current = queue.pop(0)
        for target in get_neighbors(layout, current).values():
            if target not in dist:
                dist[target] = dist[current] + 1
                queue.append(target)
    return dist


def make_rocks(count):
    """Pedras bloqueiam jogador, inimigos terrestres e tiros. Voadores passam por cima."""
    rocks = []
    center = pygame.Vector2(ROOM.center)
    for _ in range(count):
        for _attempt in range(50):
            x = random.randint(ROOM.left + 10, ROOM.right - 26) // 8 * 8
            y = random.randint(ROOM.top + 10, ROOM.bottom - 26) // 8 * 8
            rect = pygame.Rect(x, y, 16, 16)
            if pygame.Vector2(rect.center).distance_to(center) < 45:
                continue
            if any(door_trigger(d).inflate(40, 40).colliderect(rect) for d in DIRECTIONS):
                continue
            if any(rect.colliderect(other.inflate(8, 8)) for other in rocks):
                continue
            rocks.append(rect)
            break
    return rocks


# ----------------------------------------------------------------------------
# Icones reutilizados no HUD e no chao
# ----------------------------------------------------------------------------
def draw_key_icon(surface, x, y):
    pygame.draw.circle(surface, COLORS["gold"], (x + 3, y + 4), 3)
    pygame.draw.rect(surface, COLORS["gold"], (x + 5, y + 3, 6, 2))
    pygame.draw.rect(surface, COLORS["gold"], (x + 9, y + 5, 2, 2))


def draw_bomb_icon(surface, x, y, color=None):
    pygame.draw.circle(surface, color or COLORS["bomb_light"], (x + 4, y + 5), 4)
    pygame.draw.rect(surface, COLORS["bomb"], (x + 2, y + 5, 5, 3))
    pygame.draw.rect(surface, COLORS["fuse"], (x + 6, y - 1, 2, 3))


def draw_heart_icon(surface, x, y):
    pygame.draw.rect(surface, COLORS["red"], (x, y, 8, 7))
    pygame.draw.rect(surface, COLORS["white"], (x + 1, y + 1, 2, 2))


# ----------------------------------------------------------------------------
# Projeteis, bombas e efeitos
# ----------------------------------------------------------------------------
class Tear:
    def __init__(self, x, y, dx, dy, damage, speed, life):
        self.x = float(x)
        self.y = float(y)
        self.dx = dx
        self.dy = dy
        self.damage = damage
        self.speed = speed
        self.radius = 3
        self.life = life

    def update(self):
        self.x += self.dx * self.speed
        self.y += self.dy * self.speed
        self.life -= 1

    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        pygame.draw.circle(surface, COLORS["tear"], (x, y), self.radius)
        pygame.draw.rect(surface, COLORS["white"], (x - 1, y - 2, 2, 2))


class Bullet:
    """Projetil inimigo (usado pelos bosses)."""

    def __init__(self, x, y, vx, vy):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.radius = 3
        self.life = 260

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        pygame.draw.circle(surface, COLORS["dark_red"], (x, y), self.radius + 1)
        pygame.draw.circle(surface, COLORS["bullet"], (x, y), self.radius)
        pygame.draw.rect(surface, COLORS["white"], (x - 1, y - 1, 2, 2))


def fire_ring(bullets, x, y, count, offset, speed):
    for i in range(count):
        angle = offset + i * math.tau / count
        bullets.append(Bullet(x, y, math.cos(angle) * speed, math.sin(angle) * speed))


class Bomb:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.fuse = BOMB_FUSE

    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        lit = self.fuse < 30 and (self.fuse // 4) % 2 == 0
        pygame.draw.circle(surface, COLORS["white"] if lit else COLORS["bomb"], (x, y), 5)
        pygame.draw.circle(surface, COLORS["bomb_light"], (x - 2, y - 2), 1)
        pygame.draw.rect(surface, COLORS["fuse"], (x + 2, y - 8, 2, 4))


class Explosion:
    LIFE = 20

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.life = self.LIFE

    def draw(self, surface):
        progress = 1 - self.life / self.LIFE
        radius = int(BOMB_RADIUS * (0.4 + 0.6 * progress))
        pygame.draw.circle(surface, COLORS["fuse"], (round(self.x), round(self.y)), radius)
        pygame.draw.circle(surface, COLORS["gold"], (round(self.x), round(self.y)), int(radius * 0.7))
        if self.life > self.LIFE // 2:
            pygame.draw.circle(surface, COLORS["white"], (round(self.x), round(self.y)), int(radius * 0.35))


# ----------------------------------------------------------------------------
# Objetos do chao: pickups, itens, baus
# ----------------------------------------------------------------------------
class Pickup:
    def __init__(self, x, y, kind):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind  # "heart", "bomb", "key"
        self.rect = pygame.Rect(round(x) - 6, round(y) - 6, 12, 12)

    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        pygame.draw.ellipse(surface, COLORS["shadow"], (x - 4, y + 4, 9, 3))
        if self.kind == "heart":
            draw_heart_icon(surface, x - 4, y - 4)
        elif self.kind == "bomb":
            draw_bomb_icon(surface, x - 4, y - 5)
        else:
            draw_key_icon(surface, x - 5, y - 4)


class Item:
    """Melhoria do personagem flutuando sobre um pedestal."""

    def __init__(self, x, y, item_id):
        self.x = float(x)
        self.y = float(y)
        self.item_id = item_id
        self.rect = pygame.Rect(round(x) - 8, round(y) - 8, 16, 16)

    def draw(self, surface):
        data = ITEMS[self.item_id]
        x, y = round(self.x), round(self.y)
        bob = round(math.sin(pygame.time.get_ticks() / 220) * 2)
        pygame.draw.rect(surface, COLORS["rock_dark"], (x - 9, y + 5, 18, 5))
        pygame.draw.rect(surface, COLORS["rock"], (x - 8, y + 4, 16, 4))
        pygame.draw.rect(surface, COLORS["panel"], (x - 7, y - 8 + bob, 14, 14))
        pygame.draw.rect(surface, data["color"], (x - 6, y - 7 + bob, 12, 12))
        glyph = FONT_SMALL.render(data["glyph"], True, COLORS["panel"])
        surface.blit(glyph, glyph.get_rect(center=(x, y - 1 + bob)))


class Chest:
    def __init__(self, x, y, kind):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind  # "wood" ou "gold"
        self.opened = False
        self.rect = pygame.Rect(round(x) - 8, round(y) - 6, 16, 13)

    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        gold = self.kind == "gold"
        body = COLORS["gold_chest"] if gold else COLORS["chest"]
        light = COLORS["gold_chest_light"] if gold else COLORS["chest_light"]
        if self.opened:
            pygame.draw.rect(surface, COLORS["chest_dark"], (x - 8, y - 2, 16, 9))
            pygame.draw.rect(surface, COLORS["panel"], (x - 6, y - 1, 12, 3))
            pygame.draw.rect(surface, light, (x - 8, y - 8, 16, 4))
        else:
            pygame.draw.rect(surface, body, (x - 8, y - 5, 16, 12))
            pygame.draw.rect(surface, light, (x - 8, y - 6, 16, 5))
            pygame.draw.rect(surface, COLORS["gold"] if not gold else COLORS["white"], (x - 1, y - 6, 2, 12))
            pygame.draw.rect(surface, COLORS["panel"], (x - 2, y - 1, 4, 3))


# ----------------------------------------------------------------------------
# Inimigos
# ----------------------------------------------------------------------------
class Enemy:
    is_boss = False

    def __init__(self, x, y, enemy_type, bonus_health=0):
        stats = ENEMY_TYPES[enemy_type]
        self.enemy_type = enemy_type
        self.x = float(x)
        self.y = float(y)
        self.health = stats["health"] + bonus_health
        self.speed = stats["speed"]
        self.damage = stats["damage"]
        self.size = stats["size"]
        self.flying = stats["flying"]
        self.flash = 0
        self.age = random.randint(0, 100)
        self.phase = random.uniform(0, math.tau)

    @property
    def rect(self):
        return pygame.Rect(round(self.x - self.size / 2),
                           round(self.y - self.size / 2),
                           self.size, self.size)

    def update(self, player, rocks, others, bullets):
        self.age += 1
        dx = player.x - self.x
        dy = player.y - self.y
        distance = math.hypot(dx, dy)

        if distance > 1:
            ux, uy = dx / distance, dy / distance
            if self.flying:
                # Voador: ignora pedras e balanca de lado enquanto se aproxima.
                wobble = math.sin(self.age * 0.08 + self.phase) * 0.7
                self.x += (ux - uy * wobble) * self.speed
                self.y += (uy + ux * wobble) * self.speed
            else:
                # Terrestre: anda direto ao jogador, mas e barrado pelas pedras.
                move_with_rocks(self, ux * self.speed, uy * self.speed, rocks)

        # Separacao simples para inimigos da mesma camada nao ficarem empilhados.
        for other in others:
            if other is self or other.is_boss or other.flying != self.flying:
                continue
            ox = self.x - other.x
            oy = self.y - other.y
            d = math.hypot(ox, oy)
            min_d = (self.size + other.size) / 2
            if 0 < d < min_d:
                push = (min_d - d) * 0.08
                self.x += ox / d * push
                self.y += oy / d * push

        half = self.size / 2
        self.x = clamp(self.x, ROOM.left + half, ROOM.right - half)
        self.y = clamp(self.y, ROOM.top + half, ROOM.bottom - half)
        self.flash = max(0, self.flash - 1)

    def draw(self, surface):
        if self.enemy_type == "fly":
            self._draw_fly(surface)
        elif self.enemy_type == "tank":
            self._draw_tank(surface)
        else:
            self._draw_chaser(surface)

    def _draw_chaser(self, surface):
        color = COLORS["white"] if self.flash else COLORS["enemy"]
        x, y = round(self.x), round(self.y)
        pygame.draw.rect(surface, color, (x - 7, y - 6, 14, 13))
        pygame.draw.rect(surface, COLORS["enemy_light"], (x - 5, y - 7, 10, 3))
        pygame.draw.rect(surface, COLORS["dark_red"], (x - 4, y - 1, 2, 2))
        pygame.draw.rect(surface, COLORS["dark_red"], (x + 2, y - 1, 2, 2))

    def _draw_tank(self, surface):
        color = COLORS["white"] if self.flash else COLORS["tank"]
        x, y = round(self.x), round(self.y)
        pygame.draw.rect(surface, color, (x - 9, y - 8, 18, 17))
        pygame.draw.rect(surface, COLORS["tank_light"], (x - 8, y - 9, 16, 4))
        pygame.draw.rect(surface, COLORS["tank_light"], (x - 11, y - 4, 2, 3))
        pygame.draw.rect(surface, COLORS["tank_light"], (x + 9, y - 4, 2, 3))
        pygame.draw.rect(surface, COLORS["dark_red"], (x - 5, y - 1, 3, 3))
        pygame.draw.rect(surface, COLORS["dark_red"], (x + 2, y - 1, 3, 3))

    def _draw_fly(self, surface):
        x, y = round(self.x), round(self.y)
        bob = round(math.sin(self.age * 0.15) * 2)
        # Sombra no chao reforca a ideia de que ele esta no ar.
        pygame.draw.ellipse(surface, COLORS["shadow"], (x - 4, y + 7, 8, 3))
        wing_h = 3 + ((self.age // 4) % 2) * 2
        pygame.draw.rect(surface, COLORS["fly_wing"], (x - 9, y - 5 + bob, 5, wing_h))
        pygame.draw.rect(surface, COLORS["fly_wing"], (x + 4, y - 5 + bob, 5, wing_h))
        body = COLORS["white"] if self.flash else COLORS["fly"]
        pygame.draw.circle(surface, body, (x, y + bob), 5)
        pygame.draw.rect(surface, COLORS["red"], (x - 3, y - 1 + bob, 2, 2))
        pygame.draw.rect(surface, COLORS["red"], (x + 1, y - 1 + bob, 2, 2))


class Boss:
    """Dois bosses:
       king - Rei Slime: persegue devagar, dispara aneis de balas e invoca moscas.
       bull - Touro de Ferro: mira, investe contra o jogador e solta balas ao bater na parede.
       Abaixo de 50% de vida entram em fase furiosa (mais rapidos e mais balas)."""

    is_boss = True
    flying = False
    size = 30

    def __init__(self, x, y, kind, floor):
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.name = "REI SLIME" if kind == "king" else "TOURO DE FERRO"
        self.max_health = 40 + 14 * (floor - 1)
        self.health = self.max_health
        self.damage = 2
        self.flash = 0
        self.age = 0
        self.state = "idle"
        self.timer = 90
        self.summon_timer = 240
        self.vx = 0.0
        self.vy = 0.0

    @property
    def rect(self):
        return pygame.Rect(round(self.x - 15), round(self.y - 14), 30, 29)

    @property
    def enraged(self):
        return self.health <= self.max_health / 2

    def update(self, player, rocks, others, bullets):
        self.age += 1
        self.flash = max(0, self.flash - 1)
        if self.kind == "king":
            self._update_king(player, others, bullets)
        else:
            self._update_bull(player, bullets)
        self.x = clamp(self.x, ROOM.left + 15, ROOM.right - 15)
        self.y = clamp(self.y, ROOM.top + 15, ROOM.bottom - 15)

    def _toward(self, player):
        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy) or 1
        return dx / d, dy / d

    def _update_king(self, player, others, bullets):
        ux, uy = self._toward(player)
        speed = 0.55 if self.enraged else 0.35
        self.x += ux * speed
        self.y += uy * speed

        self.timer -= 1
        if self.timer <= 0:
            count = 12 if self.enraged else 8
            fire_ring(bullets, self.x, self.y, count, self.age * 0.05, 1.5)
            self.timer = 70 if self.enraged else 100

        self.summon_timer -= 1
        if self.summon_timer <= 0:
            if len(others) < 6:
                for sx in (-22, 22):
                    others.append(Enemy(self.x + sx, self.y, "fly"))
            self.summon_timer = 300 if self.enraged else 420

    def _update_bull(self, player, bullets):
        if self.state == "idle":
            ux, uy = self._toward(player)
            self.x += ux * 0.5
            self.y += uy * 0.5
            self.timer -= 1
            if self.timer <= 0:
                self.state = "windup"
                self.timer = 30 if self.enraged else 40
        elif self.state == "windup":
            self.timer -= 1
            if self.timer <= 0:
                ux, uy = self._toward(player)
                charge = 5.0 if self.enraged else 4.2
                self.vx, self.vy = ux * charge, uy * charge
                self.state = "charge"
        elif self.state == "charge":
            self.x += self.vx
            self.y += self.vy
            hit_wall = (self.x <= ROOM.left + 15 or self.x >= ROOM.right - 15 or
                        self.y <= ROOM.top + 15 or self.y >= ROOM.bottom - 15)
            if hit_wall:
                count = 10 if self.enraged else 6
                fire_ring(bullets, self.x, self.y, count, self.age * 0.1, 1.4)
                self.state = "stun"
                self.timer = 45
        elif self.state == "stun":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "idle"
                self.timer = 50 if self.enraged else 70

    def draw(self, surface):
        if self.kind == "king":
            base, light = COLORS["boss_king"], COLORS["boss_king_light"]
        else:
            base, light = COLORS["boss_bull"], COLORS["boss_bull_light"]
        if self.flash or (self.state == "windup" and (self.age // 3) % 2 == 0):
            base = COLORS["white"]

        x, y = round(self.x), round(self.y)
        if self.state == "windup":
            x += random.randint(-1, 1)

        pygame.draw.ellipse(surface, COLORS["shadow"], (x - 14, y + 12, 28, 6))
        pygame.draw.rect(surface, base, (x - 15, y - 14, 30, 29))
        pygame.draw.rect(surface, light, (x - 13, y - 15, 26, 5))

        if self.kind == "king":
            pygame.draw.rect(surface, COLORS["gold"], (x - 11, y - 17, 22, 3))
            for cx in (-10, -2, 6):
                pygame.draw.rect(surface, COLORS["gold"], (x + cx, y - 22, 4, 6))
        else:
            pygame.draw.rect(surface, COLORS["white"], (x - 19, y - 17, 5, 9))
            pygame.draw.rect(surface, COLORS["white"], (x + 14, y - 17, 5, 9))

        eye = COLORS["red"] if self.enraged else COLORS["dark_red"]
        pygame.draw.rect(surface, eye, (x - 8, y - 3, 4, 4))
        pygame.draw.rect(surface, eye, (x + 4, y - 3, 4, 4))
        pygame.draw.rect(surface, COLORS["dark_red"], (x - 7, y + 6, 14, 3))


# ----------------------------------------------------------------------------
# Jogador
# ----------------------------------------------------------------------------
class Player:
    def __init__(self):
        self.x = VIRTUAL_WIDTH / 2
        self.y = VIRTUAL_HEIGHT / 2
        self.size = PLAYER_SIZE
        self.speed = PLAYER_SPEED
        self.max_hp = PLAYER_MAX_HP
        self.hp = PLAYER_MAX_HP
        self.damage = 1
        self.cooldown = TEAR_COOLDOWN
        self.shots = 1
        self.tear_speed = TEAR_SPEED
        self.tear_life = TEAR_LIFE
        self.invuln_frames = INVULN_FRAMES
        self.invuln = 0
        self.bombs = 1
        self.keys = 0
        self.bomb_damage = 5
        self.items = []

    @property
    def rect(self):
        return pygame.Rect(round(self.x - self.size / 2),
                           round(self.y - self.size / 2),
                           self.size, self.size)

    def move(self, keys, rocks):
        dx = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
        dy = int(keys[pygame.K_s]) - int(keys[pygame.K_w])
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071

        move_with_rocks(self, dx * self.speed, dy * self.speed, rocks)

        half = self.size / 2
        self.x = clamp(self.x, ROOM.left + half, ROOM.right - half)
        self.y = clamp(self.y, ROOM.top + half, ROOM.bottom - half)

    def draw(self, surface):
        if self.invuln > 0 and (self.invuln // 4) % 2 == 0:
            return

        x, y = round(self.x), round(self.y)
        pygame.draw.rect(surface, COLORS["player"], (x - 6, y - 6, 12, 13))
        pygame.draw.rect(surface, COLORS["player_light"], (x - 4, y - 7, 8, 3))
        pygame.draw.rect(surface, COLORS["white"], (x - 3, y - 2, 2, 2))
        pygame.draw.rect(surface, COLORS["white"], (x + 2, y - 2, 2, 2))


def apply_item(player, item_id):
    data = ITEMS[item_id]
    for stat, delta in data["stats"].items():
        setattr(player, stat, getattr(player, stat) + delta)
    player.hp = min(player.max_hp, player.hp + data.get("heal", 0))
    player.cooldown = max(5, player.cooldown)
    player.shots = min(3, player.shots)
    if item_id not in player.items:
        player.items.append(item_id)


# ----------------------------------------------------------------------------
# Salas
# ----------------------------------------------------------------------------
def spawn_horde(rocks, player_pos, floor):
    """Cria a horda da sala: mistura de voadores e terrestres (no maximo 1 tank)."""
    enemies = []
    has_tank = False
    count = min(7, random.randint(3, 5) + (floor - 1) // 2)
    bonus = (floor - 1) // 2
    for _ in range(count):
        enemy_type = random.choices(["fly", "chaser", "tank"], weights=[4, 4, 1])[0]
        if enemy_type == "tank" and has_tank:
            enemy_type = "chaser"
        size = ENEMY_TYPES[enemy_type]["size"]
        flying = ENEMY_TYPES[enemy_type]["flying"]

        for _attempt in range(100):
            x = random.randint(ROOM.left + 25, ROOM.right - 25)
            y = random.randint(ROOM.top + 25, ROOM.bottom - 25)
            if math.hypot(x - player_pos[0], y - player_pos[1]) < 70:
                continue
            candidate = pygame.Rect(x - size // 2, y - size // 2, size, size)
            if not flying and any(candidate.colliderect(r.inflate(6, 6)) for r in rocks):
                continue
            enemies.append(Enemy(x, y, enemy_type, bonus))
            has_tank = has_tank or enemy_type == "tank"
            break
    return enemies


class Room:
    def __init__(self, position, neighbors, role="combat", boss_kind="king"):
        self.position = position
        self.neighbors = neighbors
        self.role = role              # start | combat | treasure | boss
        self.boss_kind = boss_kind
        if role == "combat":
            self.rocks = make_rocks(random.randint(3, 6))
        elif role == "start":
            self.rocks = make_rocks(2)
        else:
            self.rocks = []
        self.enemies = []
        self.chests = []
        self.pickups = []
        self.items = []
        self.hatch = None             # escada para o proximo andar (sala do boss)
        self.bonus_key = False        # sala que garante uma chave ao ser limpa
        self.locked = role == "treasure"
        self.visited = role == "start"
        self.spawned = role in ("start", "treasure")
        self.cleared = self.spawned
        self.rewarded = self.spawned

    def enter(self, game):
        self.visited = True
        # A horda so e criada na PRIMEIRA vez. Depois disso a sala nunca mais gera inimigos.
        if self.spawned:
            return
        self.spawned = True
        player = game.player
        if self.role == "boss":
            cx, cy = ROOM.center
            boss = Boss(cx, cy, self.boss_kind, game.floor)
            self.enemies = [boss]
            game.show_banner(boss.name, "Cuidado!", 150)
        else:
            self.enemies = spawn_horde(self.rocks, (player.x, player.y), game.floor)
        if not self.enemies:
            self.cleared = True

    def update(self):
        if self.spawned and not self.cleared and not self.enemies:
            self.cleared = True

    def is_door_open(self, direction):
        return direction in self.neighbors and self.cleared


# ----------------------------------------------------------------------------
# Estado do jogo
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.player = Player()
        self.floor = 1
        self.tears = []
        self.bullets = []
        self.bombs = []
        self.explosions = []
        self.shoot_timer = 0
        self.game_over = False
        self.banner = None  # [titulo, subtitulo, frames]
        self.rooms = {}
        self.room = None
        self.build_floor()

    # ---- construcao do andar -------------------------------------------------
    def build_floor(self):
        layout = generate_dungeon(min(8 + self.floor, 13))
        dist = bfs_distances(layout)
        others = [p for p in layout if p != (0, 0)]
        far = max(dist[p] for p in others)
        boss_pos = random.choice([p for p in others if dist[p] == far])
        candidates = [p for p in others if p != boss_pos]
        dead_ends = [p for p in candidates if len(get_neighbors(layout, p)) == 1]
        treasure_pos = random.choice(dead_ends or candidates)
        combat = [p for p in candidates if p != treasure_pos]
        boss_kind = random.choice(["king", "bull"])

        self.rooms = {}
        for pos in layout:
            if pos == (0, 0):
                role = "start"
            elif pos == boss_pos:
                role = "boss"
            elif pos == treasure_pos:
                role = "treasure"
            else:
                role = "combat"
            self.rooms[pos] = Room(pos, get_neighbors(layout, pos), role, boss_kind)

        # Duas salas de combate garantem uma chave (uma para o tesouro, outra para o bau dourado).
        for pos in random.sample(combat, min(2, len(combat))):
            self.rooms[pos].bonus_key = True

        # Baus: um dourado garantido e alguns de madeira.
        gold_pos = random.choice(combat) if combat else None
        for pos in combat:
            room = self.rooms[pos]
            kind = "gold" if pos == gold_pos else ("wood" if random.random() < 0.3 else None)
            if kind:
                spot = find_free_spot(room.rocks, 16, 13, [c.rect for c in room.chests])
                if spot:
                    room.chests.append(Chest(spot.centerx, spot.centery, kind))

        # Melhoria da sala do tesouro.
        cx, cy = ROOM.center
        self.rooms[treasure_pos].items.append(Item(cx, cy, self.random_item()))

        self.room = self.rooms[(0, 0)]
        self.player.x, self.player.y = cx, cy
        self.tears.clear()
        self.bullets.clear()
        self.bombs.clear()
        self.explosions.clear()

    def next_floor(self):
        self.floor += 1
        self.build_floor()
        self.show_banner(f"ANDAR {self.floor}", "Os inimigos estao mais fortes", 150)

    def random_item(self):
        lying = {i.item_id for r in self.rooms.values() for i in r.items}
        pool = [i for i in ITEMS if i not in self.player.items and i not in lying]
        return random.choice(pool) if pool else "bombbag"

    # ---- utilidades ------------------------------------------------------------
    def show_banner(self, title, sub="", frames=120, only_if_empty=False):
        if only_if_empty and self.banner:
            return
        self.banner = [title, sub, frames]

    def hurt_player(self, amount):
        p = self.player
        if p.invuln > 0 or self.game_over:
            return
        p.hp -= amount
        p.invuln = p.invuln_frames
        if p.hp <= 0:
            p.hp = 0
            self.game_over = True

    def drop_pickup(self, room, x, y, kind=None):
        kind = kind or random.choices(["heart", "bomb", "key"], weights=[4, 3, 2])[0]
        px, py = x, y
        for _ in range(12):
            tx = clamp(x + random.randint(-18, 18), ROOM.left + 12, ROOM.right - 12)
            ty = clamp(y + random.randint(-18, 18), ROOM.top + 12, ROOM.bottom - 12)
            if not any(r.collidepoint(tx, ty) for r in room.rocks):
                px, py = tx, ty
                break
        room.pickups.append(Pickup(px, py, kind))

    def kill_enemy(self, enemy):
        room = self.room
        if enemy in room.enemies:
            room.enemies.remove(enemy)
        if enemy.is_boss:
            room.enemies.clear()   # os servos morrem junto com o boss
            self.bullets.clear()
        elif random.random() < 0.12:
            self.drop_pickup(room, enemy.x, enemy.y)

    def on_room_cleared(self, room):
        if room.rewarded:
            return
        room.rewarded = True
        cx, cy = ROOM.center
        if room.role == "boss":
            room.items.append(Item(cx - 26, cy, self.random_item()))
            room.hatch = pygame.Rect(cx + 14, cy - 10, 20, 20)
            self.show_banner("BOSS DERROTADO!", "Pegue a melhoria e desca a escada", 180)
        elif room.bonus_key:
            self.drop_pickup(room, cx, cy, "key")
        elif random.random() < 0.3:
            self.drop_pickup(room, cx, cy)

    # ---- acoes -----------------------------------------------------------------
    def place_bomb(self):
        p = self.player
        if p.bombs <= 0 or self.game_over:
            return
        p.bombs -= 1
        self.bombs.append(Bomb(p.x, p.y))

    def explode(self, bomb):
        room, p = self.room, self.player
        bx, by = bomb.x, bomb.y
        for enemy in list(room.enemies):
            if circle_rect_collision(bx, by, BOMB_RADIUS, enemy.rect):
                enemy.health -= p.bomb_damage
                enemy.flash = 5
                if enemy.health <= 0:
                    self.kill_enemy(enemy)
        room.rocks = [r for r in room.rocks if not circle_rect_collision(bx, by, BOMB_RADIUS, r)]
        self.bullets = [b for b in self.bullets
                        if (b.x - bx) ** 2 + (b.y - by) ** 2 > BOMB_RADIUS ** 2]
        if circle_rect_collision(bx, by, BOMB_RADIUS, p.rect):
            self.hurt_player(2)
        self.explosions.append(Explosion(bx, by))

    def open_chest(self, room, chest):
        chest.opened = True
        if chest.kind == "gold":
            ix = clamp(chest.x, ROOM.left + 14, ROOM.right - 14)
            iy = clamp(chest.y + 18, ROOM.top + 14, ROOM.bottom - 14)
            room.items.append(Item(ix, iy, self.random_item()))
        else:
            for _ in range(random.randint(2, 3)):
                self.drop_pickup(room, chest.x, chest.y)

    def try_change_room(self, direction):
        target = self.rooms[self.room.neighbors[direction]]
        if target.locked:
            if self.player.keys <= 0:
                self.show_banner("PORTA TRANCADA", "Voce precisa de uma chave", 90, only_if_empty=True)
                return
            self.player.keys -= 1
            target.locked = False
            self.show_banner("PORTA DESTRANCADA", "", 60)
        self.room = target
        self.player.x, self.player.y = entry_position(direction)
        self.tears.clear()
        self.bullets.clear()
        self.bombs.clear()
        self.explosions.clear()
        target.enter(self)

    # ---- atualizacao por frame -------------------------------------------------
    def update(self, keys):
        p, room = self.player, self.room
        if p.invuln > 0:
            p.invuln -= 1
        if self.banner:
            self.banner[2] -= 1
            if self.banner[2] <= 0:
                self.banner = None

        p.move(keys, room.rocks)
        self.update_shooting(keys)
        self.update_tears()
        self.update_bullets()

        for enemy in list(room.enemies):
            if enemy not in room.enemies:
                continue
            enemy.update(p, room.rocks, room.enemies, self.bullets)
            if enemy.rect.colliderect(p.rect):
                self.hurt_player(enemy.damage)

        for bomb in self.bombs[:]:
            bomb.fuse -= 1
            if bomb.fuse <= 0:
                self.bombs.remove(bomb)
                self.explode(bomb)
        for ex in self.explosions[:]:
            ex.life -= 1
            if ex.life <= 0:
                self.explosions.remove(ex)

        self.update_interactions()

        # Quando o ultimo inimigo morre, a sala e marcada como limpa e as portas abrem.
        was_cleared = room.cleared
        room.update()
        if room.cleared and not was_cleared:
            self.on_room_cleared(room)

        # Atravessar portas (so funciona se estiverem abertas).
        if self.room is room and room.cleared and not self.game_over:
            for direction in room.neighbors:
                if p.rect.colliderect(door_trigger(direction)):
                    self.try_change_room(direction)
                    break

    def update_shooting(self, keys):
        p = self.player
        aim_x = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        aim_y = int(keys[pygame.K_DOWN]) - int(keys[pygame.K_UP])
        self.shoot_timer = max(0, self.shoot_timer - 1)
        if (aim_x or aim_y) and self.shoot_timer == 0:
            base = math.atan2(aim_y, aim_x)
            for off in SPREADS[p.shots]:
                a = base + off
                self.tears.append(Tear(p.x, p.y, math.cos(a), math.sin(a),
                                       p.damage, p.tear_speed, p.tear_life))
            self.shoot_timer = p.cooldown

    def update_tears(self):
        room = self.room
        bounds = ROOM.inflate(-5, -5)
        for tear in self.tears[:]:
            tear.update()
            if (tear.life <= 0
                    or not bounds.collidepoint(tear.x, tear.y)
                    or any(rock.collidepoint(tear.x, tear.y) for rock in room.rocks)):
                self.tears.remove(tear)
                continue

            for enemy in room.enemies:
                if circle_rect_collision(tear.x, tear.y, tear.radius, enemy.rect):
                    enemy.health -= tear.damage
                    enemy.flash = 5
                    self.tears.remove(tear)
                    if enemy.health <= 0:
                        self.kill_enemy(enemy)
                    break

    def update_bullets(self):
        room, p = self.room, self.player
        bounds = ROOM.inflate(-5, -5)
        for bullet in self.bullets[:]:
            bullet.update()
            if (bullet.life <= 0
                    or not bounds.collidepoint(bullet.x, bullet.y)
                    or any(rock.collidepoint(bullet.x, bullet.y) for rock in room.rocks)):
                self.bullets.remove(bullet)
            elif circle_rect_collision(bullet.x, bullet.y, bullet.radius, p.rect):
                self.bullets.remove(bullet)
                self.hurt_player(1)

    def update_interactions(self):
        p, room = self.player, self.room
        pr = p.rect

        for pickup in room.pickups[:]:
            if not pr.colliderect(pickup.rect):
                continue
            if pickup.kind == "heart":
                if p.hp < p.max_hp:
                    p.hp = min(p.max_hp, p.hp + 2)
                    room.pickups.remove(pickup)
            elif pickup.kind == "bomb":
                p.bombs = min(99, p.bombs + 1)
                room.pickups.remove(pickup)
            else:
                p.keys = min(99, p.keys + 1)
                room.pickups.remove(pickup)

        for item in room.items[:]:
            if pr.colliderect(item.rect):
                apply_item(p, item.item_id)
                room.items.remove(item)
                data = ITEMS[item.item_id]
                self.show_banner(data["name"], data["desc"], 170)

        for chest in room.chests:
            if chest.opened or not pr.inflate(4, 4).colliderect(chest.rect):
                continue
            if chest.kind == "gold":
                if p.keys > 0:
                    p.keys -= 1
                    self.open_chest(room, chest)
                else:
                    self.show_banner("BAU DOURADO", "Precisa de uma chave", 90, only_if_empty=True)
            else:
                self.open_chest(room, chest)

        if room.hatch and pr.colliderect(room.hatch):
            self.next_floor()


# ----------------------------------------------------------------------------
# Desenho
# ----------------------------------------------------------------------------
PAUSE_RECT = pygame.Rect(VIRTUAL_WIDTH // 2 - 7, 4, 14, 14)


def draw_room(surface, room, rooms):
    surface.fill(COLORS["background"])
    pygame.draw.rect(surface, COLORS["floor"], ROOM)

    # Pequenas marcas no chao para dar textura sem poluir a sala.
    for y in range(ROOM.top + 8, ROOM.bottom - 4, 16):
        for x in range(ROOM.left + 8, ROOM.right - 4, 16):
            if ((x // 16) + (y // 16)) % 3 == 0:
                pygame.draw.rect(surface, COLORS["floor_alt"], (x, y, 2, 2))

    pygame.draw.rect(surface, COLORS["wall_edge"], ROOM, 3)
    pygame.draw.rect(surface, COLORS["wall"], ROOM.inflate(-6, -6), 2)

    for rock in room.rocks:
        pygame.draw.rect(surface, COLORS["rock_dark"], rock.move(0, 2))
        pygame.draw.rect(surface, COLORS["rock"], rock)
        pygame.draw.rect(surface, COLORS["rock_light"], (rock.x + 2, rock.y + 2, rock.w - 6, 3))

    # Portas: fechadas (grade vermelha) ate limpar a sala; douradas se o destino esta trancado.
    for direction, target_pos in room.neighbors.items():
        rect = door_trigger(direction)
        if not room.cleared:
            pygame.draw.rect(surface, COLORS["door_closed"], rect)
            if direction in ("N", "S"):
                for bx in range(rect.left + 3, rect.right - 2, 6):
                    pygame.draw.rect(surface, COLORS["door_bar"], (bx, rect.top, 2, rect.height))
            else:
                for by in range(rect.top + 3, rect.bottom - 2, 6):
                    pygame.draw.rect(surface, COLORS["door_bar"], (rect.left, by, rect.width, 2))
        elif rooms[target_pos].locked:
            pygame.draw.rect(surface, COLORS["door_locked"], rect)
            hole = pygame.Rect(0, 0, 4, 4)
            hole.center = rect.center
            pygame.draw.rect(surface, COLORS["panel"], hole)
        else:
            pygame.draw.rect(surface, COLORS["door_open"], rect)

    if room.hatch:
        pygame.draw.rect(surface, COLORS["rock_dark"], room.hatch.inflate(4, 4))
        pygame.draw.rect(surface, COLORS["panel"], room.hatch)
        for i in range(4):
            pygame.draw.rect(surface, COLORS["rock_light"],
                             (room.hatch.x + 2 + i, room.hatch.y + 2 + i * 4, room.hatch.w - 4 - i * 2, 2))


def draw_hud(surface, game):
    player, room = game.player, game.room

    label = FONT_SMALL.render("VIDA", True, COLORS["white"])
    surface.blit(label, (ROOM.left + 3, 6))

    for i in range(player.max_hp // 2):
        x = ROOM.left + 31 + i * 13
        full = player.hp >= (i + 1) * 2
        half = player.hp == i * 2 + 1
        pygame.draw.rect(surface, COLORS["red"] if full else COLORS["dark_red"], (x, 7, 10, 8))
        if half:
            pygame.draw.rect(surface, COLORS["red"], (x, 7, 5, 8))
        if full or half:
            pygame.draw.rect(surface, COLORS["white"], (x + 2, 8, 2, 2))

    # Chaves e bombas
    draw_key_icon(surface, 148, 6)
    surface.blit(FONT_SMALL.render(f"x{player.keys}", True, COLORS["white"]), (161, 6))
    draw_bomb_icon(surface, 184, 5)
    surface.blit(FONT_SMALL.render(f"x{player.bombs}", True, COLORS["white"]), (196, 6))

    # Botao de pausa
    pygame.draw.rect(surface, COLORS["panel"], PAUSE_RECT)
    pygame.draw.rect(surface, COLORS["wall_edge"], PAUSE_RECT, 1)
    pygame.draw.rect(surface, COLORS["white"], (PAUSE_RECT.x + 4, PAUSE_RECT.y + 3, 2, 8))
    pygame.draw.rect(surface, COLORS["white"], (PAUSE_RECT.x + 8, PAUSE_RECT.y + 3, 2, 8))

    surface.blit(FONT_SMALL.render(f"ANDAR {game.floor}", True, COLORS["grey"]), (262, 6))

    if room.cleared:
        status = FONT_SMALL.render("PORTAS ABERTAS", True, COLORS["gold"])
    else:
        status = FONT_SMALL.render(f"INIMIGOS: {len(room.enemies)}", True, COLORS["white"])
    surface.blit(status, (ROOM.right - status.get_width() - 3, 6))

    # Barra de vida do boss
    for enemy in room.enemies:
        if enemy.is_boss:
            surface.blit(FONT_SMALL.render(enemy.name, True, COLORS["white"]), (ROOM.left + 3, 305))
            bar = pygame.Rect(120, 306, 300, 6)
            pygame.draw.rect(surface, COLORS["dark_red"], bar)
            fill = bar.copy()
            fill.width = int(bar.width * max(0, enemy.health) / enemy.max_health)
            pygame.draw.rect(surface, COLORS["red"], fill)
            pygame.draw.rect(surface, COLORS["wall_edge"], bar, 1)
            break


def draw_minimap(surface, game):
    """Mapa no canto superior direito: salas vistas, sala atual, boss (vermelho) e tesouro (dourado)."""
    x0, y0 = ROOM.right - 53, ROOM.top + 3
    panel = pygame.Surface((51, 37), pygame.SRCALPHA)
    panel.fill((10, 8, 15, 150))
    surface.blit(panel, (x0 - 1, y0 - 1))

    seen = set()
    for pos, room in game.rooms.items():
        if room.visited:
            seen.add(pos)
            seen.update(room.neighbors.values())

    for pos in seen:
        room = game.rooms[pos]
        rect = pygame.Rect(x0 + (pos[0] + 3) * 7, y0 + (pos[1] + 3) * 5, 6, 4)
        if pos == game.room.position:
            color = COLORS["white"]
        elif room.visited:
            color = COLORS["grey"]
        else:
            color = COLORS["dim"]
        pygame.draw.rect(surface, color, rect)
        marker = None
        if room.role == "boss":
            marker = COLORS["red"]
        elif room.role == "treasure":
            marker = COLORS["gold"]
        if marker:
            pygame.draw.rect(surface, marker, (rect.x + 2, rect.y + 1, 2, 2))


def draw_banner(surface, banner):
    title, sub, _ = banner
    t = FONT_HINT.render(title, True, COLORS["gold"])
    s = FONT_SMALL.render(sub, True, COLORS["white"]) if sub else None
    w = max(t.get_width(), s.get_width() if s else 0) + 14
    h = 24 if s else 16
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((10, 8, 15, 190))
    px = VIRTUAL_WIDTH // 2 - w // 2
    surface.blit(panel, (px, ROOM.top + 8))
    surface.blit(t, (VIRTUAL_WIDTH // 2 - t.get_width() // 2, ROOM.top + 10))
    if s:
        surface.blit(s, (VIRTUAL_WIDTH // 2 - s.get_width() // 2, ROOM.top + 22))


def draw_game_over(surface):
    overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
    overlay.fill((10, 8, 15, 190))
    surface.blit(overlay, (0, 0))
    title = FONT_BIG.render("VOCE MORREU", True, COLORS["white"])
    hint = FONT_HINT.render("Segure R por 1 segundo para tentar novamente", True, COLORS["gold"])
    surface.blit(title, title.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 - 12)))
    surface.blit(hint, hint.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 + 14)))


def pause_menu_buttons():
    cx = VIRTUAL_WIDTH // 2
    entries = [("CONTINUAR", "resume"), ("REINICIAR", "restart"), ("SAIR", "quit")]
    return [(label, pygame.Rect(cx - 55, 120 + i * 24, 110, 18), action)
            for i, (label, action) in enumerate(entries)]


def draw_pause(surface, mouse):
    overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
    overlay.fill((10, 8, 15, 200))
    surface.blit(overlay, (0, 0))
    title = FONT_BIG.render("PAUSADO", True, COLORS["white"])
    surface.blit(title, title.get_rect(center=(VIRTUAL_WIDTH // 2, 95)))
    for label, rect, _ in pause_menu_buttons():
        hover = rect.collidepoint(mouse)
        pygame.draw.rect(surface, COLORS["wall_edge"] if hover else COLORS["panel"], rect)
        pygame.draw.rect(surface, COLORS["wall_edge"], rect, 1)
        text = FONT_HINT.render(label, True, COLORS["gold"] if hover else COLORS["white"])
        surface.blit(text, text.get_rect(center=rect.center))
    hint = FONT_SMALL.render("P / ESC: continuar    Segure R: reiniciar", True, COLORS["grey"])
    surface.blit(hint, hint.get_rect(center=(VIRTUAL_WIDTH // 2, 205)))


def draw_restart_bar(surface, progress):
    w, h = 120, 8
    x = VIRTUAL_WIDTH // 2 - w // 2
    y = VIRTUAL_HEIGHT // 2 + 38
    text = FONT_SMALL.render("REINICIANDO...", True, COLORS["white"])
    surface.blit(text, text.get_rect(center=(VIRTUAL_WIDTH // 2, y - 8)))
    pygame.draw.rect(surface, COLORS["panel"], (x - 1, y - 1, w + 2, h + 2))
    pygame.draw.rect(surface, COLORS["gold"], (x, y, int(w * clamp(progress, 0, 1)), h))
    pygame.draw.rect(surface, COLORS["wall_edge"], (x - 1, y - 1, w + 2, h + 2), 1)


def render(game, paused, mouse, restart_progress):
    room = game.room
    draw_room(canvas, room, game.rooms)

    for chest in room.chests:
        chest.draw(canvas)
    for pickup in room.pickups:
        pickup.draw(canvas)
    for item in room.items:
        item.draw(canvas)
    for bomb in game.bombs:
        bomb.draw(canvas)
    for tear in game.tears:
        tear.draw(canvas)
    # Terrestres primeiro, voadores por cima.
    for enemy in sorted(room.enemies, key=lambda e: e.flying):
        enemy.draw(canvas)
    for bullet in game.bullets:
        bullet.draw(canvas)
    game.player.draw(canvas)
    for explosion in game.explosions:
        explosion.draw(canvas)

    draw_hud(canvas, game)
    draw_minimap(canvas, game)
    if game.banner:
        draw_banner(canvas, game.banner)

    if game.game_over:
        draw_game_over(canvas)
    elif paused:
        draw_pause(canvas, mouse)

    if restart_progress is not None:
        draw_restart_bar(canvas, restart_progress)

    pygame.transform.scale(canvas, (WIDTH, HEIGHT), screen)
    pygame.display.flip()


# ----------------------------------------------------------------------------
# Loop principal
# ----------------------------------------------------------------------------
def main():
    game = Game()
    paused = False
    running = True
    r_since = None      # instante em que R foi pressionado
    r_locked = False    # evita reiniciar de novo enquanto R continua segurado

    while running:
        clock.tick(FPS)
        now = pygame.time.get_ticks()
        mx, my = pygame.mouse.get_pos()
        mouse = (mx // SCALE, my // SCALE)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_p):
                    if game.game_over:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                    else:
                        paused = not paused
                elif event.key in (pygame.K_e, pygame.K_SPACE):
                    if not paused and not game.game_over:
                        game.place_bomb()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click = (event.pos[0] // SCALE, event.pos[1] // SCALE)
                if not game.game_over and PAUSE_RECT.collidepoint(click):
                    paused = not paused
                elif paused:
                    for _label, rect, action in pause_menu_buttons():
                        if rect.collidepoint(click):
                            if action == "resume":
                                paused = False
                            elif action == "restart":
                                game = Game()
                                paused = False
                            else:
                                running = False

        keys = pygame.key.get_pressed()

        # Segurar R por 1 segundo reinicia o jogo (vale na pausa e na tela de derrota tambem).
        restart_progress = None
        if keys[pygame.K_r]:
            if not r_locked:
                if r_since is None:
                    r_since = now
                held = now - r_since
                restart_progress = held / RESTART_HOLD_MS
                if held >= RESTART_HOLD_MS:
                    game = Game()
                    paused = False
                    r_since = None
                    r_locked = True
                    restart_progress = None
        else:
            r_since = None
            r_locked = False

        if not paused and not game.game_over:
            game.update(keys)

        render(game, paused, mouse, restart_progress)

    pygame.quit()


if __name__ == "__main__":
    main()