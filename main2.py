import math
import random
import pygame

# Meu Roguelike - prototipo jogavel
# Controles: WASD movimenta | Setas atiram | R reinicia apos morrer | ESC sai
#
# Regras das salas:
#  - Cada sala gera a sua horda de inimigos UMA unica vez (quando voce entra pela primeira vez).
#  - Enquanto houver inimigos vivos, as portas ficam fechadas.
#  - Ao derrotar todos, as portas abrem e a sala nunca mais gera inimigos.
#
# Inimigos:
#  - fly     (voador)   : ignora pedras, voa em zigue-zague, rapido e fragil.
#  - chaser  (terrestre): persegue o jogador, e bloqueado pelas pedras.
#  - tank    (terrestre): lento, grande, muita vida e causa 2 de dano.

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
    "tear": (115, 220, 255),
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
}

ROOM = pygame.Rect(25, 25, VIRTUAL_WIDTH - 50, VIRTUAL_HEIGHT - 50)
PLAYER_SIZE = 13
PLAYER_SPEED = 2.25
PLAYER_MAX_HP = 6
TEAR_SPEED = 5.0
TEAR_COOLDOWN = 13
INVULN_TIME = 850  # milissegundos
DOOR_W = 24

DIRECTIONS = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}

# Atributos de cada tipo de inimigo.
ENEMY_TYPES = {
    "fly": {"health": 2, "speed": 1.05, "damage": 1, "size": 10, "flying": True},
    "chaser": {"health": 3, "speed": 0.72, "damage": 1, "size": 13, "flying": False},
    "tank": {"health": 8, "speed": 0.40, "damage": 2, "size": 18, "flying": False},
}


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
# Entidades
# ----------------------------------------------------------------------------
class Tear:
    def __init__(self, x, y, dx, dy):
        self.x = float(x)
        self.y = float(y)
        self.dx = dx
        self.dy = dy
        self.radius = 3
        self.life = 105

    def update(self):
        self.x += self.dx * TEAR_SPEED
        self.y += self.dy * TEAR_SPEED
        self.life -= 1

    def draw(self, surface):
        x, y = round(self.x), round(self.y)
        pygame.draw.circle(surface, COLORS["tear"], (x, y), self.radius)
        pygame.draw.rect(surface, COLORS["white"], (x - 1, y - 2, 2, 2))


class Enemy:
    def __init__(self, x, y, enemy_type):
        stats = ENEMY_TYPES[enemy_type]
        self.enemy_type = enemy_type
        self.x = float(x)
        self.y = float(y)
        self.health = stats["health"]
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

    def update(self, player, rocks, others):
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
            if other is self or other.flying != self.flying:
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


