import colorsys
import math
import random
import pygame

# Meu Roguelike - prototipo jogavel (versao 4)
#
# CONTROLES
#   WASD ........ movimenta          Setas ....... atiram
#   E / ESPACO .. coloca bomba       Q / SHIFT ... usa o item ativo
#   P / ESC ..... pausa (ou botao de pausa no topo)
#   Segurar R ... reinicia o jogo apos 1 segundo
#
# REGRAS
#   - A horda de cada sala nasce uma unica vez; as portas so abrem quando todos morrem.
#   - Sala do tesouro (porta dourada): precisa de chave. Bau dourado tambem gasta chave.
#   - SALAS SECRETAS (como em The Binding of Isaac): nao tem porta. Exploda uma bomba
#     perto do meio de uma parede para abrir a passagem.
#       * Sala secreta ........ fica entre 2 ou mais salas e guarda varios pickups.
#       * Super sala secreta .. fica colada em UMA sala so e guarda uma melhoria.
#   - SALA DO DEMONIO (porta vermelha) e SALA DO ANJO (porta branca): aparecem em TODO
#     andar, coladas na sala do boss (ou em outra sala se nao houver espaco).
#       * Demonio: cada pacto custa CORACOES DE VIDA MAXIMA (nunca te mata: sobra ao menos 1).
#       * Anjo: bencaos de graca, mas voce so pode escolher UMA.
#   - ITENS ATIVOS: ficam guardados em um unico espaco, gastam cargas e recarregam
#     ao limpar salas (boss e mini boss recarregam mais). Pegar outro ativo troca o antigo.
#   - MINI BOSSES: versoes menores dos bosses que aparecem sozinhos em salas aleatorias.
#   - Inimigos podem nascer MUTANTES: mudam de cor e ganham poderes novos.
#   - A cada 2 andares nasce um novo inimigo personalizado, com habilidades combinadas.
#   - A cada andar os inimigos ficam mais fortes, rapidos e numerosos.

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
    "floor_secret": (46, 40, 72),
    "floor_super": (68, 40, 62),
    "floor_boss": (62, 44, 52),
    "floor_treasure": (66, 58, 44),
    "floor_devil": (66, 28, 36),
    "floor_angel": (70, 76, 100),
    "shadow": (40, 35, 48),
    "wall": (26, 24, 34),
    "wall_edge": (104, 83, 103),
    "secret_edge": (190, 120, 255),
    "devil_edge": (210, 50, 62),
    "angel_edge": (225, 232, 255),
    "player": (90, 174, 235),
    "player_light": (183, 229, 255),
    "enemy": (185, 75, 91),
    "enemy_light": (255, 151, 145),
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
    "door_devil": (190, 36, 48),
    "door_angel": (225, 232, 255),
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
MIN_MAX_HP = 2                # o demonio nunca deixa voce abaixo de 1 coracao

DIRECTIONS = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
DIR_BY_VECTOR = {v: k for k, v in DIRECTIONS.items()}


