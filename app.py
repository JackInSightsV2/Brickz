import pygame, sys, random, math

# --- Configuration ---
SCREEN_WIDTH = 300
SCREEN_HEIGHT = 500
FPS = 60

BRICK_SIZE = 50      # each cell is 50x50 pixels
BRICK_COLS = SCREEN_WIDTH // BRICK_SIZE  # should be 6
MAX_ROWS = SCREEN_HEIGHT // BRICK_SIZE   # total number of rows (here 10)

# Ball settings
BALL_RADIUS = 5
BALL_SPEED = 12  # ball speed

# Colors (using pastel values)
BG_COLOR = (30, 30, 30)
BALL_COLOR = (255, 255, 255)
AIM_LINE_COLOR = (150, 150, 150)  # muted pastel gray for the aiming line
TEXT_COLOR = (255, 255, 255)      # default text color (white)

# Pastel brick colors:
PASTEL_GREEN = (180, 230, 180)  # full health color
PASTEL_PINK  = (255, 180, 180)  # near-depleted color

# --- Global Game State ---
score = 0         # current score
high_score = 0    # session high score
lives = 3         # player starts with 3 lives
highest_level = 1 # highest level reached in session
lives_flash_timer = 0  # timer for flashing the lives text when a life is lost
dying_bricks = [] # list for bricks that are being animated when removed

# --- Utility Functions ---
def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

def get_ball_count(level):
    """
    Returns the number of balls for the given level based on the formula y = 2x.
    At level x, there are 2*x balls.
    """
    return 2 * level

def normalize(vx, vy):
    mag = math.sqrt(vx*vx + vy*vy)
    if mag == 0:
        return 0, 0
    return vx/mag, vy/mag

def ball_colliding_brick(ball, brick):
    """Return True if the ball's circle overlaps the brick's padded rectangle."""
    rect = brick.rect
    closest_x = clamp(ball.x, rect.left, rect.right)
    closest_y = clamp(ball.y, rect.top, rect.bottom)
    dx = ball.x - closest_x
    dy = ball.y - closest_y
    return (dx*dx + dy*dy) < (BALL_RADIUS * BALL_RADIUS)

def format_number(num):
    """Formats a number using shorthand notation."""
    if num < 1000:
        return str(num)
    elif num < 1_000_000:
        return f"{num/1000:.0f}k"
    elif num < 1_000_000_000:
        return f"{num/1_000_000:.0f}m"
    elif num < 1_000_000_000_000:
        return f"{num/1_000_000_000:.0f}b"
    elif num < 1_000_000_000_000_000:
        return f"{num/1_000_000_000_000:.0f}t"
    else:
        return str(num)

# --- Classes ---
class Ball:
    def __init__(self, x, y, angle):
        self.x = x
        self.y = y
        self.angle = angle
        self.dx = BALL_SPEED * math.cos(angle)
        self.dy = -BALL_SPEED * math.sin(angle)  # negative because y increases downward
        self.active = True
        self.launched = False
        self.delay = 0  # absolute frame count at which to launch this ball
        self.collision_cooldown = 0  # frames during which collisions are ignored

    def update(self):
        if self.collision_cooldown > 0:
            self.collision_cooldown -= 1

        self.x += self.dx
        self.y += self.dy

        # Bounce off left/right walls.
        if self.x - BALL_RADIUS <= 0:
            self.x = BALL_RADIUS
            self.dx = -self.dx
        elif self.x + BALL_RADIUS >= SCREEN_WIDTH:
            self.x = SCREEN_WIDTH - BALL_RADIUS
            self.dx = -self.dx

        # Bounce off top wall.
        if self.y - BALL_RADIUS <= 0:
            self.y = BALL_RADIUS
            self.dy = -self.dy

        # When hitting the bottom, the ball stops.
        if self.y + BALL_RADIUS >= SCREEN_HEIGHT:
            self.active = False
            self.y = SCREEN_HEIGHT - BALL_RADIUS

    def draw(self, screen):
        pygame.draw.circle(screen, BALL_COLOR, (int(self.x), int(self.y)), BALL_RADIUS)