class Player:
    def __init__(self):
        self.x = VIRTUAL_WIDTH / 2
        self.y = VIRTUAL_HEIGHT / 2
        self.size = PLAYER_SIZE
        self.hp = PLAYER_MAX_HP
        self.invulnerable_until = 0

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

        move_with_rocks(self, dx * PLAYER_SPEED, dy * PLAYER_SPEED, rocks)

        half = self.size / 2
        self.x = clamp(self.x, ROOM.left + half, ROOM.right - half)
        self.y = clamp(self.y, ROOM.top + half, ROOM.bottom - half)

    def draw(self, surface):
        now = pygame.time.get_ticks()
        if now < self.invulnerable_until and (now // 90) % 2 == 0:
            return

        x, y = round(self.x), round(self.y)
        pygame.draw.rect(surface, COLORS["player"], (x - 6, y - 6, 12, 13))
        pygame.draw.rect(surface, COLORS["player_light"], (x - 4, y - 7, 8, 3))
        pygame.draw.rect(surface, COLORS["white"], (x - 3, y - 2, 2, 2))
        pygame.draw.rect(surface, COLORS["white"], (x + 2, y - 2, 2, 2))


# ----------------------------------------------------------------------------
# Salas
# ----------------------------------------------------------------------------
def spawn_horde(rocks, player_pos):
    """Cria a horda da sala: mistura de voadores e terrestres (no maximo 1 tank)."""
    enemies = []
    has_tank = False
    for _ in range(random.randint(3, 5)):
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
            enemies.append(Enemy(x, y, enemy_type))
            has_tank = has_tank or enemy_type == "tank"
            break
    return enemies


class Room:
    def __init__(self, position, neighbors, is_start=False):
        self.position = position
        self.neighbors = neighbors
        self.rocks = make_rocks(2 if is_start else random.randint(3, 6))
        self.enemies = []
        self.visited = is_start
        self.spawned = is_start   # a sala inicial nao tem horda
        self.cleared = is_start

    def enter(self, player):
        self.visited = True
        # A horda so e criada na PRIMEIRA vez. Depois disso a sala nunca mais gera inimigos.
        if not self.spawned:
            self.spawned = True
            self.enemies = spawn_horde(self.rocks, (player.x, player.y))
            if not self.enemies:
                self.cleared = True

    def update(self):
        if self.spawned and not self.cleared and not self.enemies:
            self.cleared = True

    def is_door_open(self, direction):
        return direction in self.neighbors and self.cleared


class Game:
    def __init__(self):
        layout = generate_dungeon(9)
        self.rooms = {
            pos: Room(pos, get_neighbors(layout, pos), is_start=(pos == (0, 0)))
            for pos in layout
        }
        self.room = self.rooms[(0, 0)]
        self.player = Player()
        self.tears = []
        self.shoot_timer = 0
        self.game_over = False

    def change_room(self, direction):
        if not self.room.is_door_open(direction):
            return
        self.room = self.rooms[self.room.neighbors[direction]]
        self.player.x, self.player.y = entry_position(direction)
        self.tears.clear()
        self.room.enter(self.player)

    def update(self, keys, now):
        player, room = self.player, self.room
        player.move(keys, room.rocks)

        # Mira independente do movimento: setas disparam em oito direcoes.
        aim_x = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        aim_y = int(keys[pygame.K_DOWN]) - int(keys[pygame.K_UP])

        self.shoot_timer = max(0, self.shoot_timer - 1)
        if (aim_x or aim_y) and self.shoot_timer == 0:
            length = math.hypot(aim_x, aim_y)
            self.tears.append(Tear(player.x, player.y, aim_x / length, aim_y / length))
            self.shoot_timer = TEAR_COOLDOWN

        bounds = ROOM.inflate(-5, -5)
        for tear in self.tears[:]:
            tear.update()
            if (tear.life <= 0
                    or not bounds.collidepoint(tear.x, tear.y)
                    or any(rock.collidepoint(tear.x, tear.y) for rock in room.rocks)):
                self.tears.remove(tear)
                continue

            hit_enemy = None
            for enemy in room.enemies:
                if circle_rect_collision(tear.x, tear.y, tear.radius, enemy.rect):
                    hit_enemy = enemy
                    break

            if hit_enemy:
                hit_enemy.health -= 1
                hit_enemy.flash = 5
                self.tears.remove(tear)
                if hit_enemy.health <= 0:
                    room.enemies.remove(hit_enemy)

        for enemy in room.enemies:
            enemy.update(player, room.rocks, room.enemies)
            if enemy.rect.colliderect(player.rect) and now >= player.invulnerable_until:
                player.hp -= enemy.damage
                player.invulnerable_until = now + INVULN_TIME
                if player.hp <= 0:
                    player.hp = 0
                    self.game_over = True

        # Quando o ultimo inimigo morre, a sala e marcada como limpa e as portas abrem.
        room.update()

        # Atravessar portas (so funciona se estiverem abertas).
        if room.cleared and not self.game_over:
            for direction in room.neighbors:
                if player.rect.colliderect(door_trigger(direction)):
                    self.change_room(direction)
                    break


# ----------------------------------------------------------------------------
# Desenho
# ----------------------------------------------------------------------------
def draw_room(surface, room):
    surface.fill(COLORS["background"])
    pygame.draw.rect(surface, COLORS["floor"], ROOM)

    # Pequenas marcas no chao para dar textura sem poluir a sala.
    for y in range(ROOM.top + 8, ROOM.bottom - 4, 16):
        for x in range(ROOM.left + 8, ROOM.right - 4, 16):
            if ((x // 16) + (y // 16)) % 3 == 0:
                pygame.draw.rect(surface, COLORS["floor_alt"], (x, y, 2, 2))

    pygame.draw.rect(surface, COLORS["wall_edge"], ROOM, 3)
    pygame.draw.rect(surface, COLORS["wall"], ROOM.inflate(-6, -6), 2)

    # Pedras
    for rock in room.rocks:
        pygame.draw.rect(surface, COLORS["rock_dark"], rock.move(0, 2))
        pygame.draw.rect(surface, COLORS["rock"], rock)
        pygame.draw.rect(surface, COLORS["rock_light"], (rock.x + 2, rock.y + 2, rock.w - 6, 3))

    # Portas: so existem onde ha sala vizinha. Fechadas = grade; abertas = passagem escura.
    for direction in room.neighbors:
        rect = door_trigger(direction)
        if room.is_door_open(direction):
            pygame.draw.rect(surface, COLORS["door_open"], rect)
        else:
            pygame.draw.rect(surface, COLORS["door_closed"], rect)
            if direction in ("N", "S"):
                for bx in range(rect.left + 3, rect.right - 2, 6):
                    pygame.draw.rect(surface, COLORS["door_bar"], (bx, rect.top, 2, rect.height))
            else:
                for by in range(rect.top + 3, rect.bottom - 2, 6):
                    pygame.draw.rect(surface, COLORS["door_bar"], (rect.left, by, rect.width, 2))


def draw_hud(surface, player, room):
    label = FONT_SMALL.render("VIDA", True, COLORS["white"])
    surface.blit(label, (ROOM.left + 3, 5))

    for i in range(PLAYER_MAX_HP // 2):
        x = ROOM.left + 31 + i * 13
        color = COLORS["red"] if player.hp >= (i + 1) * 2 else COLORS["dark_red"]
        pygame.draw.rect(surface, color, (x, 7, 10, 8))
        pygame.draw.rect(surface, COLORS["white"], (x + 2, 8, 2, 2))

    if room.cleared:
        status = FONT_SMALL.render("PORTAS ABERTAS", True, COLORS["gold"])
    else:
        status = FONT_SMALL.render(f"INIMIGOS: {len(room.enemies)}", True, COLORS["white"])
    surface.blit(status, (ROOM.right - status.get_width() - 3, 5))


def draw_game_over(surface):
    overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
    overlay.fill((10, 8, 15, 190))
    surface.blit(overlay, (0, 0))
    title = FONT_BIG.render("VOCE MORREU", True, COLORS["white"])
    hint = FONT_HINT.render("Pressione R para tentar novamente", True, COLORS["gold"])
    surface.blit(title, title.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 - 12)))
    surface.blit(hint, hint.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 + 14)))


# ----------------------------------------------------------------------------
# Loop principal
# ----------------------------------------------------------------------------
def main():
    game = Game()
    running = True

    while running:
        clock.tick(FPS)
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if game.game_over and event.key == pygame.K_r:
                    game = Game()

        if not game.game_over:
            game.update(pygame.key.get_pressed(), now)

        # Renderizacao em baixa resolucao, ampliada com nearest-neighbor.
        draw_room(canvas, game.room)
        for tear in game.tears:
            tear.draw(canvas)
        # Terrestres primeiro, voadores por cima.
        for enemy in sorted(game.room.enemies, key=lambda e: e.flying):
            enemy.draw(canvas)
        game.player.draw(canvas)
        draw_hud(canvas, game.player, game.room)

        if game.game_over:
            draw_game_over(canvas)

        pygame.transform.scale(canvas, (WIDTH, HEIGHT), screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()