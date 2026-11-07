import math
import random
import pygame

# Meu Roguelike - prototipo jogavel
# Controles: WASD movimenta | Setas atiram | R reinicia apos morrer | ESC sai

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

COLORS = {
    "background": (25, 22, 34),
    "floor": (54, 47, 61),
    "floor_alt": (58, 50, 65),
    "wall": (26, 24, 34),
    "wall_edge": (104, 83, 103),
    "player": (90, 174, 235),
    "player_light": (183, 229, 255),
    "enemy": (185, 75, 91),
    "enemy_light": (255, 151, 145),
    "tear": (115, 220, 255),
    "white": (245, 239, 225),
    "red": (220, 66, 83),
    "dark_red": (86, 34, 49),
    "gold": (246, 201, 91),
}

ROOM = pygame.Rect(25, 25, VIRTUAL_WIDTH - 50, VIRTUAL_HEIGHT - 50)
PLAYER_SIZE = 13
PLAYER_SPEED = 2.25
PLAYER_MAX_HP = 6
TEAR_SPEED = 5.0
TEAR_COOLDOWN = 13
ENEMY_SPEED = 0.72
INVULN_TIME = 850  # milissegundos


def clamp(value, low, high):
    return max(low, min(high, value))


def circle_rect_collision(cx, cy, radius, rect):
    closest_x = clamp(cx, rect.left, rect.right)
    closest_y = clamp(cy, rect.top, rect.bottom)
    return (cx - closest_x) ** 2 + (cy - closest_y) ** 2 < radius ** 2


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
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.size = 13
        self.hp = 3
        self.flash = 0

    @property
    def rect(self):
        return pygame.Rect(round(self.x - self.size / 2),
                           round(self.y - self.size / 2),
                           self.size, self.size)

    def update(self, player):
        dx = player.x - self.x
        dy = player.y - self.y
        distance = math.hypot(dx, dy)
        if distance > 1:
            self.x += dx / distance * ENEMY_SPEED
            self.y += dy / distance * ENEMY_SPEED

        half = self.size / 2
        self.x = clamp(self.x, ROOM.left + half, ROOM.right - half)
        self.y = clamp(self.y, ROOM.top + half, ROOM.bottom - half)
        self.flash = max(0, self.flash - 1)

    def draw(self, surface):
        color = COLORS["white"] if self.flash else COLORS["enemy"]
        x, y = round(self.x), round(self.y)
        pygame.draw.rect(surface, color, (x - 7, y - 6, 14, 13))
        pygame.draw.rect(surface, COLORS["enemy_light"], (x - 5, y - 7, 10, 3))
        pygame.draw.rect(surface, COLORS["dark_red"], (x - 4, y - 1, 2, 2))
        pygame.draw.rect(surface, COLORS["dark_red"], (x + 2, y - 1, 2, 2))


class Player:
    def __init__(self):
        self.x = VIRTUAL_WIDTH / 2
        self.y = VIRTUAL_HEIGHT / 2
        self.size = PLAYER_SIZE
        self.hp = PLAYER_MAX_HP
        self.invulnerable_until = 0
        self.last_direction = (0, -1)

    @property
    def rect(self):
        return pygame.Rect(round(self.x - self.size / 2),
                           round(self.y - self.size / 2),
                           self.size, self.size)

    def move(self, keys):
        dx = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
        dy = int(keys[pygame.K_s]) - int(keys[pygame.K_w])
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071

        self.x += dx * PLAYER_SPEED
        self.y += dy * PLAYER_SPEED

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


def spawn_enemies(count=4):
    enemies = []
    for _ in range(count):
        for attempt in range(100):
            x = random.randint(ROOM.left + 25, ROOM.right - 25)
            y = random.randint(ROOM.top + 25, ROOM.bottom - 25)
            if math.hypot(x - VIRTUAL_WIDTH / 2, y - VIRTUAL_HEIGHT / 2) > 65:
                enemies.append(Enemy(x, y))
                break
    return enemies