class Brick:
    def __init__(self, col, row, value):
        self.col = col
        self.row = row
        self.value = value         # current hit points
        self.max_value = value     # starting hit points

    @property
    def rect(self):
        # Return a rectangle with a 1-pixel padding on all sides.
        return pygame.Rect(
            self.col * BRICK_SIZE + 1,
            self.row * BRICK_SIZE + 1,
            BRICK_SIZE - 2,
            BRICK_SIZE - 2
        )

    def draw(self, screen):
        ratio = max(0, min(1, self.value / self.max_value))
        r = int(PASTEL_GREEN[0] + (PASTEL_PINK[0] - PASTEL_GREEN[0]) * (1 - ratio))
        g = int(PASTEL_GREEN[1] + (PASTEL_PINK[1] - PASTEL_GREEN[1]) * (1 - ratio))
        b = int(PASTEL_GREEN[2] + (PASTEL_PINK[2] - PASTEL_GREEN[2]) * (1 - ratio))
        color = (r, g, b)
        pygame.draw.rect(screen, color, self.rect)
        font = pygame.font.SysFont(None, 24)
        text = font.render(str(max(0, self.value)), True, TEXT_COLOR)
        text_rect = text.get_rect(center=self.rect.center)
        screen.blit(text, text_rect)

# --- Collision Resolution Function ---
def resolve_collision(ball, brick):
    """
    Push the ball completely out of the brick's rectangle (treated as an impenetrable zone)
    and reflect its velocity.
    """
    rect = brick.rect
    if rect.collidepoint(ball.x, ball.y):
        left_pen = ball.x - rect.left
        right_pen = rect.right - ball.x
        top_pen = ball.y - rect.top
        bottom_pen = rect.bottom - ball.y
        min_pen = min(left_pen, right_pen, top_pen, bottom_pen)
        if min_pen == left_pen:
            normal = (-1, 0)
            ball.x = rect.left - BALL_RADIUS
        elif min_pen == right_pen:
            normal = (1, 0)
            ball.x = rect.right + BALL_RADIUS
        elif min_pen == top_pen:
            normal = (0, -1)
            ball.y = rect.top - BALL_RADIUS
        else:
            normal = (0, 1)
            ball.y = rect.bottom + BALL_RADIUS
    else:
        closest_x = clamp(ball.x, rect.left, rect.right)
        closest_y = clamp(ball.y, rect.top, rect.bottom)
        dx = ball.x - closest_x
        dy = ball.y - closest_y
        d = math.sqrt(dx*dx + dy*dy)
        if d == 0:
            if abs(ball.dx) > abs(ball.dy):
                normal = (math.copysign(1, ball.dx), 0)
            else:
                normal = (0, math.copysign(1, ball.dy))
            d = 0.001
        else:
            normal = (dx/d, dy/d)
        if d < BALL_RADIUS:
            correction = BALL_RADIUS - d
            ball.x += normal[0] * correction
            ball.y += normal[1] * correction

    dot = ball.dx * normal[0] + ball.dy * normal[1]
    ball.dx = ball.dx - 2 * dot * normal[0]
    ball.dy = ball.dy - 2 * dot * normal[1]
    ndx, ndy = normalize(ball.dx, ball.dy)
    ball.dx = ndx * BALL_SPEED
    ball.dy = ndy * BALL_SPEED

# --- Game Setup ---
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Brick Shooter")
clock = pygame.time.Clock()

# Initialize game state variables
level = 1
base_ball_count = get_ball_count(level)
balls_to_fire = []            # list of Ball objects (active or waiting)
returned_ball_positions = []  # x positions where balls return
base_x = SCREEN_WIDTH // 2    # starting x for firing balls
aim_angle = math.pi / 4       # default firing angle (45°)
firing = False                # whether balls are currently being fired
launch_start = 0              # global frame at which the current firing sequence started

# Lives, score, high score, and highest level persist across games.
lives = 3
score = 0
high_score = 0
highest_level = 1

# List of bricks
bricks = []

def spawn_new_row():
    global bricks, level
    count = random.randint(1, 4)  # spawn between 1 and 4 bricks
    cols = random.sample(range(BRICK_COLS), count)
    for col in cols:
        brick = Brick(col, 1, level)
        bricks.append(brick)

def move_bricks_down():
    global bricks
    new_bricks = []
    for brick in bricks:
        brick.row += 1
        new_bricks.append(brick)
    bricks = new_bricks

def remove_bottom_rows(n):
    """
    Remove bricks that are in the bottom n rows.
    """
    global bricks
    threshold = MAX_ROWS - n  # e.g., if MAX_ROWS=10 and n=3, remove bricks with row >= 7.
    dying = [brick for brick in bricks if brick.row >= threshold]
    for brick in dying:
        dying_bricks.append({'brick': brick, 'timer': 30})
    bricks = [brick for brick in bricks if brick.row < threshold]

