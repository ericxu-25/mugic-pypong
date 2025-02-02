import time
import pygame
import math
from collections import namedtuple
# import mugic_helper
# pypong stuff would go here

# Resources used as reference:
# * geeksforgeeks.org/create-a-pong-game-in-python-pygame/
# * https://www.pygame.org/docs/
# * https://stackoverflow.com/questions/11603222/allowing-resizing-window-pygame

# TODO list
# * advanced ball physics (spin, bounce)
# * rotating striker
# * springy striker
# * mugic controller registration debug

# GLOBALS
pygame.font.init()
FREESANS = 'freesansbold.ttf'

class Color:
    black = (0,0,0)
    white = (255, 255, 255)
    green = (0, 255, 0)

WIDTH, HEIGHT = 1300, 600

# HELPERS
class Key():
    def __init__(self, key_event):
        if key_event.type == pygame.KEYDOWN:
            self.down = True
        elif key_event.type == pygame.KEYUP:
            self.down = False
        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            self.shift = True
        else: self.shift = False
        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.control = True
        else: control = False
        if pygame.key.get_mods() & pygame.KMOD_ALT:
            self.alt = True
        else: self.alt = False
        self.key = key_event.key

    def __eq__(self, other):
        return self.key == other

class GameSprite(pygame.sprite.DirtySprite):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.dirty = 1
        self.visible = 1
        self.blendmode = 0
        self.source_rect = None
        self.layer = 0
        self._width = game._width//4
        self._height = game._width//4
        self._x = game._width//2
        self._y = game._height//2
        # sprite image
        self.rotation = 0
        self.base_image = pygame.Surface((self._width, self._height))
        self.base_image.fill(Color.green)
        self.setImage(self.base_image)
        self.rect = self.image.get_rect()
        self.moveCenterTo(self._x, self._y)
        return self

    def _redraw(self):
        self.dirty = 1 if self.dirty == 0 else 2

    def _update_image(self):
        scale = self.game._scale
        self.rect.w = self._width * scale
        self.rect.h = self._height * scale
        self.image = pygame.transform.scale(
                self.base_image,
                (self.rect.w, self.rect.h))
        if self.rotation != 0:
            self._update_rotation()
        else:
            self._update_position()
        self.mask = pygame.mask.from_surface(self.image)

    def _update_rotation(self):
        self._update_position()
        centerx = self.rect.centerx
        centery = self.rect.centery
        # rotate sprite around center, not top left
        # rotation only affects visuals
        # internal width, height, rotation are unaffected
        self.image = pygame.transform.rotate(self.image, self.rotation)
        rotated_rect = self.image.get_rect()
        self.rect.w = rotated_rect.w
        self.rect.h = rotated_rect.h
        self.rect.centerx = centerx
        self.rect.centery = centery

    def _update_position(self):
        scale = self.game._scale
        left_padding = self.game._padding[0]
        top_padding = self.game._padding[2]
        self.rect.x = (self._x + left_padding) * scale
        self.rect.y = (self._y + top_padding) * scale
        self._redraw()

    def move(self, x, y):
        self._x += x
        self._y += y
        self._update_position()
        return self

    def moveTo(self, x, y):
        self._x, self._y = x, y
        self._update_position()
        return self

    def moveCenterTo(self, x, y):
        self._x = x - self._width // 2
        self._y = y - self._height // 2
        self._update_position()
        return self

    @property
    def _cx(self):
        return self._x + self._width // 2

    @_cx.setter
    def _cx(self, x):
        self._x = x - self._width // 2
        self._update_position()

    @property
    def _cy(self):
        return self._y + self._height // 2

    @_cy.setter
    def _cy(self, y):
        self._y = y - self._height // 2
        self._update_position()

    def resize(self, w, h = None):
        if h == None:
            self.resize(w, self._height * w // self._width)
            return self
        self._width = w
        self._height = h
        self._update_image()
        return self

    def rotate(self, degrees):
        self.rotation += degrees
        self.rotateTo(self.rotation)
        return self

    def rotateTo(self, degrees):
        degrees %= 360
        if degrees < 0: degrees += 360
        self.rotation = degrees
        self._update_image()
        return self

    def setImage(self, image):
        self.base_image = image
        self.rect = image.get_rect()
        self.resize(self.rect.w, self.rect.h)
        return self

    def hide(self):
        self.visible = 0
        self._redraw()
        return self

    def show(self):
        self.visible = 1
        self._redraw()
        return self

    def inBounds(self):
        if self._y < self.game.top:
            return False
        elif self._y + self._height > self.game.bottom:
            return False
        elif self._x < self.game.left:
            return False
        elif self._x + self._width > self.game.right:
            return False
        return True

    def update(self):
        return

class TextSprite(GameSprite):
    def __init__(self, game):
        super().__init__(game)
        self.layer = 2
        self.format_str = "text_sprite: {}"
        self.fontsize = 10
        self.fonttype = FREESANS
        self.color = Color.white
        self.setFontType(self.fonttype)
        self.antialias = True
        self.setText("sample text")

    def setAntiAlias(self, antialias: bool):
        self.antialias = antialias
        return self

    def setFontSize(self, size):
        self.fontsize = size
        self.setFontType(self.fonttype)
        return self

    def setFontType(self, font):
        self.font = pygame.font.Font(font, self.fontsize)
        self.fonttype = font
        self._redraw()
        return self

    def _renderText(self):
        text = self.format_str.format(*self.text)
        text_render = self.font.render(text,
                                       self.antialias,
                                       self.color)
        self.setImage(text_render)
        self._update_position()
        self._redraw()

    @property
    def bold(self):
        return self.font.bold

    @bold.setter
    def bold(self, val):
        self.font.bold = val
        self._renderText()

    @property
    def italic(self):
        return self.font.italic

    @italic.setter
    def italic(self, val):
        self.font.italic = val
        self._renderText()

    @property
    def underline(self):
        return self.font.underline

    @underline.setter
    def underline(self, val):
        self.font.underline = val
        self._renderText()

    @property
    def strikerthrough(self):
        return self.font.strikerthrough

    @strikerthrough.setter
    def strikerthrough(self, val):
        self.font.strikerthrough = val
        self._renderText()

    def setFormatString(self, format_str):
        self.format_str = format_str
        self._renderText()
        return self

    def setColor(self, color):
        self.color = color
        self._renderText()
        return this

    def setText(self, *format_text):
        self.text = format_text
        self._renderText()
        return self

class Game:
    def __init__(self, w = None, h = None):
        self.name = "game"
        self.sprites = pygame.sprite.LayeredDirty()
        self._pause = False
        padding = (10, 10, 10, 10)
        self._window = Window(self)
        if w == None: w = WIDTH
        if h == None: h = HEIGHT
        self._init_screen(padding, w, h)

    def _init_screen(self, padding, w, h):
        self._padding = padding
        self.screen_ratio = w/h
        self._width = w - padding[0] - padding[1]
        self._height = h - padding[2] - padding[3]
        self._scale = 1
        self.base_background = pygame.Surface((w, h))
        self.base_background.fill(Color.green)
        game_space = pygame.Rect((padding[0], padding[1]),
                                 (self._width, self._height))
        pygame.draw.rect(self.base_background,
                         Color.black,
                         game_space)
        self.background = self.base_background
        self.refresh()

    @property
    def width(self):
        return self._scale*(self._width + self._padding[0] + self._padding[1])

    @property
    def height(self):
        return self._scale*(self._height + self._padding[1] + self._padding[2])

    def refresh(self):
        self._redraw()

    def start(self):
        self.refresh()
        self._reset()

    def _add_sprite(self, *sprites):
        self.sprites.add(sprites)

    def _resize(self, scale):
        self._scale = scale
        self.background = pygame.transform.scale(
            self.base_background, (self.width, self.height))
        for sprite in self.sprites:
            sprite._update_image()
        self.refresh()

    def _draw_sprites(self):
        self.sprites.clear(self.screen, self.background)
        self.sprites.draw(self.screen)
        pygame.display.update()

    def _redraw(self):
        scale = self._scale
        self.screen = pygame.Surface((self.width, self.height))
        self.screen.blit(self.background, (0, 0))
        for sprite in self.sprites:
            sprite._redraw()
        self._draw_sprites()

    def _handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.KEYUP):
            self._handle_key(event)

    def unpause(self):
        self._pause = False

    def pause(self):
        self._pause = True

    def _game_loop(self):
        self._update()
        self.sprites.update()
        self._draw_sprites()

    def _tick(self):
        if self._pause == False:
            self._game_loop()

    @property
    def left(self):
        return 0

    @property
    def right(self):
        return self._width

    @property
    def top(self):
        return 0

    @property
    def bottom(self):
        return self._height

    @property
    def fps(self):
        return self._window.fps

    @fps.setter
    def fps(self, fps):
        self._window.fps = fps

    # functions to override
    def _handle_key(self, event):
        return

    def _update(self):
        return

    def _reset(self):
        return

    def _save(self):
        return

    def _load(self):
        return

