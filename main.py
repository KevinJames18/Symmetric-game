import pygame
import time
import math
from utils import scale_image, blit_rotate_center

pygame.init()
pygame.mixer.init()

FONT = pygame.font.SysFont("comicsans", 80)
LAP_FONT = pygame.font.SysFont("comicsans", 30)

GRASS = scale_image(pygame.image.load("grass.jpg"), 2.5)
TRACK = scale_image(pygame.image.load("track.png"), 0.9)

TRACK_BORDER = scale_image(pygame.image.load("track-border.png"), 0.9)
TRACK_BORDER_MASK = pygame.mask.from_surface(TRACK_BORDER)

FINISH = scale_image(pygame.image.load("finish.png"), 0.5)
FINISH_MASK = pygame.mask.from_surface(FINISH)
FINISH_POS = (150, 200)  # Finish line position

# checkpoint as a visible marker 
CHECKPOINT_SIZE = 25
CHECKPOINT = pygame.Surface((CHECKPOINT_SIZE, CHECKPOINT_SIZE), pygame.SRCALPHA)
pygame.draw.circle(CHECKPOINT, (255, 255, 0, 200), (CHECKPOINT_SIZE//2, CHECKPOINT_SIZE//2), CHECKPOINT_SIZE//2)
CHECKPOINT_MASK = pygame.mask.from_surface(CHECKPOINT)

# IMPORTANT: Adjust this checkpoint position based on your track layout
CHECKPOINT_POS = (500, 465)  

RED_CAR = scale_image(pygame.image.load("red-car.png"), 0.55)
GREEN_CAR = scale_image(pygame.image.load("green-car.png"), 0.55)

sound_3 = pygame.mixer.Sound("3.mp3")
sound_2 = pygame.mixer.Sound("2.mp3")
sound_1 = pygame.mixer.Sound("1.mp3")
sound_go = pygame.mixer.Sound("GO.mp3")

pygame.mixer.music.load("bg_music.mp3")
pygame.mixer.music.set_volume(0.5)

WIDTH, HEIGHT = TRACK.get_width(), TRACK.get_height()
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("1v1 Racing Game!")

FPS = 60


class AbstractCar:
    def __init__(self, max_vel, rotation_vel):
        self.img = self.IMG
        self.max_vel = max_vel
        self.vel = 0
        self.rotation_vel = rotation_vel
        self.angle = 0
        self.x, self.y = self.START_POS
        self.acceleration = 0.1

        self.lap = 0
        self.crossed_finish = False
        self.has_left_start = False
        
        # Checkpoint tracking
        self.checkpoint_hit = False
        self.checkpoint2_hit = False  # For second checkpoint
        
        # Store previous position for direction checking
        self.prev_y = self.y

        self.last_collision_time = time.time()
        self.boost_active = False
        self.boost_multiplier = 1.5

    def rotate(self, left=False, right=False):
        if left:
            self.angle += self.rotation_vel
        elif right:
            self.angle -= self.rotation_vel

    def draw(self, win):
        blit_rotate_center(win, self.img, (self.x, self.y), self.angle)

    def collide(self, mask, x=0, y=0):
        rotated_image = pygame.transform.rotate(self.img, self.angle)
        car_mask = pygame.mask.from_surface(rotated_image)

        offset = (
            int(self.x - x + (self.img.get_width() - rotated_image.get_width()) / 2),
            int(self.y - y + (self.img.get_height() - rotated_image.get_height()) / 2)
        )
        return mask.overlap(car_mask, offset)

    def collide_car(self, other_car):
        rotated_self = pygame.transform.rotate(self.img, self.angle)
        self_mask = pygame.mask.from_surface(rotated_self)

        rotated_other = pygame.transform.rotate(other_car.img, other_car.angle)
        other_mask = pygame.mask.from_surface(rotated_other)

        offset = (
            int(self.x - other_car.x + (self.img.get_width() - rotated_self.get_width()) / 2),
            int(self.y - other_car.y + (self.img.get_height() - rotated_self.get_height()) / 2)
        )
        return other_mask.overlap(self_mask, offset)

    def move(self, other_car=None):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.vel
        horizontal = math.sin(radians) * self.vel

        collision = False

        self.x -= horizontal
        if self.collide(TRACK_BORDER_MASK) or (other_car and self.collide_car(other_car)):
            self.x += horizontal
            collision = True

        self.y -= vertical
        if self.collide(TRACK_BORDER_MASK) or (other_car and self.collide_car(other_car)):
            self.y += vertical
            collision = True

        if collision:
            self.last_collision_time = time.time()
            self.boost_active = False

        if time.time() - self.last_collision_time >= 3:
            self.boost_active = True

    def move_forward(self, other_car=None):
        multiplier = self.boost_multiplier if self.boost_active else 1
        self.vel = min(self.vel + self.acceleration * multiplier,
                       self.max_vel * multiplier)
        self.move(other_car)

    def reduce_speed(self, other_car=None):
        self.vel = max(self.vel - self.acceleration / 10, 0)
        self.move(other_car)

    def check_checkpoint(self, checkpoint_mask, checkpoint_pos):
        """Check if car hits a checkpoint"""
        rotated_image = pygame.transform.rotate(self.img, self.angle)
        car_mask = pygame.mask.from_surface(rotated_image)

        offset = (
            int(self.x - checkpoint_pos[0] + (self.img.get_width() - rotated_image.get_width()) / 2),
            int(self.y - checkpoint_pos[1] + (self.img.get_height() - rotated_image.get_height()) / 2)
        )

        return checkpoint_mask.overlap(car_mask, offset)

    def check_finish(self, finish_mask, finish_pos):
        rotated_image = pygame.transform.rotate(self.img, self.angle)
        car_mask = pygame.mask.from_surface(rotated_image)

        offset = (
            int(self.x - finish_pos[0] + (self.img.get_width() - rotated_image.get_width()) / 2),
            int(self.y - finish_pos[1] + (self.img.get_height() - rotated_image.get_height()) / 2)
        )

        collide = finish_mask.overlap(car_mask, offset)
        
        # Check if car is moving in the correct direction
        is_moving_forward = self.y < self.prev_y  # Adjust based on your track orientation
        
        if collide:
            # Only count lap if:
            # 1. Has left start position
            # 2. Hasn't crossed finish line yet in this lap segment
            # 3. Is moving forward (not going backward)
            # 4. Has hit all checkpoints first (completed the full track)
            if self.has_left_start and not self.crossed_finish and is_moving_forward:
                if self.checkpoint_hit:  # At least one checkpoint is required
                    self.lap += 1
                    # Reset checkpoints for next lap
                    self.checkpoint_hit = False
                    self.checkpoint2_hit = False
                    print(f"Lap {self.lap} completed!")
            self.crossed_finish = True
        else:
            if not self.has_left_start:
                self.has_left_start = True
            self.crossed_finish = False
        
        # Update previous Y position for next frame
        self.prev_y = self.y


class PlayerCar(AbstractCar):
    IMG = RED_CAR
    START_POS = (185, 250)


class Player2Car(AbstractCar):
    IMG = GREEN_CAR
    START_POS = (150, 250)


def draw(win, images, car1, car2, countdown_text=""):
    for img, pos in images:
        win.blit(img, pos)

    # Draw checkpoints
    win.blit(CHECKPOINT, CHECKPOINT_POS)
    
    win.blit(FINISH, FINISH_POS)

    car1.draw(win)
    car2.draw(win)

    red_lap_text = LAP_FONT.render(f"RED: {car1.lap}/3", True, (255, 0, 0))
    green_lap_text = LAP_FONT.render(f"GREEN: {car2.lap}/3", True, (0, 255, 0))

    win.blit(red_lap_text, (20, 20))
    win.blit(green_lap_text, (20, 60))

    # Removed checkpoint status text (Red: CP1 and Green: CP1)

    if car1.boost_active:
        win.blit(LAP_FONT.render("RED BOOST!", True, (255, 255, 0)), (WIDTH - 220, 20))

    if car2.boost_active:
        win.blit(LAP_FONT.render("GREEN BOOST!", True, (255, 255, 0)), (WIDTH - 260, 60))

    if countdown_text != "":
        text = FONT.render(countdown_text, True, (255, 255, 0))
        win.blit(text, (WIDTH // 2 - text.get_width() // 2,
                        HEIGHT // 2 - text.get_height() // 2))

    pygame.display.update()


def draw_pause_menu():
    WIN.fill((0, 0, 0))

    title = FONT.render("PAUSED", True, (255, 255, 255))
    resume = LAP_FONT.render("R - Resume", True, (0, 255, 0))
    restart = LAP_FONT.render("N - New Game", True, (255, 255, 0))
    quit_text = LAP_FONT.render("Q - Quit", True, (255, 0, 0))

    WIN.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 120))
    WIN.blit(resume, (WIDTH // 2 - resume.get_width() // 2, HEIGHT // 2 - 40))
    WIN.blit(restart, (WIDTH // 2 - restart.get_width() // 2, HEIGHT // 2))
    WIN.blit(quit_text, (WIDTH // 2 - quit_text.get_width() // 2, HEIGHT // 2 + 40))

    pygame.display.update()


def reset_game():
    global player1, player2, race_started, start_time, last_count, game_started

    player1 = PlayerCar(4, 4)
    player2 = Player2Car(4, 4)

    race_started = False
    start_time = pygame.time.get_ticks()
    game_started = True

    last_count = None

    pygame.mixer.music.stop()


def draw_winner_menu(text):
    pygame.mixer.music.stop()
    while True:
        WIN.fill((0, 0, 0))

        color = (255, 0, 0) if "RED" in text else (0, 255, 0)

        win_text = FONT.render(text, True, color)
        restart_text = LAP_FONT.render("R - Restart", True, (255, 255, 0))
        quit_text = LAP_FONT.render("Q - Quit", True, (255, 0, 0))

        WIN.blit(win_text,
                 (WIDTH // 2 - win_text.get_width() // 2,
                  HEIGHT // 2 - 100))

        WIN.blit(restart_text,
                 (WIDTH // 2 - restart_text.get_width() // 2,
                  HEIGHT // 2))

        WIN.blit(quit_text,
                 (WIDTH // 2 - quit_text.get_width() // 2,
                  HEIGHT // 2 + 50))

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    reset_game()
                    return

                if event.key == pygame.K_q:
                    pygame.quit()
                    exit()


run = True
clock = pygame.time.Clock()
images = [(GRASS, (0, 0)), (TRACK, (0, 0))]

player1 = PlayerCar(4, 4)
player2 = Player2Car(4, 4)

start_time = 0
race_started = False
game_started = False
paused = False
last_count = None

# Debug mode to help find correct checkpoint positions
debug_mode = True
if debug_mode:
    print("=== CHECKPOINT PLACEMENT HELP ===")
    print(f"Screen size: {WIDTH} x {HEIGHT}")
    print(f"Start positions: Red at {player1.START_POS}, Green at {player2.START_POS}")
    print(f"Finish line at: {FINISH_POS}")
    print("\nSuggested checkpoint positions:")
    print("- Place checkpoint 1 at a far corner of the track")
    print("- Place checkpoint 2 at another strategic location")
    print(f"\nCurrent checkpoint 1 position: {CHECKPOINT_POS}")
    print("\nYou can adjust these coordinates in the code at the top!")

while run:
    clock.tick(FPS)

    # START SCREEN
    if not game_started:
        WIN.fill((0, 0, 0))

        title = FONT.render("1v1 RACING GAME", True, (255, 255, 255))
        start_text = LAP_FONT.render("PRESS SPACE TO START", True, (255, 255, 0))

        WIN.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 100))
        WIN.blit(start_text, (WIDTH // 2 - start_text.get_width() // 2, HEIGHT // 2))

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE]:
            game_started = True
            start_time = pygame.time.get_ticks()

        continue

    # EVENTS
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and race_started:
                paused = not paused

    if paused:
        pygame.mixer.music.pause()
    else:
        pygame.mixer.music.unpause()

    # PAUSE MENU
    if paused:
        draw_pause_menu()
        keys = pygame.key.get_pressed()

        if keys[pygame.K_r]:
            paused = False

        if keys[pygame.K_n]:
            pygame.mixer.music.stop()
            reset_game()
            paused = False

        if keys[pygame.K_q]:
            run = False

        continue

    # COUNTDOWN
    elapsed_time = (pygame.time.get_ticks() - start_time) / 1000
    countdown_text = ""

    if not race_started:
        if elapsed_time < 1:
            countdown_text = "3"
        elif elapsed_time < 2:
            countdown_text = "2"
        elif elapsed_time < 3:
            countdown_text = "1"
        elif elapsed_time < 4:
            countdown_text = "GO!"
        else:
            race_started = True

        if countdown_text != last_count:
            if countdown_text == "3":
                sound_3.play()
            elif countdown_text == "2":
                sound_2.play()
            elif countdown_text == "1":
                sound_1.play()
            elif countdown_text == "GO!":
                sound_go.play()
                pygame.mixer.music.play(-1)

            last_count = countdown_text

    # Check checkpoints
    if race_started:
        # Check checkpoint 1 for player 1
        if player1.check_checkpoint(CHECKPOINT_MASK, CHECKPOINT_POS):
            if not player1.checkpoint_hit and player1.has_left_start:
                player1.checkpoint_hit = True
                print("Red car hit checkpoint 1!")
        
      
        # Check checkpoint 1 for player 2
        if player2.check_checkpoint(CHECKPOINT_MASK, CHECKPOINT_POS):
            if not player2.checkpoint_hit and player2.has_left_start:
                player2.checkpoint_hit = True
                print("Green car hit checkpoint 1!")
        

    draw(WIN, images, player1, player2, countdown_text)

    keys = pygame.key.get_pressed()

    if race_started:
        moved1 = False
        if keys[pygame.K_a]:
            player1.rotate(left=True)
        if keys[pygame.K_d]:
            player1.rotate(right=True)
        if keys[pygame.K_w]:
            moved1 = True
            player1.move_forward(player2)
        if not moved1:
            player1.reduce_speed(player2)

        moved2 = False
        if keys[pygame.K_LEFT]:
            player2.rotate(left=True)
        if keys[pygame.K_RIGHT]:
            player2.rotate(right=True)
        if keys[pygame.K_UP]:
            moved2 = True
            player2.move_forward(player1)
        if not moved2:
            player2.reduce_speed(player1)

    player1.check_finish(FINISH_MASK, FINISH_POS)
    player2.check_finish(FINISH_MASK, FINISH_POS)

    if player1.lap >= 4:
        draw_winner_menu("RED WINS!")

    if player2.lap >= 4:
        draw_winner_menu("GREEN WINS!")

pygame.quit()