def mix(c1, c2, t):
    """Mistura duas cores RGB (t=0 -> c1, t=1 -> c2)."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# ----------------------------------------------------------------------------
# Inimigos: cada tipo e uma "ficha" de habilidades
#   move    : chase | kite (mantem distancia) | orbit (circula) | dash (investida) | static
#   attacks : shoot (tiro mirado) | spread (leque de 3) | ring (anel de balas)
#   death   : explode | split          passive : regen | teleport
# ----------------------------------------------------------------------------
ENEMY_SPECS = {
    "fly": {"name": "Mosca", "health": 2, "speed": 1.05, "damage": 1, "size": 10, "flying": True,
            "move": "chase", "attacks": [], "death": [], "passive": [], "shape": "fly",
            "color": (120, 140, 80), "light": (205, 225, 245), "weight": 4, "min_floor": 1},
    "chaser": {"name": "Perseguidor", "health": 3, "speed": 0.72, "damage": 1, "size": 13, "flying": False,
               "move": "chase", "attacks": [], "death": [], "passive": [], "shape": "box",
               "color": (185, 75, 91), "light": (255, 151, 145), "weight": 4, "min_floor": 1},
    "tank": {"name": "Tanque", "health": 8, "speed": 0.40, "damage": 2, "size": 18, "flying": False,
             "move": "chase", "attacks": [], "death": [], "passive": [], "shape": "tank",
             "color": (110, 72, 140), "light": (166, 128, 196), "weight": 1, "min_floor": 1},
    "shooter": {"name": "Atirador", "health": 3, "speed": 0.55, "damage": 1, "size": 13, "flying": False,
                "move": "kite", "attacks": ["shoot"], "death": [], "passive": [], "shape": "cannon",
                "color": (80, 150, 170), "light": (160, 220, 230), "weight": 3, "min_floor": 1},
    "dasher": {"name": "Investida", "health": 3, "speed": 0.60, "damage": 1, "size": 13, "flying": False,
               "move": "dash", "attacks": [], "death": [], "passive": [], "shape": "horn",
               "color": (200, 120, 60), "light": (250, 190, 120), "weight": 3, "min_floor": 1},
    "wasp": {"name": "Vespa", "health": 2, "speed": 0.90, "damage": 1, "size": 10, "flying": True,
             "move": "orbit", "attacks": ["shoot"], "death": [], "passive": [], "shape": "fly",
             "color": (230, 190, 40), "light": (255, 240, 170), "weight": 2, "min_floor": 2},
    "bomber": {"name": "Bombardeiro", "health": 2, "speed": 1.00, "damage": 1, "size": 12, "flying": False,
               "move": "chase", "attacks": [], "death": ["explode"], "passive": [], "shape": "round",
               "color": (230, 100, 40), "light": (255, 190, 110), "weight": 2, "min_floor": 2},
    "slime": {"name": "Gosma", "health": 4, "speed": 0.50, "damage": 1, "size": 14, "flying": False,
              "move": "chase", "attacks": [], "death": ["split"], "passive": [], "shape": "round",
              "color": (90, 190, 110), "light": (170, 240, 170), "weight": 2, "min_floor": 2},
    "turret": {"name": "Torreta", "health": 6, "speed": 0.0, "damage": 1, "size": 14, "flying": False,
               "move": "static", "attacks": ["ring"], "death": [], "passive": [], "shape": "turret",
               "color": (110, 110, 130), "light": (170, 170, 190), "weight": 1, "min_floor": 3},
    "mage": {"name": "Mago", "health": 4, "speed": 0.50, "damage": 1, "size": 14, "flying": False,
             "move": "kite", "attacks": ["spread"], "death": [], "passive": ["teleport"], "shape": "mage",
             "color": (120, 90, 200), "light": (190, 160, 255), "weight": 2, "min_floor": 4},
}
for _id, _spec in ENEMY_SPECS.items():
    _spec["id"] = _id

# Filhote criado quando uma Gosma / inimigo "mitose" morre.
MINI_SPEC = {"id": "mini", "name": "Filhote", "health": 1, "speed": 1.10, "damage": 1, "size": 8,
             "flying": False, "move": "chase", "attacks": [], "death": [], "passive": [],
             "shape": "round", "color": (90, 190, 110), "light": (170, 240, 170),
             "weight": 0, "min_floor": 99}

# Mutacoes: mudam a cor do inimigo e dao novas funcoes.
MUTATIONS = {
    "fast": {"name": "Veloz", "color": (255, 225, 80)},
    "armored": {"name": "Blindado", "color": (150, 175, 210)},
    "explosive": {"name": "Explosivo", "color": (255, 140, 40)},
    "regen": {"name": "Regenerador", "color": (90, 225, 120)},
    "splitting": {"name": "Mitose", "color": (200, 110, 245)},
    "gunner": {"name": "Pistoleiro", "color": (255, 90, 120)},
}

TRAIT_WORDS = {"dash": "Investida", "orbit": "Orbital", "kite": "Franco", "shoot": "Atirador",
               "spread": "Dispersor", "ring": "Pulsar", "regen": "Regenerante",
               "teleport": "Fantasma", "explode": "Explosivo", "split": "Mitotico"}
BODY_WORDS = ["Larva", "Golem", "Espectro", "Casulo", "Verme", "Sentinela"]


def roll_mutations(floor):
    chance = min(0.6, 0.06 + 0.07 * (floor - 1))
    if random.random() >= chance:
        return []
    count = 2 if floor >= 5 and random.random() < 0.25 else 1
    return random.sample(list(MUTATIONS), count)


def generate_custom_enemy(floor):
    """A cada 2 andares: cria um inimigo novo combinando habilidades (mais habilidades quanto mais fundo)."""
    tier = max(1, floor // 2)
    flying = random.random() < 0.4
    moves = ["orbit"] if flying else ["dash", "orbit", "kite"]
    pool = ([("move", m) for m in moves]
            + [("attacks", a) for a in ("shoot", "spread", "ring")]
            + [("passive", p) for p in ("regen", "teleport")]
            + [("death", d) for d in ("explode", "split")])
    chosen = random.sample(pool, min(len(pool), min(4, 1 + tier)))

    spec = {"move": "chase", "attacks": [], "death": [], "passive": []}
    for category, value in chosen:
        if category == "move":
            spec["move"] = value
        else:
            spec[category].append(value)
    traits = ([spec["move"]] if spec["move"] != "chase" else []) \
        + spec["attacks"] + spec["passive"] + spec["death"]

    hue = random.random()
    body = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.65, 0.85))
    light = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.30, 1.00))
    word = TRAIT_WORDS[traits[0]] if traits else "Comum"
    spec.update({
        "id": f"custom_{floor}",
        "tier": tier,
        "name": f"{random.choice(BODY_WORDS)} {word}",
        "desc": ", ".join(TRAIT_WORDS[t].lower() for t in traits),
        "health": (3 + tier * 1.5) * (0.7 if flying else 1.0),
        "speed": random.uniform(0.55, 0.95) + (0.25 if flying else 0.0),
        "damage": 1 + (1 if tier >= 3 else 0),
        "size": random.randint(10, 12) if flying else random.randint(12, 16),
        "flying": flying,
        "shape": "fly" if flying else random.choice(["box", "round", "horn", "cannon"]),
        "color": body, "light": light,
        "weight": 3 + tier, "min_floor": 1,
    })
    return spec


# ----------------------------------------------------------------------------
# Melhorias do personagem (stats + efeitos nos tiros)
# ----------------------------------------------------------------------------
FX_COLORS = {
    "fire": (255, 140, 50),
    "ice": (190, 240, 255),
    "poison": (120, 230, 90),
    "pierce": (255, 255, 150),
    "homing": (255, 120, 220),
    "bounce": (255, 200, 120),
}

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
    # --- efeitos nos tiros ---
    "fire": {"name": "TIROS DE FOGO", "desc": "queima os inimigos com o tempo",
             "glyph": "F", "color": FX_COLORS["fire"], "stats": {}, "fx": "fire"},
    "ice": {"name": "TIROS DE GELO", "desc": "deixa os inimigos lentos",
            "glyph": "I", "color": FX_COLORS["ice"], "stats": {}, "fx": "ice"},
    "poison": {"name": "TIROS VENENOSOS", "desc": "envenena: dano longo e constante",
               "glyph": "P", "color": FX_COLORS["poison"], "stats": {}, "fx": "poison"},
    "pierce": {"name": "TIROS PERFURANTES", "desc": "atravessam os inimigos",
               "glyph": "X", "color": FX_COLORS["pierce"], "stats": {}, "fx": "pierce"},
    "homing": {"name": "TIROS TELEGUIADOS", "desc": "perseguem o inimigo mais proximo",
               "glyph": "T", "color": FX_COLORS["homing"], "stats": {}, "fx": "homing"},
    "bounce": {"name": "TIROS SALTITANTES", "desc": "quicam nas paredes",
               "glyph": "S", "color": FX_COLORS["bounce"], "stats": {}, "fx": "bounce"},
    # --- utilidade ---
    "map": {"name": "MAPA ANTIGO", "desc": "revela o mapa e as salas secretas",
            "glyph": "?", "color": (200, 170, 120), "stats": {}, "flag": "map"},
}

# Itens que so aparecem na Sala do Demonio (custam vida maxima; cost esta em "meios coracoes").
DEVIL_ITEMS = {
    "bloodlens": {"name": "LENTE DE SANGUE", "desc": "+2 de dano dos tiros",
                  "glyph": "L", "color": (170, 30, 50), "stats": {"damage": 2},
                  "devil_only": True, "cost": 2},
    "hellfire": {"name": "GATILHO INFERNAL", "desc": "+1 dano e tiro muito mais rapido",
                 "glyph": "H", "color": (255, 90, 40), "stats": {"damage": 1, "cooldown": -5},
                 "devil_only": True, "cost": 4},
    "trident": {"name": "TRIDENTE", "desc": "tiro triplo em chamas",
                "glyph": "Y", "color": (200, 40, 40), "stats": {"shots": 2}, "fx": "fire",
                "devil_only": True, "cost": 4},
}

# Itens ATIVOS: ocupam um unico espaco, gastam "charges" e recarregam ao limpar salas.
ACTIVES = {
    "bombbox": {"name": "CAIXA DE BOMBAS", "desc": "[Q] invoca bombas ao seu redor",
                "glyph": "O", "color": (150, 150, 170), "stats": {},
                "active": True, "charges": 3, "effect": "bombs"},
    "masterkey": {"name": "CHAVE MESTRA", "desc": "[Q] abre portas e baus trancados",
                  "glyph": "K", "color": (246, 201, 91), "stats": {},
                  "active": True, "charges": 2, "effect": "keys"},
    "fury": {"name": "FURIA", "desc": "[Q] dano x2 por 10 segundos",
             "glyph": "R", "color": (230, 70, 60), "stats": {},
             "active": True, "charges": 3, "effect": "fury"},
    "shield": {"name": "ESCUDO ARCANO", "desc": "[Q] invulneravel por 5 segundos",
               "glyph": "E", "color": (140, 200, 255), "stats": {},
               "active": True, "charges": 4, "effect": "shield"},
    "shockwave": {"name": "ONDA DE CHOQUE", "desc": "[Q] fere todos da sala e limpa balas",
                  "glyph": "W", "color": (200, 160, 255), "stats": {},
                  "active": True, "charges": 4, "effect": "blast"},
}
ITEMS.update(DEVIL_ITEMS)
ITEMS.update(ACTIVES)

# O que o anjo pode oferecer de graca (alem de um ativo).
ANGEL_POOL = ["homing", "goldheart", "container", "amulet", "ice", "range", "double", "pierce",
              "trigger", "lens"]

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
# Status (queimar, envenenar, congelar) - compartilhado por inimigos e bosses
# ----------------------------------------------------------------------------
class Combatant:
    def init_status(self):
        self.burn = 0
        self.poison = 0
        self.slow = 0
        self.status_clock = 0

    def apply_fx(self, fx):
        if "fire" in fx:
            self.burn = 120
        if "ice" in fx:
            self.slow = 120
        if "poison" in fx:
            self.poison = 240

    @property
    def speed_mult(self):
        return 0.5 if self.slow > 0 else 1.0

    def tick_status(self):
        """Avanca os status e devolve o dano causado neste frame."""
        self.status_clock += 1
        damage = 0.0
        if self.burn > 0:
            self.burn -= 1
            if self.status_clock % 30 == 0:
                damage += 1.0
        if self.poison > 0:
            self.poison -= 1
            if self.status_clock % 20 == 0:
                damage += 0.5
        if self.slow > 0:
            self.slow -= 1
        return damage

    def status_color(self):
        if self.burn > 0:
            return FX_COLORS["fire"]
        if self.poison > 0:
            return FX_COLORS["poison"]
        if self.slow > 0:
            return FX_COLORS["ice"]
        return None


# ----------------------------------------------------------------------------
# Projeteis, bombas e efeitos
# ----------------------------------------------------------------------------
class Tear:
    def __init__(self, x, y, dx, dy, damage, speed, life, fx=frozenset()):
        self.x = float(x)
        self.y = float(y)
        self.dx = dx
        self.dy = dy
        self.damage = damage
        self.speed = speed
        self.radius = 3
        self.life = life
        self.fx = fx
        self.hit = set()
        self.bounces = 0
        colors = [FX_COLORS[f] for f in fx if f in FX_COLORS]
        if colors:
            self.color = tuple(sum(c[i] for c in colors) // len(colors) for i in range(3))
        else:
            self.color = COLORS["tear"]

    def update(self, enemies):
        if "homing" in self.fx and enemies:
            target = min(enemies, key=lambda e: (e.x - self.x) ** 2 + (e.y - self.y) ** 2)
            tx, ty = target.x - self.x, target.y - self.y
            d = math.hypot(tx, ty) or 1.0
            self.dx += tx / d * 0.14
            self.dy += ty / d * 0.14
            n = math.hypot(self.dx, self.dy) or 1.0
            self.dx, self.dy = self.dx / n, self.dy / n
        self.x += self.dx * self.speed
        self.y += self.dy * self.speed
        self.life -= 1

    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        pygame.draw.circle(surface, self.color, (x, y), self.radius)
        pygame.draw.rect(surface, COLORS["white"], (x - 1, y - 2, 2, 2))


class Bullet:
    """Projetil inimigo."""

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

    def __init__(self, x, y, radius=BOMB_RADIUS):
        self.x = x
        self.y = y
        self.radius = radius
        self.life = self.LIFE

    def draw(self, surface):
        progress = 1 - self.life / self.LIFE
        radius = int(self.radius * (0.4 + 0.6 * progress))
        pos = (round(self.x), round(self.y))
        pygame.draw.circle(surface, COLORS["fuse"], pos, radius)
        pygame.draw.circle(surface, COLORS["gold"], pos, int(radius * 0.7))
        if self.life > self.LIFE // 2:
            pygame.draw.circle(surface, COLORS["white"], pos, int(radius * 0.35))


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
    """Melhoria do personagem flutuando sobre um pedestal.
       cost  : vida maxima cobrada (em meios coracoes) - usado na Sala do Demonio
       group : itens do mesmo grupo somem quando um deles e pego - usado na Sala do Anjo"""

    def __init__(self, x, y, item_id, cost=0, group=None):
        self.x = float(x)
        self.y = float(y)
        self.item_id = item_id
        self.cost = cost
        self.group = group
        self.armed = True     # item largado pela troca de ativo so volta a valer depois que voce sai de cima
        self.near = False     # mostra nome e descricao quando o jogador esta perto
        self.rect = pygame.Rect(round(x) - 8, round(y) - 8, 16, 16)

    def draw(self, surface):
        data = ITEMS[self.item_id]
        x, y = round(self.x), round(self.y)
        bob = round(math.sin(pygame.time.get_ticks() / 220) * 2)
        pygame.draw.rect(surface, COLORS["rock_dark"], (x - 9, y + 5, 18, 5))
        pygame.draw.rect(surface, COLORS["rock"], (x - 8, y + 4, 16, 4))
        pygame.draw.rect(surface, COLORS["panel"], (x - 7, y - 8 + bob, 14, 14))
        pygame.draw.rect(surface, data["color"], (x - 6, y - 7 + bob, 12, 12))
        if data.get("active"):
            pygame.draw.rect(surface, COLORS["gold"], (x - 8, y - 9 + bob, 16, 16), 1)
        glyph = FONT_SMALL.render(data["glyph"], True, COLORS["panel"])
        surface.blit(glyph, glyph.get_rect(center=(x, y - 1 + bob)))

        if self.cost:
            draw_heart_icon(surface, x - 9, y + 11)
            price = FONT_SMALL.render(f"-{self.cost // 2}", True, COLORS["red"])
            surface.blit(price, (x + 1, y + 11))

        if self.near:
            name = FONT_SMALL.render(data["name"], True, COLORS["gold"])
            desc = FONT_SMALL.render(data["desc"], True, COLORS["white"])
            w = max(name.get_width(), desc.get_width()) + 8
            cx = clamp(x, w // 2 + 4, VIRTUAL_WIDTH - w // 2 - 4)
            top = y - 40 if y > 75 else y + 24
            panel = pygame.Surface((w, 22), pygame.SRCALPHA)
            panel.fill((10, 8, 15, 200))
            surface.blit(panel, (cx - w // 2, top))
            surface.blit(name, (cx - name.get_width() // 2, top + 2))
            surface.blit(desc, (cx - desc.get_width() // 2, top + 12))


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
            pygame.draw.rect(surface, COLORS["white"] if gold else COLORS["gold"], (x - 1, y - 6, 2, 12))
            pygame.draw.rect(surface, COLORS["panel"], (x - 2, y - 1, 4, 3))


# ----------------------------------------------------------------------------
# Inimigos
# ----------------------------------------------------------------------------
class Enemy(Combatant):
    is_boss = False

    def __init__(self, x, y, spec, floor=1, mutations=()):
        self.spec = spec
        self.name = spec["name"]
        self.x = float(x)
        self.y = float(y)
        self.size = spec["size"]
        self.flying = spec["flying"]
        self.floor = floor
        self.mutations = list(mutations)

        # Dificuldade cresce a cada andar: vida, velocidade e dano.
        health = max(1.0, spec["health"] * (1 + 0.2 * (floor - 1)))
        self.speed = spec["speed"] * min(1.45, 1 + 0.04 * (floor - 1))
        self.damage = spec["damage"] + (1 if floor >= 6 else 0) + (1 if floor >= 11 else 0)

        self.move = spec["move"]
        self.attacks = list(spec["attacks"])
        self.death = list(spec["death"])
        self.passive = list(spec["passive"])

        for m in self.mutations:
            if m == "fast":
                self.speed *= 1.45
            elif m == "armored":
                health *= 1.8
                self.speed *= 0.85
            elif m == "explosive" and "explode" not in self.death:
                self.death.append("explode")
            elif m == "regen" and "regen" not in self.passive:
                self.passive.append("regen")
            elif m == "splitting" and "split" not in self.death:
                self.death.append("split")
            elif m == "gunner" and "shoot" not in self.attacks:
                self.attacks.append("shoot")

        self.health = health
        self.max_health = health

        self.bullet_speed = min(2.4, 1.4 + 0.04 * floor)
        self.interval = max(50, 125 - 6 * (floor - 1))
        if self.move == "static":
            self.interval = int(self.interval * 1.3)
        self.attack_timer = random.randint(50, self.interval + 30)
        self.attack_index = 0
        self.dash_state = "idle"
        self.dash_timer = random.randint(40, 90)
        self.vx = 0.0
        self.vy = 0.0
        self.teleport_timer = random.randint(120, 220)
        self.regen_timer = 0
        self.flash = 0
        self.age = random.randint(0, 100)
        self.phase = random.uniform(0, math.tau)
        self.aim = (0.0, 1.0)
        self.telegraph = False
        self.init_status()

    @property
    def rect(self):
        return pygame.Rect(round(self.x - self.size / 2),
                           round(self.y - self.size / 2),
                           self.size, self.size)

    # ---- comportamento ---------------------------------------------------------
    def _step(self, vx, vy, rocks):
        if self.flying:
            self.x += vx
            self.y += vy
        else:
            move_with_rocks(self, vx, vy, rocks)

    def update(self, player, rocks, others, bullets):
        self.age += 1
        self.flash = max(0, self.flash - 1)
        self.telegraph = False

        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        self.aim = (ux, uy)
        sm = self.speed_mult
        spd = self.speed * sm
        side = 1 if self.phase > math.pi else -1

        if self.move == "chase":
            if self.flying:
                wobble = math.sin(self.age * 0.08 + self.phase) * 0.7
                self.x += (ux - uy * wobble) * spd
                self.y += (uy + ux * wobble) * spd
            else:
                move_with_rocks(self, ux * spd, uy * spd, rocks)
        elif self.move == "kite":
            near_wall = (self.x < ROOM.left + 25 or self.x > ROOM.right - 25 or
                         self.y < ROOM.top + 25 or self.y > ROOM.bottom - 25)
            if dist > 115:
                vx, vy = ux, uy
            elif dist < 75 and not near_wall:
                vx, vy = -ux, -uy
            else:
                vx, vy = -uy * side, ux * side
            self._step(vx * spd, vy * spd, rocks)
        elif self.move == "orbit":
            radial = clamp((dist - 80) * 0.05, -1, 1)
            self._step((ux * radial - uy * side) * spd, (uy * radial + ux * side) * spd, rocks)
        elif self.move == "dash":
            self._update_dash(ux, uy, spd, sm, rocks)

        # Ataques
        dashing = self.move == "dash" and self.dash_state in ("windup", "dash")
        if self.attacks and not dashing:
            self.attack_timer -= sm
            if self.attack_timer < 14:
                self.telegraph = True
            if self.attack_timer <= 0:
                self._attack(ux, uy, bullets)
                self.attack_timer = self.interval + random.randint(-10, 20)

        # Passivas
        if "regen" in self.passive and self.health < self.max_health:
            self.regen_timer += 1
            if self.regen_timer >= 100:
                self.health = min(self.max_health, self.health + 1)
                self.regen_timer = 0
        if "teleport" in self.passive:
            self.teleport_timer -= 1
            if self.teleport_timer <= 0:
                self._teleport(player, rocks)
                self.teleport_timer = random.randint(150, 240)

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

    def _update_dash(self, ux, uy, spd, sm, rocks):
        self.dash_timer -= 1
        if self.dash_state == "idle":
            self._step(ux * spd * 0.6, uy * spd * 0.6, rocks)
            if self.dash_timer <= 0:
                self.dash_state, self.dash_timer = "windup", 35
        elif self.dash_state == "windup":
            self.telegraph = True
            if self.dash_timer <= 0:
                self.dash_state, self.dash_timer = "dash", 24
                self.vx, self.vy = ux * 3.8 * sm, uy * 3.8 * sm
        elif self.dash_state == "dash":
            self._step(self.vx, self.vy, rocks)
            if self.dash_timer <= 0:
                self.dash_state, self.dash_timer = "rest", 40
        else:  # rest
            if self.dash_timer <= 0:
                self.dash_state, self.dash_timer = "idle", random.randint(50, 90)

    def _attack(self, ux, uy, bullets):
        kind = self.attacks[self.attack_index % len(self.attacks)]
        self.attack_index += 1
        bs = self.bullet_speed
        angle = math.atan2(uy, ux)
        if kind == "shoot":
            bullets.append(Bullet(self.x, self.y, math.cos(angle) * bs, math.sin(angle) * bs))
        elif kind == "spread":
            for off in (-0.35, 0.0, 0.35):
                a = angle + off
                bullets.append(Bullet(self.x, self.y, math.cos(a) * bs, math.sin(a) * bs))
        else:  # ring
            fire_ring(bullets, self.x, self.y, 8, random.uniform(0, math.tau), bs)

    def _teleport(self, player, rocks):
        for _ in range(20):
            angle = random.uniform(0, math.tau)
            radius = random.uniform(70, 120)
            nx = clamp(player.x + math.cos(angle) * radius, ROOM.left + 15, ROOM.right - 15)
            ny = clamp(player.y + math.sin(angle) * radius, ROOM.top + 15, ROOM.bottom - 15)
            probe = pygame.Rect(round(nx - self.size / 2), round(ny - self.size / 2), self.size, self.size)
            if not self.flying and any(probe.colliderect(r) for r in rocks):
                continue
            self.x, self.y = nx, ny
            self.flash = 4
            self.attack_timer = min(self.attack_timer, 20)
            break

    # ---- desenho ---------------------------------------------------------------
    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        body, light = self.spec["color"], self.spec["light"]

        # A cor muda com mutacoes (alternando) e com status (fogo/veneno/gelo).
        tint = None
        if self.mutations:
            tint = MUTATIONS[self.mutations[(self.age // 40) % len(self.mutations)]]["color"]
        status = self.status_color()
        if status:
            tint = status
        if tint:
            t = 0.45 + 0.2 * math.sin(self.age * 0.15)
            body = mix(body, tint, t)
            light = mix(light, tint, t * 0.6)
        if self.flash or (self.telegraph and (self.age // 3) % 2 == 0):
            body = COLORS["white"]

        getattr(self, "_shape_" + self.spec["shape"])(surface, x, y, body, light)

        if self.mutations and (self.age // 8) % 3 != 0:
            outline = MUTATIONS[self.mutations[(self.age // 40) % len(self.mutations)]]["color"]
            pygame.draw.rect(surface, outline, self.rect.inflate(4, 4), 1)

        if self.health < self.max_health:
            w = max(8, self.size)
            top = y - self.size // 2 - 5
            pygame.draw.rect(surface, COLORS["dark_red"], (x - w // 2, top, w, 2))
            pygame.draw.rect(surface, COLORS["red"],
                             (x - w // 2, top, int(w * max(0, self.health) / self.max_health), 2))

    def _eyes(self, surface, x, y):
        pygame.draw.rect(surface, COLORS["dark_red"], (x - 4, y - 1, 2, 2))
        pygame.draw.rect(surface, COLORS["dark_red"], (x + 2, y - 1, 2, 2))

    def _shape_box(self, surface, x, y, body, light):
        h = self.size // 2
        pygame.draw.rect(surface, body, (x - h, y - h + 1, self.size, self.size - 1))
        pygame.draw.rect(surface, light, (x - h + 2, y - h, self.size - 4, 3))
        self._eyes(surface, x, y)

    def _shape_horn(self, surface, x, y, body, light):
        h = self.size // 2
        self._shape_box(surface, x, y, body, light)
        pygame.draw.rect(surface, light, (x - h, y - h - 3, 3, 5))
        pygame.draw.rect(surface, light, (x + h - 3, y - h - 3, 3, 5))

    def _shape_round(self, surface, x, y, body, light):
        h = self.size // 2
        pygame.draw.circle(surface, body, (x, y), h)
        pygame.draw.circle(surface, light, (x - h // 3, y - h // 3), max(1, h // 3))
        if h >= 6:
            self._eyes(surface, x, y + 1)

    def _shape_cannon(self, surface, x, y, body, light):
        h = self.size // 2
        self._shape_box(surface, x, y, body, light)
        ax, ay = self.aim
        pygame.draw.line(surface, light, (x, y), (round(x + ax * (h + 4)), round(y + ay * (h + 4))), 3)

    def _shape_turret(self, surface, x, y, body, light):
        h = self.size // 2
        pygame.draw.rect(surface, COLORS["rock_dark"], (x - h, y - h + 3, self.size, self.size - 3))
        pygame.draw.rect(surface, body, (x - h + 1, y - h + 2, self.size - 2, self.size - 4))
        ax, ay = self.aim
        pygame.draw.line(surface, light, (x, y), (round(x + ax * (h + 2)), round(y + ay * (h + 2))), 3)
        pygame.draw.circle(surface, light, (x, y), h - 3)

    def _shape_mage(self, surface, x, y, body, light):
        h = self.size // 2
        pygame.draw.polygon(surface, body, [(x, y - h - 3), (x - h, y + h), (x + h, y + h)])
        pygame.draw.rect(surface, light, (x - 2, y - h - 4, 4, 4))
        pygame.draw.rect(surface, COLORS["white"], (x - 3, y, 2, 2))
        pygame.draw.rect(surface, COLORS["white"], (x + 1, y, 2, 2))

    def _shape_tank(self, surface, x, y, body, light):
        pygame.draw.rect(surface, body, (x - 9, y - 8, 18, 17))
        pygame.draw.rect(surface, light, (x - 8, y - 9, 16, 4))
        pygame.draw.rect(surface, light, (x - 11, y - 4, 2, 3))
        pygame.draw.rect(surface, light, (x + 9, y - 4, 2, 3))
        pygame.draw.rect(surface, COLORS["dark_red"], (x - 5, y - 1, 3, 3))
        pygame.draw.rect(surface, COLORS["dark_red"], (x + 2, y - 1, 3, 3))

    def _shape_fly(self, surface, x, y, body, light):
        bob = round(math.sin(self.age * 0.15) * 2)
        pygame.draw.ellipse(surface, COLORS["shadow"], (x - 4, y + 7, 8, 3))
        wing_h = 3 + ((self.age // 4) % 2) * 2
        pygame.draw.rect(surface, COLORS["white"], (x - 9, y - 5 + bob, 5, wing_h))
        pygame.draw.rect(surface, COLORS["white"], (x + 4, y - 5 + bob, 5, wing_h))
        pygame.draw.circle(surface, body, (x, y + bob), 5)
        pygame.draw.circle(surface, light, (x - 1, y - 2 + bob), 1)
        pygame.draw.rect(surface, COLORS["red"], (x - 3, y - 1 + bob, 2, 2))
        pygame.draw.rect(surface, COLORS["red"], (x + 1, y - 1 + bob, 2, 2))


# ----------------------------------------------------------------------------
# Bosses (e mini bosses)
# ----------------------------------------------------------------------------
BOSS_INFO = {  # nome, tamanho, vida base, cor, cor clara
    "king": ("REI SLIME", 30, 40, (150, 60, 160), (206, 120, 214)),
    "bull": ("TOURO DE FERRO", 30, 40, (170, 110, 70), (222, 170, 120)),
    "wizard": ("MAGO SOMBRIO", 26, 34, (60, 60, 150), (130, 130, 230)),
    "eye": ("OLHO VIGILANTE", 30, 46, (200, 90, 90), (240, 200, 200)),
    "golem": ("GOLEM DE PEDRA", 36, 58, (100, 96, 110), (150, 146, 160)),
}
BOSS_KINDS = list(BOSS_INFO)
MINI_SCALE = 0.7


class Boss(Combatant):
    """5 bosses com padroes diferentes. Abaixo de 50% de vida ficam furiosos.
       king   - persegue, dispara aneis e invoca moscas.
       bull   - mira, investe e solta balas ao bater na parede.
       wizard - teleporta, dispara leques de balas e invoca atiradores.
       eye    - fica no centro disparando espirais e invoca moscas.
       golem  - pesado: pula e cria ondas de balas em anel.
       mini=True cria a versao reduzida: menor, com bem menos vida, menos dano e
       poucas invocacoes. Aparece sozinha em salas de combate aleatorias."""

    is_boss = True
    flying = False

    def __init__(self, x, y, kind, floor, mini=False):
        name, size, base_hp, color, light = BOSS_INFO[kind]
        self.mini = mini
        self.draw_size = size                     # tamanho "de desenho" (mini e reduzido na hora de desenhar)
        if mini:
            name = "MINI " + name
            size = int(size * MINI_SCALE)
            base_hp = max(10, int(base_hp * 0.4))
            hp_per_floor = 6
        else:
            hp_per_floor = 16
        self.kind = kind
        self.name = name
        self.size = size
        self.color = color
        self.light = light
        self.x = float(x)
        self.y = float(y)
        self.level = floor
        self.max_health = base_hp + hp_per_floor * (floor - 1)
        self.health = self.max_health
        self.damage = 1 if mini else 2
        self.bs = min(2.3, 1.4 + 0.04 * floor)      # velocidade das balas
        self.extra = (floor - 1) // (4 if mini else 2)   # balas extras por padrao
        self.flash = 0
        self.age = 0
        self.state = "idle"
        self.timer = 90
        self.summon_timer = 240
        self.cast_count = 0
        self.spin = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.aim = (0.0, 1.0)
        self.init_status()

    @property
    def rect(self):
        return pygame.Rect(round(self.x - self.size / 2), round(self.y - self.size / 2),
                           self.size, self.size)

    @property
    def enraged(self):
        return self.health <= self.max_health / 2

    @property
    def speed_mult(self):
        return 1.0  # bosses sao imunes a lentidao

    def apply_fx(self, fx):
        super().apply_fx(set(fx) - {"ice"})

    def update(self, player, rocks, others, bullets):
        self.age += 1
        self.flash = max(0, self.flash - 1)
        self._toward(player)
        getattr(self, "_update_" + self.kind)(player, others, bullets)
        half = self.size / 2
        self.x = clamp(self.x, ROOM.left + half, ROOM.right - half)
        self.y = clamp(self.y, ROOM.top + half, ROOM.bottom - half)

    def _toward(self, player):
        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy) or 1.0
        self.aim = (dx / d, dy / d)
        return self.aim

    def _summon(self, others, spec_id, count, cooldown, cap):
        self.summon_timer -= 1
        if self.summon_timer > 0:
            return
        if self.mini:
            count, cap, cooldown = 1, min(cap, 3), int(cooldown * 1.5)
        if len(others) < cap:
            for i in range(count):
                sx = (i - (count - 1) / 2) * 26
                others.append(Enemy(self.x + sx, self.y, ENEMY_SPECS[spec_id], self.level))
        self.summon_timer = cooldown

    # --- Rei Slime ---
    def _update_king(self, player, others, bullets):
        ux, uy = self.aim
        speed = 0.55 if self.enraged else 0.35
        self.x += ux * speed
        self.y += uy * speed
        self.timer -= 1
        if self.timer <= 0:
            count = (12 if self.enraged else 8) + self.extra
            fire_ring(bullets, self.x, self.y, count, self.age * 0.05, self.bs)
            self.timer = 70 if self.enraged else 100
        self._summon(others, "fly", 2, 300 if self.enraged else 420, 6)

    # --- Touro de Ferro ---
    def _update_bull(self, player, others, bullets):
        ux, uy = self.aim
        if self.state == "idle":
            self.x += ux * 0.5
            self.y += uy * 0.5
            self.timer -= 1
            if self.timer <= 0:
                self.state = "windup"
                self.timer = 30 if self.enraged else 40
        elif self.state == "windup":
            self.timer -= 1
            if self.timer <= 0:
                charge = 5.0 if self.enraged else 4.2
                self.vx, self.vy = ux * charge, uy * charge
                self.state = "charge"
        elif self.state == "charge":
            self.x += self.vx
            self.y += self.vy
            half = self.size / 2
            if (self.x <= ROOM.left + half or self.x >= ROOM.right - half or
                    self.y <= ROOM.top + half or self.y >= ROOM.bottom - half):
                count = (10 if self.enraged else 6) + self.extra
                fire_ring(bullets, self.x, self.y, count, self.age * 0.1, self.bs * 0.95)
                self.state = "stun"
                self.timer = 45
        elif self.state == "stun":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "idle"
                self.timer = 50 if self.enraged else 70

    # --- Mago Sombrio ---
    def _update_wizard(self, player, others, bullets):
        self.y += math.sin(self.age * 0.07) * 0.4
        self.timer -= 1
        if self.state == "idle" and self.timer <= 0:
            for _ in range(30):
                rx = random.randint(ROOM.left + 30, ROOM.right - 30)
                ry = random.randint(ROOM.top + 30, ROOM.bottom - 30)
                if math.hypot(rx - player.x, ry - player.y) > 90:
                    self.x, self.y = float(rx), float(ry)
                    break
            self.state = "cast"
            self.timer = 24
        elif self.state == "cast" and self.timer <= 0:
            self._toward(player)
            self.cast_count += 1
            base = math.atan2(self.aim[1], self.aim[0])
            n = 5 + self.extra + (2 if self.enraged else 0)
            for i in range(n):
                a = base + (i - (n - 1) / 2) * 0.22
                bullets.append(Bullet(self.x, self.y, math.cos(a) * self.bs, math.sin(a) * self.bs))
            if self.cast_count % 3 == 0:
                fire_ring(bullets, self.x, self.y, 10 + self.extra, self.age * 0.07, self.bs * 0.8)
            self.state = "idle"
            self.timer = 80 if self.enraged else 110
        self._summon(others, "shooter", 2, 380 if self.enraged else 520, 5)

    # --- Olho Vigilante ---
    def _update_eye(self, player, others, bullets):
        cx, cy = ROOM.center
        self.x = cx + math.sin(self.age * 0.02) * 70
        self.y = cy + math.cos(self.age * 0.027) * 40
        self.timer -= 1
        if self.state == "idle":
            if self.timer <= 0:
                self.state = "spiral"
                self.timer = 170 if self.enraged else 130
        elif self.state == "spiral":
            if self.age % 5 == 0:
                arms = (2 if self.enraged else 1) + (1 if self.extra >= 2 else 0)
                self.spin += 0.38
                for k in range(arms):
                    a = self.spin + k * math.tau / arms
                    bullets.append(Bullet(self.x, self.y, math.cos(a) * self.bs, math.sin(a) * self.bs))
            if self.timer <= 0:
                fire_ring(bullets, self.x, self.y, 12 + self.extra, self.age * 0.1, self.bs * 0.9)
                self.state = "rest"
                self.timer = 70
        elif self.state == "rest" and self.timer <= 0:
            self.state = "idle"
            self.timer = 30
        self._summon(others, "fly", 2, 300 if self.enraged else 400, 6)

    # --- Golem de Pedra ---
    def _update_golem(self, player, others, bullets):
        ux, uy = self.aim
        if self.state == "idle":
            speed = 0.45 if self.enraged else 0.3
            self.x += ux * speed
            self.y += uy * speed
            self.timer -= 1
            if self.timer <= 0:
                self.state = "windup"
                self.timer = 30 if self.enraged else 40
        elif self.state == "windup":
            self.timer -= 1
            if self.timer <= 0:
                count = 12 + self.extra * 2
                fire_ring(bullets, self.x, self.y, count, self.age * 0.1, self.bs)
                if self.enraged:
                    fire_ring(bullets, self.x, self.y, count, self.age * 0.1 + math.pi / count, self.bs * 0.65)
                self.state = "idle"
                self.timer = 90 if self.enraged else 120

    def draw(self, surface):
        if not self.mini:
            self._draw_at(surface, round(self.x), round(self.y))
            return
        # Mini boss: desenha o boss normal numa superficie temporaria e reduz.
        temp = pygame.Surface((80, 80), pygame.SRCALPHA)
        self._draw_at(temp, 40, 40)
        side = max(8, int(80 * self.size / self.draw_size))
        small = pygame.transform.scale(temp, (side, side))
        surface.blit(small, (round(self.x) - side // 2, round(self.y) - side // 2))

    def _draw_at(self, surface, x, y):
        base, light = self.color, self.light
        status = self.status_color()
        if status:
            base = mix(base, status, 0.4)
        telegraph = self.state in ("windup", "cast")
        if self.flash or (telegraph and (self.age // 3) % 2 == 0):
            base = COLORS["white"]

        ds = self.draw_size
        h = ds // 2
        if self.state == "windup":
            x += random.randint(-1, 1)

        pygame.draw.ellipse(surface, COLORS["shadow"], (x - h, y + h - 3, ds, 7))
        eye = COLORS["red"] if self.enraged else COLORS["dark_red"]

        if self.kind in ("king", "bull"):
            pygame.draw.rect(surface, base, (x - 15, y - 14, 30, 29))
            pygame.draw.rect(surface, light, (x - 13, y - 15, 26, 5))
            if self.kind == "king":
                pygame.draw.rect(surface, COLORS["gold"], (x - 11, y - 17, 22, 3))
                for cx in (-10, -2, 6):
                    pygame.draw.rect(surface, COLORS["gold"], (x + cx, y - 22, 4, 6))
            else:
                pygame.draw.rect(surface, COLORS["white"], (x - 19, y - 17, 5, 9))
                pygame.draw.rect(surface, COLORS["white"], (x + 14, y - 17, 5, 9))
            pygame.draw.rect(surface, eye, (x - 8, y - 3, 4, 4))
            pygame.draw.rect(surface, eye, (x + 4, y - 3, 4, 4))
            pygame.draw.rect(surface, COLORS["dark_red"], (x - 7, y + 6, 14, 3))
        elif self.kind == "wizard":
            pygame.draw.polygon(surface, base, [(x, y - h - 6), (x - h, y + h), (x + h, y + h)])
            pygame.draw.rect(surface, light, (x - 4, y - h - 8, 8, 5))
            pygame.draw.rect(surface, COLORS["gold"], (x - 1, y - h - 11, 2, 3))
            pygame.draw.rect(surface, eye, (x - 5, y - 2, 3, 3))
            pygame.draw.rect(surface, eye, (x + 2, y - 2, 3, 3))
        elif self.kind == "eye":
            pygame.draw.circle(surface, COLORS["white"] if not self.flash else base, (x, y), h)
            pygame.draw.circle(surface, base, (x, y), h, 2)
            ax, ay = self.aim
            ix, iy = round(x + ax * 6), round(y + ay * 6)
            pygame.draw.circle(surface, eye if self.enraged else light, (ix, iy), 8)
            pygame.draw.circle(surface, COLORS["panel"], (ix, iy), 4)
        else:  # golem
            pygame.draw.rect(surface, base, (x - h, y - h, ds, ds))
            pygame.draw.rect(surface, light, (x - h + 2, y - h, ds - 4, 6))
            pygame.draw.rect(surface, light, (x - h - 4, y - 6, 6, 16))
            pygame.draw.rect(surface, light, (x + h - 2, y - 6, 6, 16))
            pygame.draw.rect(surface, eye, (x - 9, y - 6, 5, 5))
            pygame.draw.rect(surface, eye, (x + 4, y - 6, 5, 5))
            pygame.draw.rect(surface, COLORS["rock_dark"], (x - 8, y + 6, 16, 3))


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
        self.tear_fx = set()
        self.invuln_frames = INVULN_FRAMES
        self.invuln = 0
        self.bombs = 1
        self.keys = 0
        self.bomb_damage = 5
        self.map_reveal = False
        self.items = []
        # item ativo
        self.active = None
        self.active_charge = 0
        self.fury = 0       # frames restantes de dano x2
        self.shield = 0     # frames restantes de escudo

    @property
    def damage_mult(self):
        return 2 if self.fury > 0 else 1

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
        x, y = round(self.x), round(self.y)

        if self.shield > 0 and (self.shield > 60 or (self.shield // 5) % 2 == 0):
            pygame.draw.circle(surface, (140, 200, 255), (x, y), 11, 1)
            pygame.draw.circle(surface, (210, 235, 255), (x, y), 9, 1)

        if self.invuln > 0 and (self.invuln // 4) % 2 == 0:
            return

        body = COLORS["player"]
        if self.fury > 0:
            body = mix(body, COLORS["red"], 0.55 + 0.25 * math.sin(pygame.time.get_ticks() / 90))
        pygame.draw.rect(surface, body, (x - 6, y - 6, 12, 13))
        pygame.draw.rect(surface, COLORS["player_light"], (x - 4, y - 7, 8, 3))
        pygame.draw.rect(surface, COLORS["white"], (x - 3, y - 2, 2, 2))
        pygame.draw.rect(surface, COLORS["white"], (x + 2, y - 2, 2, 2))


def apply_item(player, item_id):
    data = ITEMS[item_id]
    for stat, delta in data.get("stats", {}).items():
        setattr(player, stat, getattr(player, stat) + delta)
    player.hp = min(player.max_hp, player.hp + data.get("heal", 0))
    player.cooldown = max(5, player.cooldown)
    player.shots = min(3, player.shots)
    if "fx" in data:
        player.tear_fx.add(data["fx"])
    if data.get("flag") == "map":
        player.map_reveal = True
    if item_id not in player.items:
        player.items.append(item_id)


# ----------------------------------------------------------------------------
# Salas
# ----------------------------------------------------------------------------
def spawn_horde(rocks, player_pos, floor, custom_specs):
    """Cria a horda: mistura de tipos liberados no andar + inimigos personalizados."""
    pool = [(s, s["weight"]) for s in ENEMY_SPECS.values()
            if s["min_floor"] <= floor and s["weight"] > 0]
    pool += [(s, s["weight"]) for s in custom_specs]
    specs = [s for s, _ in pool]
    weights = [w for _, w in pool]

    caps = {"tank": 1, "turret": 2}
    used = {}
    enemies = []
    count = min(9, random.randint(3, 5) + (floor - 1) // 2)

    for _ in range(count):
        spec = random.choices(specs, weights=weights)[0]
        if used.get(spec["id"], 0) >= caps.get(spec["id"], 99):
            spec = ENEMY_SPECS["chaser"]
        size = spec["size"]

        for _attempt in range(100):
            x = random.randint(ROOM.left + 25, ROOM.right - 25)
            y = random.randint(ROOM.top + 25, ROOM.bottom - 25)
            if math.hypot(x - player_pos[0], y - player_pos[1]) < 70:
                continue
            candidate = pygame.Rect(x - size // 2, y - size // 2, size, size)
            if not spec["flying"] and any(candidate.colliderect(r.inflate(6, 6)) for r in rocks):
                continue
            enemies.append(Enemy(x, y, spec, floor, roll_mutations(floor)))
            used[spec["id"]] = used.get(spec["id"], 0) + 1
            break
    return enemies


ROOM_BANNERS = {
    "secret": ("SALA SECRETA!", ""),
    "super": ("SUPER SALA SECRETA!", ""),
    "devil": ("SALA DO DEMONIO", "Cada pacto custa vida maxima"),
    "angel": ("SALA DO ANJO", "Escolha UMA bencao gratuita"),
}


class Room:
    def __init__(self, position, neighbors, role="combat", boss_kind="king"):
        self.position = position
        self.neighbors = neighbors    # so passagens ABERTAS (secretas entram aqui ao serem reveladas)
        self.role = role              # start | combat | treasure | boss | secret | super | devil | angel
        self.boss_kind = boss_kind
        self.mini_boss = False        # sala de combate com um mini boss sozinho
        self.mini_kind = None
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
        self.hidden = {}              # direcao -> posicao de uma sala secreta atras da parede
        self.secret_doors = set()     # direcoes cujas portas vieram de paredes quebradas
        self.announced = False
        self.locked = role == "treasure"
        self.visited = role == "start"
        self.spawned = role in ("start", "treasure", "secret", "super", "devil", "angel")
        self.cleared = self.spawned
        self.rewarded = self.spawned

    @property
    def floor_color(self):
        return {"secret": COLORS["floor_secret"], "super": COLORS["floor_super"],
                "boss": COLORS["floor_boss"], "treasure": COLORS["floor_treasure"],
                "devil": COLORS["floor_devil"], "angel": COLORS["floor_angel"],
                }.get(self.role, COLORS["floor"])

    def enter(self, game):
        self.visited = True
        if self.role in ROOM_BANNERS and not self.announced:
            self.announced = True
            title, sub = ROOM_BANNERS[self.role]
            game.show_banner(title, sub, 150)
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
        elif self.mini_boss:
            cx, cy = ROOM.center
            boss = Boss(cx, cy, self.mini_kind, game.floor, mini=True)
            self.enemies = [boss]
            game.show_banner(boss.name, "Um mini boss apareceu!", 150)
        else:
            self.enemies = spawn_horde(self.rocks, (player.x, player.y), game.floor, game.custom_specs)
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
        self.custom_specs = []
        self.last_boss = None
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
        boss_kind = random.choice([k for k in BOSS_KINDS if k != self.last_boss])
        self.last_boss = boss_kind

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

        self.add_secret_rooms(layout)
        self.add_special_rooms(boss_pos)

        # Mini bosses: 1 ou 2 salas de combate aleatorias recebem um mini boss sozinho.
        mini_kinds = [k for k in BOSS_KINDS if k != boss_kind]
        mini_count = 1 + (1 if random.random() < 0.4 else 0)
        for pos in random.sample(combat, min(mini_count, len(combat))):
            self.rooms[pos].mini_boss = True
            self.rooms[pos].mini_kind = random.choice(mini_kinds)

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

        cx, cy = ROOM.center
        self.rooms[treasure_pos].items.append(Item(cx, cy, self.random_item()))
        self.fill_secret_rooms()
        self.fill_special_rooms()

        self.room = self.rooms[(0, 0)]
        self.player.x, self.player.y = cx, cy
        self.tears.clear()
        self.bullets.clear()
        self.bombs.clear()
        self.explosions.clear()

    def add_secret_rooms(self, layout):
        """Como no TBOI: a sala secreta fica num buraco cercado por 2+ salas; a super secreta,
        num buraco encostado em UMA sala so. Ambas sem porta: so aparecem ao explodir a parede."""
        eligible = {p for p, r in self.rooms.items() if r.role in ("start", "combat", "treasure")}
        empties = [(x, y) for x in range(-3, 4) for y in range(-3, 4) if (x, y) not in layout]

        def around(cell):
            return [(cell[0] + dx, cell[1] + dy) for dx, dy in DIRECTIONS.values()]

        def count(cell):
            return sum(1 for a in around(cell) if a in eligible)

        secret_cell = None
        cands = [c for c in empties if count(c) >= 2]
        if cands:
            best = max(count(c) for c in cands)
            secret_cell = random.choice([c for c in cands if count(c) == best])

        super_cell = None
        cands = [c for c in empties
                 if c != secret_cell
                 and sum(1 for a in around(c) if a in layout) == 1 and count(c) == 1
                 and (secret_cell is None or abs(c[0] - secret_cell[0]) + abs(c[1] - secret_cell[1]) > 1)]
        if cands:
            super_cell = random.choice(cands)

        for cell, role in ((secret_cell, "secret"), (super_cell, "super")):
            if not cell:
                continue
            self.rooms[cell] = Room(cell, {}, role)
            for a in around(cell):
                if a in eligible:
                    vec = (cell[0] - a[0], cell[1] - a[1])
                    self.rooms[a].hidden[DIR_BY_VECTOR[vec]] = cell

    def add_special_rooms(self, boss_pos):
        """Sala do Demonio e Sala do Anjo: existem em TODO andar, com porta comum.
        Preferem ficar coladas na sala do boss (abrem quando o boss morre); se nao houver
        espaco ali, grudam em qualquer outra sala do andar."""
        attachable = [p for p, r in self.rooms.items()
                      if r.role in ("start", "combat", "treasure", "boss")]

        def free_cells_next_to(positions):
            options = []
            for pos in positions:
                for direction, (dx, dy) in DIRECTIONS.items():
                    cell = (pos[0] + dx, pos[1] + dy)
                    if abs(cell[0]) <= 3 and abs(cell[1]) <= 3 and cell not in self.rooms:
                        options.append((cell, pos, direction))
            return options

        for role in ("devil", "angel"):
            options = free_cells_next_to([boss_pos]) or free_cells_next_to(attachable)
            if not options:
                continue
            cell, source, direction = random.choice(options)
            room = Room(cell, {OPPOSITE[direction]: source}, role)
            self.rooms[cell] = room
            self.rooms[source].neighbors[direction] = cell

    def fill_secret_rooms(self):
        cx, cy = ROOM.center
        for room in self.rooms.values():
            if room.role == "secret":
                for dx, dy in ((-34, 0), (0, -22), (34, 0), (0, 22)):
                    if random.random() < 0.85:
                        self.drop_pickup(room, cx + dx, cy + dy)
                if random.random() < 0.5:
                    room.chests.append(Chest(cx, cy - 40, "wood"))
            elif room.role == "super":
                room.items.append(Item(cx, cy, self.random_item()))
                room.chests.append(Chest(cx - 45, cy, "wood"))

    def fill_special_rooms(self):
        """Demonio: ativo + item exclusivo + passivo comum, todos pagos com vida maxima.
        Anjo: tiros teleguiados (se ainda nao tem) + outra bencao + um ativo; escolha UMA."""
        cx, cy = ROOM.center
        for room in self.rooms.values():
            if room.role == "devil":
                devil_only = [i for i, d in ITEMS.items() if d.get("devil_only")]
                normal = [i for i, d in ITEMS.items()
                          if not d.get("devil_only") and not d.get("active")
                          and "max_hp" not in d["stats"]]
                chosen = []
                for pool in (list(ACTIVES), devil_only, normal):
                    pick = self.random_item(pool, chosen)
                    if pick:
                        chosen.append(pick)
                n = len(chosen)
                for i, item_id in enumerate(chosen):
                    x = cx + (i - (n - 1) / 2) * 46
                    room.items.append(Item(x, cy, item_id, cost=ITEMS[item_id].get("cost", 2)))
            elif room.role == "angel":
                chosen = []
                homing = self.random_item(["homing"])
                if homing:
                    chosen.append(homing)
                while len(chosen) < 2:
                    pick = self.random_item(ANGEL_POOL, chosen)
                    if not pick:
                        break
                    chosen.append(pick)
                pick = self.random_item(list(ACTIVES), chosen)
                if pick:
                    chosen.append(pick)
                n = len(chosen)
                for i, item_id in enumerate(chosen):
                    x = cx + (i - (n - 1) / 2) * 46
                    room.items.append(Item(x, cy, item_id, group="angel"))

    def next_floor(self):
        self.floor += 1
        sub = "Os inimigos estao mais fortes"
        if self.floor % 2 == 0:
            spec = generate_custom_enemy(self.floor)
            self.custom_specs.append(spec)
            sub = f"Novo inimigo: {spec['name']} ({spec['desc']})"
        self.build_floor()
        self.show_banner(f"ANDAR {self.floor}", sub, 240)

    def random_item(self, pool=None, exclude=()):
        """Sorteia um item que o jogador nao tem e que nao esta no chao.
        Sem 'pool': usa todos os itens menos os exclusivos do demonio (e nunca falha).
        Com 'pool': sorteia so dentro dela e devolve None se nao sobrar nada."""
        lying = {i.item_id for r in self.rooms.values() for i in r.items}
        owned = set(self.player.items) | {self.player.active}
        base = list(ITEMS) if pool is None else list(pool)
        cands = [i for i in base
                 if i not in owned and i not in lying and i not in exclude
                 and (pool is not None or not ITEMS[i].get("devil_only"))]
        if cands:
            return random.choice(cands)
        return "bombbag" if pool is None else None

    # ---- utilidades ------------------------------------------------------------
    def show_banner(self, title, sub="", frames=120, only_if_empty=False):
        if only_if_empty and self.banner:
            return
        self.banner = [title, sub, frames]

    def hurt_player(self, amount):
        p = self.player
        if p.invuln > 0 or p.shield > 0 or self.game_over:
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
            tx = clamp(x + random.randint(-14, 14), ROOM.left + 12, ROOM.right - 12)
            ty = clamp(y + random.randint(-14, 14), ROOM.top + 12, ROOM.bottom - 12)
            if not any(r.collidepoint(tx, ty) for r in room.rocks):
                px, py = tx, ty
                break
        room.pickups.append(Pickup(px, py, kind))

    def kill_enemy(self, enemy):
        room = self.room
        if enemy not in room.enemies:
            return
        room.enemies.remove(enemy)
        if enemy.is_boss:
            room.enemies.clear()   # os servos morrem junto com o boss
            self.bullets.clear()
            return
        if "explode" in enemy.death:
            self.enemy_explode(enemy.x, enemy.y)
        if "split" in enemy.death:
            for sx in (-7, 7):
                room.enemies.append(Enemy(enemy.x + sx, enemy.y, MINI_SPEC, enemy.floor))
        if random.random() < 0.12:
            self.drop_pickup(room, enemy.x, enemy.y)

    def enemy_explode(self, x, y):
        radius = 30
        self.explosions.append(Explosion(x, y, radius))
        if circle_rect_collision(x, y, radius, self.player.rect):
            self.hurt_player(1)
        for other in list(self.room.enemies):
            if other.is_boss:
                continue
            if circle_rect_collision(x, y, radius, other.rect):
                other.health -= 2
                other.flash = 5
                if other.health <= 0:
                    self.kill_enemy(other)

    def charge_active(self, amount):
        p = self.player
        if p.active:
            p.active_charge = min(ITEMS[p.active]["charges"], p.active_charge + amount)

    def on_room_cleared(self, room):
        if room.rewarded:
            return
        room.rewarded = True
        cx, cy = ROOM.center
        if room.role == "boss":
            self.charge_active(2)
            room.items.append(Item(cx - 26, cy, self.random_item()))
            room.hatch = pygame.Rect(cx + 14, cy - 10, 20, 20)
            self.show_banner("BOSS DERROTADO!", "Pegue a melhoria, visite o demonio/anjo ou desca", 200)
        elif room.mini_boss:
            self.charge_active(2)
            self.drop_pickup(room, cx, cy, "heart")
            for _ in range(2):
                self.drop_pickup(room, cx, cy)
            if room.bonus_key:
                self.drop_pickup(room, cx, cy, "key")
            self.show_banner("MINI BOSS DERROTADO!", "Recompensas no chao", 150)
        else:
            self.charge_active(1)
            if room.bonus_key:
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

    def use_active(self):
        p, room = self.player, self.room
        if self.game_over or not p.active:
            return
        data = ITEMS[p.active]
        if p.active_charge < data["charges"]:
            self.show_banner("SEM CARGA", f"Limpe salas para recarregar ({p.active_charge}/{data['charges']})",
                             70, only_if_empty=True)
            return

        effect = data["effect"]
        if effect == "bombs":
            for i in range(6):
                a = math.tau * i / 6 + random.uniform(-0.2, 0.2)
                bx = clamp(p.x + math.cos(a) * 52, ROOM.left + 10, ROOM.right - 10)
                by = clamp(p.y + math.sin(a) * 52, ROOM.top + 10, ROOM.bottom - 10)
                if math.hypot(bx - p.x, by - p.y) < BOMB_RADIUS + 12:
                    continue   # encostado na parede: nao cria bomba que te acertaria
                bomb = Bomb(bx, by)
                bomb.fuse = 25 + i * 7
                self.bombs.append(bomb)
            self.show_banner("CHUVA DE BOMBAS", "", 60)
        elif effect == "keys":
            locked = [r for r in self.rooms.values() if r.locked]
            golds = [c for c in room.chests if c.kind == "gold" and not c.opened]
            if not locked and not golds:
                self.show_banner("CHAVE MESTRA", "Nada trancado por aqui", 80, only_if_empty=True)
                return
            for r in locked:
                r.locked = False
            for chest in golds:
                self.open_chest(room, chest)
            self.show_banner("CHAVE MESTRA", "Portas e baus destrancados", 90)
        elif effect == "fury":
            p.fury = 600
            self.show_banner("FURIA!", "Dano x2 por 10 segundos", 80)
        elif effect == "shield":
            p.shield = 300
            self.show_banner("ESCUDO ARCANO", "Invulneravel por 5 segundos", 80)
        elif effect == "blast":
            self.explosions.append(Explosion(p.x, p.y, 110))
            for enemy in list(room.enemies):
                enemy.health -= 6
                enemy.flash = 5
                if enemy.health <= 0:
                    self.kill_enemy(enemy)
            self.bullets.clear()
        p.active_charge = 0

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
        self.reveal_secret_walls(room, bx, by)

    def reveal_secret_walls(self, room, bx, by):
        """Bomba perto do meio de uma parede com sala secreta atras abre a passagem."""
        for direction, target_pos in list(room.hidden.items()):
            if circle_rect_collision(bx, by, BOMB_RADIUS, door_trigger(direction).inflate(20, 20)):
                target = self.rooms[target_pos]
                room.neighbors[direction] = target_pos
                target.neighbors[OPPOSITE[direction]] = room.position
                room.secret_doors.add(direction)
                target.secret_doors.add(OPPOSITE[direction])
                del room.hidden[direction]
                self.show_banner("PAREDE QUEBRADA!", "Uma passagem secreta se abriu", 130)

    def open_chest(self, room, chest):
        chest.opened = True
        if chest.kind == "gold":
            ix = clamp(chest.x, ROOM.left + 14, ROOM.right - 14)
            iy = clamp(chest.y + 18, ROOM.top + 14, ROOM.bottom - 14)
            room.items.append(Item(ix, iy, self.random_item()))
        else:
            for _ in range(random.randint(2, 3)):
                self.drop_pickup(room, chest.x, chest.y)

    def collect_item(self, room, item):
        """Pega um item: remove os rivais do mesmo grupo (anjo), troca o ativo e mostra o aviso."""
        p = self.player
        data = ITEMS[item.item_id]
        room.items = [i for i in room.items
                      if i is not item and not (item.group and i.group == item.group)]
        if data.get("active"):
            if p.active:   # o ativo antigo cai no lugar do novo (so pode ser repego depois de sair de cima)
                old = Item(item.x, item.y, p.active)
                old.armed = False
                room.items.append(old)
            p.active = item.item_id
            p.active_charge = data["charges"]
            self.show_banner(data["name"], "ATIVO: aperte Q ou SHIFT - " + data["desc"][4:], 190)
        else:
            apply_item(p, item.item_id)
            sub = data["desc"]
            if item.cost:
                sub = f"Pacto selado: -{item.cost // 2} coracao de vida maxima"
            self.show_banner(data["name"], sub, 170)

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
        if p.fury > 0:
            p.fury -= 1
        if p.shield > 0:
            p.shield -= 1
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
            damage = enemy.tick_status()
            if damage:
                enemy.health -= damage
                enemy.flash = 1
                if enemy.health <= 0:
                    self.kill_enemy(enemy)
                    continue
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
            fx = frozenset(p.tear_fx)
            damage = p.damage * p.damage_mult
            for off in SPREADS[p.shots]:
                a = base + off
                self.tears.append(Tear(p.x, p.y, math.cos(a), math.sin(a),
                                       damage, p.tear_speed, p.tear_life, fx))
            self.shoot_timer = p.cooldown

    def update_tears(self):
        room = self.room
        bounds = ROOM.inflate(-5, -5)
        for tear in self.tears[:]:
            tear.update(room.enemies)
            if (tear.life <= 0
                    or any(rock.collidepoint(tear.x, tear.y) for rock in room.rocks)):
                self.tears.remove(tear)
                continue

            if not bounds.collidepoint(tear.x, tear.y):
                if "bounce" in tear.fx and tear.bounces < 3:
                    if tear.x < bounds.left or tear.x > bounds.right:
                        tear.dx = -tear.dx
                    if tear.y < bounds.top or tear.y > bounds.bottom:
                        tear.dy = -tear.dy
                    tear.x = clamp(tear.x, bounds.left + 1, bounds.right - 1)
                    tear.y = clamp(tear.y, bounds.top + 1, bounds.bottom - 1)
                    tear.bounces += 1
                else:
                    self.tears.remove(tear)
                    continue

            pierce = "pierce" in tear.fx
            for enemy in list(room.enemies):
                if id(enemy) in tear.hit:
                    continue
                if circle_rect_collision(tear.x, tear.y, tear.radius, enemy.rect):
                    tear.hit.add(id(enemy))
                    enemy.health -= tear.damage
                    enemy.flash = 5
                    enemy.apply_fx(tear.fx)
                    if enemy.health <= 0:
                        self.kill_enemy(enemy)
                    if not pierce:
                        self.tears.remove(tear)
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
            if item not in room.items:      # removido por um rival do mesmo grupo
                continue
            item.near = pr.inflate(70, 70).colliderect(item.rect)
            touching = pr.colliderect(item.rect)
            if not item.armed:
                if not touching:
                    item.armed = True
                continue
            if not touching:
                continue
            if item.cost:
                if p.max_hp - item.cost < MIN_MAX_HP:
                    self.show_banner("VIDA INSUFICIENTE", "Esse pacto te custaria a vida", 90, only_if_empty=True)
                    continue
                p.max_hp -= item.cost
                p.hp = min(p.hp, p.max_hp)
            self.collect_item(room, item)

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
    pygame.draw.rect(surface, room.floor_color, ROOM)

    # Pequenas marcas no chao para dar textura sem poluir a sala.
    for y in range(ROOM.top + 8, ROOM.bottom - 4, 16):
        for x in range(ROOM.left + 8, ROOM.right - 4, 16):
            if ((x // 16) + (y // 16)) % 3 == 0:
                pygame.draw.rect(surface, mix(room.floor_color, (255, 255, 255), 0.06), (x, y, 2, 2))

    edge = {"devil": COLORS["devil_edge"], "angel": COLORS["angel_edge"]}.get(room.role, COLORS["wall_edge"])
    pygame.draw.rect(surface, edge, ROOM, 3)
    pygame.draw.rect(surface, COLORS["wall"], ROOM.inflate(-6, -6), 2)

    for rock in room.rocks:
        pygame.draw.rect(surface, COLORS["rock_dark"], rock.move(0, 2))
        pygame.draw.rect(surface, COLORS["rock"], rock)
        pygame.draw.rect(surface, COLORS["rock_light"], (rock.x + 2, rock.y + 2, rock.w - 6, 3))

    # Portas: fechadas (grade vermelha) ate limpar a sala; douradas se o destino esta trancado;
    # vermelho vivo = sala do demonio; branco = sala do anjo;
    # passagens secretas abertas por bomba ganham uma borda roxa.
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
            target_role = rooms[target_pos].role
            if target_role == "devil":
                pygame.draw.rect(surface, COLORS["door_devil"], rect)
                pygame.draw.rect(surface, COLORS["panel"], rect.inflate(-6, -6))
            elif target_role == "angel":
                pygame.draw.rect(surface, COLORS["door_angel"], rect)
                pygame.draw.rect(surface, COLORS["panel"], rect.inflate(-6, -6))
            else:
                pygame.draw.rect(surface, COLORS["door_open"], rect)
            if direction in room.secret_doors:
                pygame.draw.rect(surface, COLORS["secret_edge"], rect, 1)

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

    # Item ativo (canto inferior esquerdo): icone + cargas. Brilha quando esta pronto.
    if player.active:
        data = ITEMS[player.active]
        ready = player.active_charge >= data["charges"]
        icon = pygame.Rect(ROOM.left + 3, 299, 12, 12)
        pygame.draw.rect(surface, COLORS["gold"] if ready else COLORS["panel"], icon.inflate(2, 2))
        pygame.draw.rect(surface, data["color"] if ready else mix(data["color"], COLORS["panel"], 0.65), icon)
        glyph = FONT_SMALL.render(data["glyph"], True, COLORS["panel"])
        surface.blit(glyph, glyph.get_rect(center=icon.center))
        for i in range(data["charges"]):
            pygame.draw.rect(surface, COLORS["gold"] if i < player.active_charge else COLORS["dark_red"],
                             (ROOM.left + 19 + i * 6, 308, 4, 4))
        surface.blit(FONT_SMALL.render("Q", True, COLORS["white"] if ready else COLORS["grey"]),
                     (ROOM.left + 19, 298))

    # Barra de vida do boss
    for enemy in room.enemies:
        if enemy.is_boss:
            surface.blit(FONT_SMALL.render(enemy.name, True, COLORS["white"]), (ROOM.left + 62, 305))
            bar = pygame.Rect(195, 306, 150, 6)
            pygame.draw.rect(surface, COLORS["dark_red"], bar)
            fill = bar.copy()
            fill.width = int(bar.width * max(0, enemy.health) / enemy.max_health)
            pygame.draw.rect(surface, COLORS["red"], fill)
            pygame.draw.rect(surface, COLORS["wall_edge"], bar, 1)
            break

    # Melhorias coletadas (quadradinhos coloridos no canto inferior direito)
    for i, item_id in enumerate(player.items[:14]):
        pygame.draw.rect(surface, ITEMS[item_id]["color"], (ROOM.right - 7 * (i + 1), 306, 5, 5))


def draw_minimap(surface, game):
    """Mapa no canto superior direito. Vermelho = boss, dourado = tesouro,
    roxo = sala secreta, rosa = super secreta, vermelho vivo = demonio, azul claro = anjo."""
    x0, y0 = ROOM.right - 53, ROOM.top + 3
    panel = pygame.Surface((51, 37), pygame.SRCALPHA)
    panel.fill((10, 8, 15, 150))
    surface.blit(panel, (x0 - 1, y0 - 1))

    seen = set()
    for pos, room in game.rooms.items():
        if room.visited:
            seen.add(pos)
            seen.update(room.neighbors.values())
    if game.player.map_reveal:
        seen = set(game.rooms)

    marker_colors = {"boss": COLORS["red"], "treasure": COLORS["gold"],
                     "secret": COLORS["secret_edge"], "super": (255, 120, 200),
                     "devil": (235, 40, 55), "angel": (190, 225, 255)}
    for pos in seen:
        room = game.rooms[pos]
        rect = pygame.Rect(x0 + (pos[0] + 3) * 7, y0 + (pos[1] + 3) * 5, 6, 4)
        if pos == game.room.position:
            color = COLORS["white"]
        elif room.visited:
            color = COLORS["grey"]
        elif room.role == "secret":
            color = (80, 50, 110)
        elif room.role == "super":
            color = (110, 50, 90)
        else:
            color = COLORS["dim"]
        pygame.draw.rect(surface, color, rect)
        marker = marker_colors.get(room.role)
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


def draw_game_over(surface, game):
    overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
    overlay.fill((10, 8, 15, 190))
    surface.blit(overlay, (0, 0))
    title = FONT_BIG.render("VOCE MORREU", True, COLORS["white"])
    floor = FONT_HINT.render(f"Voce chegou ao andar {game.floor}", True, COLORS["grey"])
    hint = FONT_HINT.render("Segure R por 1 segundo para tentar novamente", True, COLORS["gold"])
    surface.blit(title, title.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 - 20)))
    surface.blit(floor, floor.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 + 4)))
    surface.blit(hint, hint.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 + 22)))


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
    y = VIRTUAL_HEIGHT // 2 + 48
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
        draw_game_over(canvas, game)
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
                elif event.key in (pygame.K_q, pygame.K_LSHIFT, pygame.K_RSHIFT):
                    if not paused and not game.game_over:
                        game.use_active()
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