def draw_room(surface):
    surface.fill(COLORS["background"])
    pygame.draw.rect(surface, COLORS["floor"], ROOM)

    # Pequenas marcas no chao para dar textura sem poluir a sala.
    for y in range(ROOM.top + 8, ROOM.bottom - 4, 16):
        for x in range(ROOM.left + 8, ROOM.right - 4, 16):
            if ((x // 16) + (y // 16)) % 3 == 0:
                pygame.draw.rect(surface, COLORS["floor_alt"], (x, y, 2, 2))

    pygame.draw.rect(surface, COLORS["wall_edge"], ROOM, 3)
    pygame.draw.rect(surface, COLORS["wall"], ROOM.inflate(-6, -6), 2)

    # Portas fechadas nesta primeira sala de combate.
    door_w, door_h = 24, 8
    cx = ROOM.centerx
    pygame.draw.rect(surface, COLORS["wall"], (cx - door_w // 2, ROOM.top - 2, door_w, door_h))
    pygame.draw.rect(surface, COLORS["wall"], (cx - door_w // 2, ROOM.bottom - 6, door_w, door_h))


def draw_hud(surface, player, enemies_left):
    font = pygame.font.Font(None, 14)
    label = font.render("VIDA", True, COLORS["white"])
    surface.blit(label, (ROOM.left + 3, 5))

    for i in range(PLAYER_MAX_HP // 2):
        x = ROOM.left + 31 + i * 13
        color = COLORS["red"] if player.hp >= (i + 1) * 2 else COLORS["dark_red"]
        pygame.draw.rect(surface, color, (x, 7, 10, 8))
        pygame.draw.rect(surface, COLORS["white"], (x + 2, 8, 2, 2))

    status = font.render(f"INIMIGOS: {enemies_left}", True, COLORS["white"])
    surface.blit(status, (ROOM.right - status.get_width() - 3, 5))


def reset_game():
    return Player(), spawn_enemies(4), [], 0, False


player, enemies, tears, shoot_timer, game_over = reset_game()
damage_flash_until = 0

running = True
while running:
    dt = clock.tick(FPS)
    now = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            if game_over and event.key == pygame.K_r:
                player, enemies, tears, shoot_timer, game_over = reset_game()

    keys = pygame.key.get_pressed()

    if not game_over:
        player.move(keys)

        # Mira independente do movimento: setas disparam em quatro direcoes.
        aim_x = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        aim_y = int(keys[pygame.K_DOWN]) - int(keys[pygame.K_UP])

        shoot_timer = max(0, shoot_timer - 1)
        if (aim_x or aim_y) and shoot_timer == 0:
            length = math.hypot(aim_x, aim_y)
            tears.append(Tear(player.x, player.y, aim_x / length, aim_y / length))
            shoot_timer = TEAR_COOLDOWN

        for tear in tears[:]:
            tear.update()
            if (tear.life <= 0 or
                not ROOM.inflate(-5, -5).collidepoint(tear.x, tear.y)):
                tears.remove(tear)
                continue

            hit_enemy = None
            for enemy in enemies:
                if circle_rect_collision(tear.x, tear.y, tear.radius, enemy.rect):
                    hit_enemy = enemy
                    break

            if hit_enemy:
                hit_enemy.hp -= 1
                hit_enemy.flash = 5
                if tear in tears:
                    tears.remove(tear)
                if hit_enemy.hp <= 0:
                    enemies.remove(hit_enemy)

        for enemy in enemies:
            enemy.update(player)
            if enemy.rect.colliderect(player.rect) and now >= player.invulnerable_until:
                player.hp -= 1
                player.invulnerable_until = now + INVULN_TIME
                if player.hp <= 0:
                    game_over = True

        if not enemies:
            # Ao limpar a sala, aparece uma nova leva para manter o prototipo jogavel.
            enemies = spawn_enemies(5)

    # Renderizacao em baixa resolucao, ampliada com filtro nearest-neighbor.
    draw_room(canvas)
    for tear in tears:
        tear.draw(canvas)
    for enemy in enemies:
        enemy.draw(canvas)
    player.draw(canvas)
    draw_hud(canvas, player, len(enemies))

    if game_over:
        overlay = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 8, 15, 190))
        canvas.blit(overlay, (0, 0))
        big = pygame.font.Font(None, 34)
        small = pygame.font.Font(None, 17)
        title = big.render("VOCE MORREU", True, COLORS["white"])
        hint = small.render("Pressione R para tentar novamente", True, COLORS["gold"])
        canvas.blit(title, title.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 - 12)))
        canvas.blit(hint, hint.get_rect(center=(VIRTUAL_WIDTH // 2, VIRTUAL_HEIGHT // 2 + 14)))

    pygame.transform.scale(canvas, (WIDTH, HEIGHT), screen)
    pygame.display.flip()
dungeon = {
    (0, 0): ["N", "S", "E"],
    (0, 1): ["N", "W"],
    (1, 0): ["W", "E"],
    (2, 0): ["W"]
}
directions = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0)
}

current_room = (0, 0)

for direction, (dx, dy) in directions.items():
    neighbor = (
        current_room[0] + dx,
        current_room[1] + dy
    )

    print(direction, neighbor)
import random

DIRECTIONS = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0)
}

def generate_dungeon(total_rooms=9):
    rooms = {(0, 0)}

    while len(rooms) < total_rooms:
        current = random.choice(list(rooms))
        direction = random.choice(list(DIRECTIONS.values()))

        new_room = (
            current[0] + direction[0],
            current[1] + direction[1]
        )

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
import random

DIRECTIONS = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0)
}