def check_bricks_bottom():
    """
    If any brick's grid row is greater than or equal to 9 (i.e. row 10 is touched),
    lose a life and remove the bottom 3 rows.
    """
    global lives, highest_level, level, lives_flash_timer
    for brick in bricks:
        if brick.row >= 9:
            lives -= 1
            lives_flash_timer = 30  # Start the flash for lives text.
            remove_bottom_rows(3)
            break

def reset_for_next_turn():
    global level, base_ball_count, balls_to_fire, returned_ball_positions, firing, base_x, launch_start, frame_count, highest_level
    if returned_ball_positions:
        new_base_x = returned_ball_positions[0]
        base_x = max(BALL_RADIUS, min(SCREEN_WIDTH - BALL_RADIUS, int(new_base_x)))
    level += 1
    if level > highest_level:
        highest_level = level
    base_ball_count = get_ball_count(level)
    move_bricks_down()
    spawn_new_row()
    balls_to_fire = []
    returned_ball_positions = []
    firing = False

def fire_balls():
    global balls_to_fire, firing, launch_start, frame_count
    firing = True
    balls_to_fire = []
    launch_start = frame_count
    launch_delay = 5  # 5 frames delay between each ball's launch.
    for i in range(base_ball_count):
        ball = Ball(base_x, SCREEN_HEIGHT - BALL_RADIUS, aim_angle)
        ball.delay = launch_start + i * launch_delay
        ball.launched = False
        balls_to_fire.append(ball)

def new_game():
    """
    Resets the game state for a new game.
    Note: The session high score and highest level persist.
    """
    global level, base_ball_count, balls_to_fire, returned_ball_positions, base_x, aim_angle, firing, launch_start, lives, score, bricks, frame_count, game_over, dying_bricks, highest_level, lives_flash_timer
    level = 1
    base_ball_count = get_ball_count(level)
    balls_to_fire = []
    returned_ball_positions = []
    base_x = SCREEN_WIDTH // 2
    aim_angle = math.pi / 4
    firing = False
    launch_start = 0
    lives = 3
    score = 0
    bricks = []
    dying_bricks.clear()
    highest_level = 1
    lives_flash_timer = 0
    spawn_new_row()
    frame_count = 0
    game_over = False

# Spawn the initial row so that the game starts with bricks.
spawn_new_row()

# --- Main Game Loop ---
frame_count = 0
running = True
game_over = False