class Window:
    def __new__(cls, game = None):
        if not hasattr(cls, 'singleton'):
            cls.singleton = super().__new__(cls)
            cls.singleton.initialize()
        if game != None: cls.singleton.addGame(game)
        return cls.singleton

    def initialize(self):
        global WIDTH
        global HEIGHT
        self.name = "Nameless Window"
        self.vsync = 1
        self.games = set()
        self.focused_games = set()
        self.fps = 30
        padding = [10, 10, 10, 10]
        self._init_window(padding, WIDTH, HEIGHT)


    def _init_window(self, padding, w, h):
        self._width = WIDTH
        self._height = HEIGHT
        self._padding = padding
        self.screen_ratio = self._width / self._height
        self._scale = 1
        self.base_background = pygame.Surface((w, h))
        self.base_background.fill(Color.white)
        self._resize_window(WIDTH, HEIGHT)

    def _handle_events(self):
        for event in pygame.event.get():
            self._handle_event(event)
            for game in self.focused_games:
                game._handle_event(event)

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.VIDEORESIZE:
            self._resize_window(event.w, event.h)
            self._redraw()
        elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
            self._handle_key(event)

    def _handle_key(self, event):
        key = Key(event)
        if key == pygame.K_ESCAPE:
           self.quit()

    def _redraw(self):
        for game in self.games:
            game._redraw()

    def _render_games(self):
        for game in self.games:
            game._tick()
            self.window.blit(game.screen, game.window_position)
        pygame.display.update()

    def _resize_window(self, w, h):
        global WIDTH
        global HEIGHT
        if (WIDTH - w) != 0:
            WIDTH = w
            HEIGHT = (1.0/self.screen_ratio) * w
        else:
            HEIGHT = h
            WIDTH = h * self.screen_ratio
        WIDTH = round(WIDTH)
        HEIGHT = round(HEIGHT)
        self.window = pygame.display.set_mode(
                        (WIDTH, HEIGHT),
                        pygame.RESIZABLE, vsync = self.vsync)
        pygame.display.set_caption(self.name)
        self._scale = (float(WIDTH) /self._width)
        self.background = pygame.transform.scale(
                self.base_background,
                (WIDTH, HEIGHT))
        self.window.blit(self.background, (0, 0))
        for game in self.games:
            game._resize(self._scale)
            self._update_game_position(game)
        self.refresh()

    def _update_game_position(self, game):
        game.window_position = (game._window_position[0] * self._scale,
                                game._window_position[1] * self._scale)

    def refresh(self):
        self._render_games()

    def setName(name):
        self.name = name
        pygame.display.set_caption(self.name)

    def addGame(self, game: Game, position = (0, 0), focus = True):
        self.games.add(game)
        self.moveGameTo(game, *position)
        self.focusGame(game, focus)
        return self

    def removeGame(self, game):
        self.games.remove(game)

    def focusGame(self, game: Game, focus):
        if focus: self.focused_games.add(game)
        else: self.focused_games.remove(game)

    def moveGameTo(self, game, x, y):
        game._window_position = (x, y)
        self._update_game_position(game)

    def moveGame(self, game, dx, dy):
        game._window_position = (game.window_position + dx,
                                game.window_position + dy)
        self._update_game_position(game)

    def moveGameCenterTo(self, game, cx, cy):
        game._window_position = (cx - game._width//2,
                                cy - game._height//2)
        self._update_game_position(game)

    def start(self):
        for game in self.games:
            game.start()
        self.clock = pygame.time.Clock()
        self.stop = False
        while not self.stop:
            self._tick()

    def quit(self):
        self.stop = True

    def _tick(self):
        self._handle_events()
        self._render_games()
        last_tick = self.clock.tick(self.fps)

# PONG implementation
class Striker(GameSprite):
    def __init__(self, game):
        super().__init__(game)
        self.velocity = 0
        self.rot_velocity = 0

    def setup(self, color, wh, friction, speed, accel, rot_speed, rot_accel, power, grip, elasticity):
        self.speed = 15 * (speed/10.0)
        self.accel = 5 * (accel/10.0)
        self.rot_speed = 10 * (rot_speed/10.0)
        self.rot_accel = 2 * (rot_accel/10.0)
        self.color = color
        self.friction = 0.8 * (10.0/friction)
        self.elasticity = 1.0 - 0.6 / (elasticity/10.0 + 0.6)
        self.power = 8 * (power / 10.0)
        self.grip = 0.5 - 0.5/(2*grip/10.0 + 0.5)
        striker = pygame.Surface(wh, flags=pygame.SRCALPHA)
        striker.fill(self.color)
        self.setImage(striker)

    def _apply_friction(self):
        self.velocity *= self.friction
        self.rot_velocity *= self.friction
        if abs(self.velocity) < 1: self.velocity = 0
        if abs(self.rot_velocity) < 1: self.rot_velocity = 0

    def update(self):
        self.move(0, self.velocity * 60.0/self.game.fps)
        self._rotate()
        self._apply_friction()

    def _moveDown(self):
        self.velocity += self.accel
        if self.velocity >= self.speed:
            self.velocity = self.speed

    def _moveUp(self):
        self.velocity -= self.accel
        if self.velocity <= -self.speed:
            self.velocity = -self.speed

    def _rotateRight(self):
        self.rot_velocity -= self.rot_accel
        if abs(self.rot_velocity) >= self.rot_speed:
            self.rot_velocity = -self.rot_speed

    def _rotateLeft(self):
        self.rot_velocity += self.rot_accel
        if abs(self.rot_velocity) >= self.rot_speed:
            self.rot_velocity = self.rot_speed

    def _rotate(self):
        self.rotation += self.rot_velocity * 60.0/self.game.fps
        self.rotateTo(self.rotation)

    def _snapToEdge(self):
        if self._y > self.game._height // 2:
            self._y = self.game.bottom - self._height
        else:
            self._y = self.game.top
        self._update_position()

    def move(self, x, y):
        super().move(x, y)
        if not self.inBounds():
            self._snapToEdge()
            self.velocity = 0

class Ball(GameSprite):
    def __init__(self, game):
        super().__init__(game)
        self.spin = 0
        self.velocity = pygame.math.Vector2(1, 0)

    def setup(self, speed, color, r, mass):
        self.min_speed = 10 * (speed/10.0)
        self.speed = self.min_speed
        self.mass = (mass / 10.0)
        self.rolling_friction = 0.1 *\
                (speed/10.0) * (1 - 1.0 / (self.mass + 1))
        self._substeps = 10 # use substepping for greater simulation accuracy
        self.color = color
        self.r = r
        ball = pygame.Surface((2 * r, 2 * r))
        pygame.draw.circle(ball, self.color\
                , (r, r), r)
        self.setImage(ball)
        return self

    def _bounce(self, wall_normal):
        self.velocity.reflect_ip(wall_normal)

    def bounceOnCeiling(self):
        next_y = self._y + self.velocity.y
        next_x = self._x + self.velocity.x
        floor = self.game.bottom
        right = self.game.right
        if next_y <= 0:
            self._y = 0
            self._bounce(pygame.math.Vector2(0, -1))
        elif next_y + 2 * self.r >= floor:
            self._y = floor - 2 * self.r
            self._bounce(pygame.math.Vector2(0, 1))

        if next_x <= 0:
            self._x = 0
            self._bounce(pygame.math.Vector2(1, 0))
        elif next_x + 2 * self.r >= right:
            self._x = right - 2 * self.r
            self._bounce(pygame.math.Vector2(-1, 0))

    def scoreOnPlayers(self):
        goals = self.game.goals # dict(striker, goal_zone)
        for striker, zone in goals.items():
            if (self._x + self.r >= zone[0]
                and self._x + self.r <= zone[1]):
                self.game._scoreOnPlayer(striker)

    def bounceOnStrikers(self):
        strikers = self.game.goals.keys()
        for striker in strikers:
            if pygame.sprite.collide_mask(self, striker):
                self._bounceOnStriker(striker)

    def _unclipFromStriker(self, striker):
        backstep = -self.velocity
        backstep.normalize_ip()
        limit = 3 * self._substeps
        while pygame.sprite.collide_mask(self, striker):
            self.move(*(backstep).xy)
            self.move(0, striker.velocity)
            limit -= 1
            if limit <= 0:
                break

    def _normalizedStrikerImpactAngle(self, striker):
        rotation = striker.rotation
        # use the offset from the striker to calculate
        # on which face the impact occured
        offset_vector = pygame.math.Vector2(
                self._cx - striker._cx,
                self._cy - striker._cy)
        # rotate the offset vector to match striker
        offset_vector.rotate_ip(striker.rotation)
        # determine which face is hit
        if (offset_vector.y > -striker._height//2 and
            offset_vector.y < striker._height //2):
            if offset_vector.x < striker._width//2:
                striker_normal = pygame.math.Vector2(-1, 0)
            else: striker_normal = pygame.math.Vector2(1, 0)
        else:
            if (offset_vector.y <= -striker._height//2):
                striker_normal = pygame.math.Vector2(0, -1)
            else:
                striker_normal = pygame.math.Vector2(0, 1)
        # calculate the resulting normal
        striker_normal.rotate_ip(-rotation)
        return striker_normal

    def _rotateHitOnStriker(self, striker):
        final_vector = pygame.math.Vector2(0, 0)
        if abs(striker.rot_velocity) <= 1: return final_vector
        # first, test if the striker is rotating onto the ball
        offset_vector = pygame.math.Vector2(
                self._cx - striker._cx,
                self._cy - striker._cy)
        striker_normal = self._normalizedStrikerImpactAngle(striker)
        scale = self.game._scale
        hitting = None
        for i in range(self._substeps):
            future_striker_image = pygame.transform.rotate(striker.image,
                                            striker.rot_velocity/self._substeps)
            future_striker_mask = pygame.mask.from_surface(future_striker_image)
            mask_offset = pygame.math.Vector2(
               striker.rect.centerx - future_striker_image.get_width()/2,
               striker.rect.centery - future_striker_image.get_height()/2)
            mask_offset -= pygame.math.Vector2(self.rect.x, self.rect.y)
            hitting = self.mask.overlap(future_striker_mask, mask_offset)

            # debug drawing
            self.game.screen.blit(self.game.background, (0, 0))
            self.game.screen.blit(self.image, (400,400))
            self.game.screen.blit(future_striker_image, (400 + mask_offset.x,
                                                         400 + mask_offset.y))
            if hitting == None:
                continue
            else:
                print(self.mask.overlap_area(future_striker_mask, mask_offset))
                break
        if hitting == None:
            print("not rotate hit!")
            return final_vector
        else:
            print("rotate hit!")
        # then, determine the direction and angle of the hit
        striker_rot_hit_vector = striker_normal
        future_offset = offset_vector.rotate(striker.rot_velocity)
        rot_hit_speed = ((future_offset - offset_vector).magnitude()
                         * striker.elasticity / self.mass)
        if striker_rot_hit_vector.length() == 0:
            print("error rotate hit")
            return final_vector
        striker_rot_hit_vector.scale_to_length(rot_hit_speed)
        print(rot_hit_speed)
        print(striker_rot_hit_vector)
        if striker.rot_velocity > 0: striker.rot_velocity -= rot_hit_speed
        else: striker.rot_velocity += rot_hit_speed

        # debug drawing
        line = pygame.draw.line(self.game.screen, Color.green,
                                (400, 400),
                                (400 + striker_rot_hit_vector.x * 30,
                                 400 + striker_rot_hit_vector.y * 30))
        # final_vector += striker_rot_hit_vector
        return final_vector


    def _bounceOnStriker(self, striker):
        # first, move ball back until not clipping Striker
        self._unclipFromStriker(striker)
        final_vector = pygame.math.Vector2(0, 0)
        # then calculate information about the collision
        striker_normal = self._normalizedStrikerImpactAngle(striker)
        # reflect off the striker
        reflect_vector = self.velocity.copy().reflect(striker_normal)
        reflect_vector.scale_to_length(self.speed * striker.elasticity)
        # final_vector = reflect_vector
        # apply modifications based on the striker's attributes
        # modification 1: striker power
        striker_hit_vector = striker_normal.copy()
        striker_hit_vector.scale_to_length(striker.power/self.mass)
        # final_vector += striker_hit_vector
        # modification 2: striker grip
        grip_vector = pygame.math.Vector2(0,
                striker.velocity * striker.grip / self.mass)
        grip_vector = grip_vector.rotate(-striker.rotation)
        self.spin += grip_vector.y
        striker.velocity -= grip_vector.y * self.mass
        # final_vector += grip_vector
        # modification 3: striker rotation
        final_vector += self._rotateHitOnStriker(striker)
        # apply final calculated vector
        if final_vector.magnitude() == 0:
            if striker_normal.magnitude() == 0:
                self.velocity = offset_vector
            else:
                # self.velocity = striker_hit_vector
                self.velocity *= -1
        else:
            self.velocity = final_vector
        self.speed = self.velocity.magnitude()

    def roll(self):
        self.speed -= self.rolling_friction/self._substeps
        if self.speed < self.min_speed:
            self.speed = self.min_speed
        fps_ratio = 60.0/self.game.fps
        self.velocity.scale_to_length(self.speed * fps_ratio)
        self.move(float(self.velocity.x/self._substeps),
                  float(self.velocity.y/self._substeps))
        #TODO spin logic

    def update(self):
        for i in range(self._substeps):
            self.roll()
            self.bounceOnCeiling()
            self.bounceOnStrikers()
        # self.scoreOnPlayers()

class PONGGAME(Game):
    def __init__(self):
        super().__init__()
        self.name = "pong"
        self.fps = 60
        self._initialize_sprites()
        self._initialize_controls()

    def _initialize_sprites(self):
        striker_size = (100, 30)
        striker_speed = 10
        striker_accel = 10
        striker_rot_speed = 10
        striker_rot_accel = 10
        striker_color = Color.white
        striker_friction = 10
        striker_power = 10
        striker_grip = 10
        striker_elasticity = 10
        striker_parameters = (
                striker_color,
                striker_size,
                striker_friction,
                striker_speed,
                striker_accel,
                striker_rot_speed,
                striker_rot_accel,
                striker_power,
                striker_grip,
                striker_elasticity)
        ball_speed = 10
        ball_color = Color.white
        ball_size = 10
        ball_mass = 10
        ball_parameters = (ball_speed,
                           ball_color,
                           ball_size,
                           ball_mass)
        self.striker_left = Striker(self)
        self.striker_right = Striker(self)
        self.striker_left.setup(*striker_parameters)
        self.striker_right.setup(*striker_parameters)
        self.ball = Ball(self).setup(*ball_parameters)
        self._add_sprite(self.striker_left)
        self._add_sprite(self.striker_right)
        self._add_sprite(self.ball)
        goal_length = 10
        self.goals = {self.striker_left: None,
                      self.striker_right: None}
        self.goals[self.striker_left] = \
            (-self._width, goal_length)
        self.goals[self.striker_right] = \
            (self._width - goal_length, 2*self._width)
        score_text_size = 100
        self.s1_score_text = TextSprite(self).setFormatString("{}")
        self.s2_score_text = TextSprite(self).setFormatString("{}")
        self.s1_score_text.setFontSize(score_text_size)
        self.s2_score_text.setFontSize(score_text_size)
        self._add_sprite(self.s1_score_text)
        self._add_sprite(self.s2_score_text)
        self.s1_score = 0
        self.s2_score = 0
        self._update_score()
        self.menu_title_text = TextSprite(self)
        self._add_sprite(self.menu_title_text)
        self.menu_title_text.hide()
        self.menu_title_text.setFontSize(100)
        self.menu_title_text.bold = True

    def _update_score(self):
        self.s1_score_text.setText(self.s1_score)
        self.s2_score_text.setText(self.s2_score)

    def _initialize_controls(self):
        self.p1_up = False
        self.p1_dn = False
        self.p1_lt = False
        self.p1_rt = False
        self.p2_up = False
        self.p2_dn = False
        self.p2_lt = False
        self.p2_rt = False

    def _reset(self):
        middle = self._height // 2
        top_middle = self._height // 4
        center = self._width // 2
        left = self._width // 16
        right = self._width - left
        center_left = self._width // 4
        center_right = self._width - center_left
        self.striker_left.moveCenterTo(left, middle)
        self.striker_right.moveCenterTo(right, middle)
        print(right, middle)
        for striker in (self.striker_right, self.striker_left):
            striker.rotateTo(0)
            striker.rot_velocity = 0
            striker.velocity = 0
        self.ball.moveCenterTo(center, middle)
        self.ball.velocity = pygame.math.Vector2(1, 0)
        self.ball.speed = self.ball.min_speed
        self.s1_score_text.moveCenterTo(center_left,
                                        top_middle)
        self.s2_score_text.moveCenterTo(center_right,
                                        top_middle)
        self.menu_title_text.moveCenterTo(center, middle)
        self._update_score()

    def _restart(self):
        self.s1_score = 0
        self.s2_score = 0
        self._reset()

    def _handle_key(self, event):
        key = Key(event)
        if key in (pygame.K_UP,):
            self.p1_up = key.down
        elif event.key in (pygame.K_DOWN,):
            self.p1_dn = key.down
        elif event.key in (pygame.K_RIGHT,):
            self.p1_rt = key.down
        elif event.key in (pygame.K_LEFT,):
            self.p1_lt = key.down
        elif event.key in (pygame.K_w,):
            self.p2_up = key.down
        elif event.key in (pygame.K_s,):
            self.p2_dn = key.down
        elif event.key in (pygame.K_a,):
            self.p2_lt = key.down
        elif event.key in (pygame.K_d,):
            self.p2_rt = key.down
        elif key in (pygame.K_p,) and key.down:
            self._pause = not self._pause
            self._handle_pause()
        elif key in (pygame.K_r,) and key.down:
            self._restart()

    def _update(self):
        if self.p1_up:
            self.striker_right._moveUp()
        if self.p1_dn:
            self.striker_right._moveDown()
        if self.p1_rt:
            self.striker_right._rotateRight()
        if self.p1_lt:
            self.striker_right._rotateLeft()
        if self.p2_up:
            self.striker_left._moveUp()
        if self.p2_dn:
            self.striker_left._moveDown()
        if self.p2_rt:
            self.striker_left._rotateRight()
        if self.p2_lt:
            self.striker_left._rotateLeft()

    def _scoreOnPlayer(self, player):
        if player == self.striker_left:
            self.s2_score += 1
        elif player == self.striker_right:
            self.s1_score += 1
        self._update_score()
        self._reset()

    def _handle_pause(self):
        if self._pause:
            middle = self._height // 2
            center = self._width // 2
            self.menu_title_text.setText("PAUSED")
            self.menu_title_text.setFormatString("{}")
            self.menu_title_text.moveCenterTo(center, middle)
            self.menu_title_text.show()
            self._draw_sprites()
        else:
            self.menu_title_text.hide()

# MAIN
def main():
    pygame.init()
    window = Window()
    window.addGame(PONGGAME())
    window.start()
    pygame.quit()

if __name__ == "__main__":
    print("running pypong!")
    main()