def generate_dungeon(total_rooms=9):
    rooms = {(0, 0)}

    while len(rooms) < total_rooms:
        current = random.choice(list(rooms))
        direction = random.choice(list(DIRECTIONS.values()))

        new_room = (
            current[0] + direction[0],
            current[1] + direction[1]
        )

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
class Room:

    def __init__(self, position, neighbors):
        self.position = position
        self.neighbors = neighbors

        self.enemies = []
        self.visited = False
        self.cleared = False

    def update(self):
        if len(self.enemies) == 0:
            self.cleared = True

    def is_door_open(self, direction):
        return (
            direction in self.neighbors
            and self.cleared
        )
def is_door_open(self, direction):
    return direction in self.neighbors and self.cleared
def change_room(game, direction):

    current = game.current_room

    if not current.is_door_open(direction):
        return

    next_position = current.neighbors[direction]

    game.current_room = game.rooms[next_position]

    # Posicionar jogador na entrada oposta
    if direction == "N":
        game.player.x = 480
        game.player.y = 560

    elif direction == "S":
        game.player.x = 480
        game.player.y = 80

    elif direction == "E":
        game.player.x = 80
        game.player.y = 320

    elif direction == "W":
        game.player.x = 880
        game.player.y = 320
class Room:
    def __init__(self):
        self.enemies = []
        self.horde_started = False
        self.cleared = False

    def start_horde(self):
        if self.horde_started:
            return

        self.horde_started = True
        self.enemies = create_horde()

    def update(self):
        if self.horde_started and len(self.enemies) == 0:
            self.cleared = True
def enter_room(room):
    room.start_horde()



ENEMY_TYPES = {
    "fly": {
        "health": 2,
        "speed": 1.5,
        "damage": 1
    },

    "chaser": {
        "health": 3,
        "speed": 1.0,
        "damage": 1
    },

    "tank": {
        "health": 8,
        "speed": 0.4,
        "damage": 2
    }
}
class Enemy:

    def __init__(self, x, y, enemy_type):

        stats = ENEMY_TYPES[enemy_type]

        self.x = x
        self.y = y

        self.health = stats["health"]
        self.speed = stats["speed"]
        self.damage = stats["damage"]

        self.enemy_type = enemy_type
import random

enemy_type = random.choice([
    "fly",
    "chaser",
    "tank"
])

enemy = Enemy(300, 200, enemy_type)




pygame.quit()