while running:
    dt = clock.tick(FPS)
    frame_count += 1

    # --- Event Handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if not game_over:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    base_x -= 10
                    if base_x < BALL_RADIUS:
                        base_x = BALL_RADIUS
                elif event.key == pygame.K_RIGHT:
                    base_x += 10
                    if base_x > SCREEN_WIDTH - BALL_RADIUS:
                        base_x = SCREEN_WIDTH - BALL_RADIUS
                elif event.key == pygame.K_SPACE and not firing:
                    fire_balls()
            if event.type == pygame.MOUSEMOTION:
                mx, my = pygame.mouse.get_pos()
                dx = mx - base_x
                dy = (SCREEN_HEIGHT - BALL_RADIUS) - my
                if dy <= 0:
                    dy = 1
                aim_angle = math.atan2(dy, dx)
        else:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    new_game()

    if not game_over:
        # --- Update Balls ---
        if firing:
            for ball in balls_to_fire:
                if not ball.launched and frame_count >= ball.delay:
                    ball.launched = True

            for ball in balls_to_fire:
                if ball.launched and ball.active:
                    ball.update()
                    max_iterations = 10
                    iterations = 0
                    collision_found = True
                    while collision_found and iterations < max_iterations:
                        collision_found = False
                        for brick in bricks[:]:
                            if ball_colliding_brick(ball, brick):
                                brick.value -= 1
                                score += 10
                                if score > high_score:
                                    high_score = score
                                ball.collision_cooldown = 10
                                resolve_collision(ball, brick)
                                collision_found = True
                                if brick.value <= 0:
                                    bricks.remove(brick)
                                break
                        iterations += 1

            if all(ball.launched and not ball.active for ball in balls_to_fire):
                for ball in balls_to_fire:
                    returned_ball_positions.append(ball.x)
                reset_for_next_turn()
                frame_count = 0

        # Check if any brick has reached row 9 or greater.
        check_bricks_bottom()

        if lives <= 0:
            game_over = True

    # Update the lives flash timer (for flashing the lives text)
    if lives_flash_timer > 0:
        lives_flash_timer -= 1

    # Update dying bricks (fade-out animation)
    for item in dying_bricks[:]:
        item['timer'] -= 1
        if item['timer'] <= 0:
            dying_bricks.remove(item)

    # --- Drawing ---
    screen.fill(BG_COLOR)

    for brick in bricks:
        brick.draw(screen)

    for item in dying_bricks:
        brick = item['brick']
        timer = item['timer']
        alpha = int(255 * (timer / 30))
        s = pygame.Surface((BRICK_SIZE - 2, BRICK_SIZE - 2), pygame.SRCALPHA)
        ratio = max(0, min(1, brick.value / brick.max_value))
        r = int(PASTEL_GREEN[0] + (PASTEL_PINK[0] - PASTEL_GREEN[0]) * (1 - ratio))
        g = int(PASTEL_GREEN[1] + (PASTEL_PINK[1] - PASTEL_GREEN[1]) * (1 - ratio))
        b = int(PASTEL_GREEN[2] + (PASTEL_PINK[2] - PASTEL_GREEN[2]) * (1 - ratio))
        s.fill((r, g, b, alpha))
        screen.blit(s, (brick.rect.x, brick.rect.y))

    # Draw Score and High Score at the top.
    font = pygame.font.SysFont(None, 24)
    score_text = font.render(f"Score: {format_number(score)}", True, TEXT_COLOR)
    high_text = font.render(f"High: {format_number(high_score)}", True, TEXT_COLOR)
    score_rect = score_text.get_rect(topleft=(10, 10))
    high_rect = high_text.get_rect(topright=(SCREEN_WIDTH - 10, 10))
    screen.blit(score_text, score_rect)
    screen.blit(high_text, high_rect)

    # Draw H-Level (highest level achieved) below the High Score.
    hlevel_text = font.render(f"H-Level: {highest_level}", True, TEXT_COLOR)
    hlevel_rect = hlevel_text.get_rect(topright=(SCREEN_WIDTH - 10, 30))
    screen.blit(hlevel_text, hlevel_rect)

    # Draw Level and Lives at the bottom.
    level_text = font.render(f"Level: {level}", True, TEXT_COLOR)
    # For Lives, if the lives_flash_timer is active, interpolate from red to white.
    if lives_flash_timer > 0:
        ratio = (30 - lives_flash_timer) / 30  # 0 at start, 1 at end.
        lives_color = (255, int(255 * ratio), int(255 * ratio))
    else:
        lives_color = TEXT_COLOR
    lives_text = font.render(f"Lives: {lives}", True, lives_color)
    level_rect = level_text.get_rect(bottomleft=(10, SCREEN_HEIGHT - 10))
    lives_rect = lives_text.get_rect(bottomright=(SCREEN_WIDTH - 10, SCREEN_HEIGHT - 10))
    screen.blit(level_text, level_rect)
    screen.blit(lives_text, lives_rect)

    # Draw aiming line (dotted, 200 pixels long, 5px dashes, 5px gaps, thickness 3) when not firing and game not over.
    if not firing and not game_over:
        start_pos = (base_x, SCREEN_HEIGHT - BALL_RADIUS)
        direction = (math.cos(aim_angle), -math.sin(aim_angle))
        total_length = 200
        dash_length = 5
        gap_length = 5
        num_dashes = total_length // (dash_length + gap_length)
        for i in range(int(num_dashes)):
            start_dash = (start_pos[0] + direction[0] * i * (dash_length + gap_length),
                          start_pos[1] + direction[1] * i * (dash_length + gap_length))
            end_dash = (start_dash[0] + direction[0] * dash_length,
                        start_dash[1] + direction[1] * dash_length)
            pygame.draw.line(screen, AIM_LINE_COLOR, start_dash, end_dash, 3)

    pygame.draw.circle(screen, BALL_COLOR, (base_x, SCREEN_HEIGHT - BALL_RADIUS), BALL_RADIUS)

    if firing:
        for ball in balls_to_fire:
            if ball.launched:
                ball.draw(screen)

    if game_over:
        over_font = pygame.font.SysFont(None, 48)
        over_text = over_font.render("GAME OVER", True, (255, 0, 0))
        over_rect = over_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 20))
        restart_text = font.render("Press SPACE to restart", True, (255, 255, 0))
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 20))
        screen.blit(over_text, over_rect)
        screen.blit(restart_text, restart_rect)

    pygame.display.flip()

pygame.quit()
sys.exit()
