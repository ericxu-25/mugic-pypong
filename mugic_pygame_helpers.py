import time
import pygame
import math
import random
import colorsys
# Resources used as reference:
# * geeksforgeeks.org/create-a-pong-game-in-python-pygame/
# * https://www.pygame.org/docs/
# * https://stackoverflow.com/questions/11603222/allowing-resizing-window-pygame

# TODO list
# * debug windows (1: game, 2: controller, 3: more controller)
# * mugic controller module (calibration + implementation)
# * springy striker (striker x velocity)
# * port to godot

# GLOBALS
pygame.font.init()
FREESANS = 'freesansbold.ttf'

class Color:
    black = (0,0,0)
    white = (255, 255, 255)
    green = (0, 255, 0)
    red = (255, 0, 0)
    blue = (0, 0, 255)
    cyan = (0, 255, 255)
    magenta = (255, 0, 255)
    yellow = (255, 255, 0)
    orange = (255, 165, 0)

    _random_hue = random.random()

    @classmethod
    def random(cls):
        cls._random_hue = ((cls._random_hue * 360 + random.randint(50, 100))
                           % 360 / 360.0)
        r, g, b = colorsys.hsv_to_rgb(cls._random_hue, 1, 0.9)
        return (r * 255, g * 255, b * 255)

WIDTH, HEIGHT = 1300, 600

# HELPERS

# class to work with pygame keyevents
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

# pygame sprite subclass with dynamic scaling/rotation
class Sprite(pygame.sprite.DirtySprite):
    # class variables
    sprite_id = 0
    def __init__(self, screen=None):
        super().__init__()
        # screen the sprite will be adjusted to
        if screen is None:
            screen = Screen()
        self.screen = screen
        # sprite properties
        self.dirty = 1
        self.visible = 1
        self.blendmode = 0
        self.source_rect = None
        self.layer = 0
        self._width = random.randint(50, 200)
        self._height = random.randint(50, 200)
        self._x = random.randint(50, 100)
        self._y = random.randint(50, 100)
        # sprite image
        self._scale = 1
        self.rotation = 0
        self.base_image = pygame.Surface((self._width, self._height))
        self.base_image.fill(Color.green)
        self._colorkey = None
        self.setImage(self.base_image)
        self.rect = self.image.get_rect()
        self.moveCenterTo(self._x, self._y)
        # debug output
        Sprite.sprite_id += 1
        self.name = f"Sprite {self.sprite_id}"
        self._debug = False
        self._debug_screen = None
        return self

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, val):
        self._scale = val

    @property
    def _rect(self):
        return pygame.Rect(self._x, self._y, self._width, self._height)

    @_rect.setter
    def _rect(self, rect):
        self._x = rect.x
        self._y = rect.y
        self._width = rect.w
        self._height = rect.h
        self._update_image()

    def _redraw(self):
        self.dirty = 1 if self.dirty == 0 else 2

    def _update_image(self):
        scale = self.scale
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
        scale = self.scale
        left_padding = self.screen._padding[0]
        top_padding = self.screen._padding[2]
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

    @property
    def colorkey(self):
        return self._colorkey

    @colorkey.setter
    def colorkey(self, color):
        self._colorkey = color
        self.setImage(self.base_image)

    @property
    def scale(self):
        return self.screen._scale

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
        image.set_colorkey(self._colorkey)
        self.rect = image.get_rect()
        self.resize(self.rect.w, self.rect.h)
        return self

    def inBounds(self):
        if self._y < self.screen.top:
            return False
        elif self._y + self._height > self.screen.bottom:
            return False
        elif self._x < self.screen.left:
            return False
        elif self._x + self._width > self.screen.right:
            return False
        return True

    def hide(self):
        self.visible = 0
        self._redraw()
        return self

    def show(self):
        self.visible = 1
        self._redraw()
        return self

    def toggleVisibility(self):
        if self.visible: self.hide()
        else: self.show()

    def debugPrint(self, *args, **kwargs):
        if self._debug:
            print("["+self.name+"]", *args, **kwargs)

    def debugFunction(self, func, *args, **kwargs):
        if not self._debug:
            return None
        return func(*args, **kwargs)

    def debugDraw(self, func, *args, **kwargs):
        if not self._debug and self._debug_screen == None:
            return None
        func(self._debug_screen, *args, **kwargs)

    def debugDrawRefresh(self):
        if not self._debug and self._debug_screen == None:
            return None
        self._debug_screen.refresh()



class GameSprite(Sprite):
    def __init__(self, game=None):
        super().__init__(game)
        self.name = f"GameSprite {self.sprite_id}"

    @property
    def game(self): return self.screen

    @game.setter
    def game(self, game): self.screen = game

    # put Sprite logic in here
    def _reset(self):
        return

    def update(self):
        return

# sprite used to display formatted text
class TextSprite(Sprite):
    def __init__(self, screen=None):
        super().__init__(screen)
        self.name = f"TextSprite {TextSprite.sprite_id}"
        self.layer = 2
        self._format_str = "text_sprite: {}"
        self._fontsize = 10
        self._spacing = 4
        self._fonttype = FREESANS
        self._color = Color.white
        self._backcolor = None
        self.setFontType(self._fonttype)
        self._antialias = True
        self.setText("sample text")

    def _line_renders(self):
        spacing = self._fontsize + self._spacing
        for i, line in enumerate(self.text.split('\n')):
            line_render = self.font.render(
                    line,
                    self._antialias,
                    self._color,
                    self._colorkey)
            line_rect = line_render.get_rect()
            line_rect.topleft = (0, spacing * i)
            yield line_render, line_rect

    def _renderText(self):
        text_render_rect = pygame.Rect(0,0,0,0)
        lines = list()
        for line_render, line_rect in self._line_renders():
            text_render_rect.union_ip(line_rect)
            lines.append((line_render, line_rect))
        text_render = pygame.Surface(text_render_rect.size)
        if self._antialias or self._colorkey is None:
            text_render = text_render.convert_alpha()
            text_render.fill((0, 0, 0, 0))
        if self._backcolor is not None:
            text_render.fill(self._backcolor)
        for line_render, line_rect in lines:
            text_render.blit(line_render, line_rect)
        self.setImage(text_render)
        self._update_position()
        self._redraw()

    def setAntialias(self, antialias: bool):
        self._antialias = antialias
        self._renderText()
        return self

    def setFontSize(self, size):
        self._fontsize = size
        self.setFontType(self._fonttype)
        return self

    def setFontType(self, font):
        self.font = pygame.font.Font(font, self._fontsize)
        self._fonttype = font
        self._redraw()
        if hasattr(self, "text"):
            self._renderText()
        return self

    def setFormatString(self, format_str):
        self._format_str = format_str
        self._renderText()
        return self

    def setColor(self, color):
        self._color = color
        self._renderText()
        return self

    def setBackColor(self, color):
        self._backcolor = color
        self._renderText()
        return self

    def setText(self, *args, **kwargs):
        self._text = (args, kwargs)
        self._renderText()
        return self

    @property
    def antialias(self, size):
        return self._antialias

    @antialias.setter
    def antialias(self, on):
        self.setAntialias(bool(on))

    @property
    def fontsize(self, size):
        return self._fontsize

    @fontsize.setter
    def fontsize(self, size):
        self.setFontSize(size)

    @property
    def fonttype(self, font):
        return self._fonttype

    @fonttype.setter
    def fonttype(self, font):
        self.setFontType(font)

    @property
    def format(self):
        return self._format_str

    @format.setter
    def format(self, format_str):
        self.setFormatString(format_str)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self.setColor(color)

    @property
    def backcolor(self):
        return self._color

    @backcolor.setter
    def backcolor(self, backcolor):
        self.setBackColor(backcolor)


    @property
    def text(self):
        try:
            text = self._format_str.format(
                    *(self._text[0]), **(self._text[1]))
        except (ValueError, IndexError) as e:
            text = f"incompatible format {self._format_str} and {self._text}"
        return text

    @text.setter
    def text(self, *args, **kwargs):
        self.setText(*args, **kwargs)

    @property
    def spacing(self):
        return self._spacing

    @spacing.setter
    def spacing(self, amount):
        self._spacing = amount
        self._renderText()


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
    def strikethrough(self):
        return self.font.strikerthrough

    @strikethrough.setter
    def strikethrough(self, val):
        self.font.strikerthrough = val
        self._renderText()


# dynamic resizable surface with sprites and event handling
class Screen:
    def __init__(self, w = None, h = None, padding = None):
        self.name = "screen"
        self.sprites = pygame.sprite.LayeredDirty()
        if w == None: w = 400
        if h == None: h = 300
        self._pause = False
        self._position = (0, 0)
        if padding == None: padding = (0, 0, 0, 0)
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
        self._screen = pygame.Surface((self.width, self.height))
        self._redraw()

    @property
    def screen(self):
        return self._screen

    @screen.setter
    def screen(self, new_screen):
        self.setScreen(new_screen)

    @property
    def scale(self):
        return self._scale

    # setScreen - does not update the screen ratio
    def setScreen(self, new_screen):
        self._screen = new_screen
        new_size = ((self._screen.get_width() / self._scale),
                    (self._screen.get_height() / self._scale))
        self.base_background = pygame.transform.smoothscale(
                self.base_background, new_size)
        self._redraw()
        return self

    @property
    def base_width(self):
        return self._width + self._padding[0] + self._padding[1]

    @property
    def width(self):
        return self._scale*(self.base_width)

    @property
    def base_height(self):
        return self._height + self._padding[2] + self._padding[3]

    @property
    def height(self):
        return self._scale*(self.base_height)

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
    def center(self):
        return (self._width/2, self._height/2)

    @property
    def centerx(self):
        return self._width/2

    @property
    def centery(self):
        return self._height/2

    @property
    def fps(self):
        return self._window.fps

    @property
    def position(self):
        return (self._position[0] * self._scale,
                self._position[1] * self._scale)

    @property
    def base_rect(self):
        return pygame.Rect(self._position,
                           (self.base_width, self.base_height))

    @property
    def rect(self):
        return pygame.Rect(self.position, (self.width, self.height))

    @fps.setter
    def fps(self, fps):
        self._window.fps = fps

    def __str__(self):
        return f"{self.name}: {self.base_rect}"

    def _redraw(self):
        self._screen.blit(self.background, (0, 0))
        for sprite in self.sprites:
            sprite._redraw()
        self._draw_sprites()

    def _add_sprite(self, *sprites):
        for sprite in sprites: sprite.screen = self
        self.sprites.add(*sprites)

    def _remove_sprite(self, *sprites):
        self.sprites.remove(*sprites)

    def addSprite(self, *sprites):
        self._add_sprite(*sprites)

    def removeSprite(self, *sprites):
        self._remove_sprite(*sprites)

    def _resize(self, scale):
        self._scale = scale
        self.background = pygame.transform.scale(
                self.base_background, (self.width, self.height))
        for sprite in self.sprites:
            sprite._update_image()
        self.refresh()

    def _draw_sprites(self):
        self.sprites.draw(self._screen, bgsurf=self.background)

    def _handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.KEYUP):
            self._handle_key(event)

    def refresh(self):
        self._redraw()

    def resize(self, w, h, padding = None):
        if padding == None:
            padding = self._padding
        scale = self._scale
        self._init_screen(padding, w, h)
        self._resize(scale)

    # functions to override
    def _handle_key(self, event):
        return

# Screen which works with the main Window
class WindowScreen(Screen):
    def __init__(self, w = None, h = None, padding = None):
        if w == None: w = self._window._width
        if h == None: h = self._window._height
        super().__init__(w, h, padding)
        self.name = "window screen"
        self._window = Window()

    def _render(self):
        self._draw_sprites()
        # if screen is not a subsurface, draw directly onto the window
        if self._screen.get_parent() is None:
            self._window.window.blit(self._screen, self.position)

# Screen with interface to display many things in tabs
class DisplayScreen(WindowScreen):
    def __init__(self, w = None, h = None, padding = None):
        self.tabs = list()
        super().__init__(w, h, padding)
        self.base_background.fill(Color.red)

    # returns the next available tab position (left to right)
    def _get_next_tab_position(self, tab_rect):
        if len(self.tabs) == 0: return (0, 0)
        self.tabs = sorted(self.tabs, key=lambda x: x._position)
        last_tab = self.tabs[-1]
        tab_rect.topleft = last_tab.base_rect.topleft
        tab_rect.move_ip(last_tab.base_width, 0)
        if not self.base_rect.contains(tab_rect):
            tab_rect.x = 0
            tab_rect.y += last_tab.base_height
        if not self.base_rect.contains(tab_rect):
            print("addTab: Error fitting next tab!")
        return tab_rect.topleft

    def addTab(self, w, h = None, padding = (5, 5, 5, 5), position = None):
        if h == None: h = w
        new_tab = Screen(w, h, padding)
        if position == None:
            position = self._get_next_tab_position(new_tab.base_rect)
        new_tab._position = position
        new_tab.base_background.fill(Color.random())
        self.tabs.append(new_tab)
        tab_num = len(self.tabs) - 1
        new_tab.name = f"Tab {tab_num}"
        self._resize_tabs()
        return tab_num

    def totalTabs(self):
        return len(self.tabs)

    def splitTabs(self, rows, columns=1):
        tab_width = self._width/columns
        tab_height = self._height/rows
        for row in range(rows):
            for col in range(columns):
                self.addTab(tab_width, tab_height)


    def getTab(self, tab_num) -> pygame.Surface:
        if len(self.tabs) == 0: return None
        if tab_num <= 0: return None
        if len(self.tabs) <= tab_num: return None
        return self.tabs[tab_num]

    def _render(self):
        for tab in self.tabs:
            tab._draw_sprites()
            if tab.screen.get_parent == None:
                self.screen.blit(tab.screen, tab.position)
        super()._render()

    def _resize_tabs(self):
        for tab in self.tabs:
            tab._resize(self._scale)

    def _resize(self, scale):
        super()._resize(scale)
        self._resize_tabs()

    def _redraw(self):
        super()._redraw()
        for tab in self.tabs:
            tab._redraw()

    @property
    def screen(self):
        return self._screen

    @screen.setter
    def screen(self, new_screen):
        self.setScreen(new_screen)
        self._update_tab_subsurfaces()
        self._redraw()

    def _update_tab_subsurfaces(self):
        for tab in self.tabs:
            try:
                tab.screen = self.screen.subsurface(tab.rect)
            except ValueError as e:
                print("ValueError:", e)
                print("\twhile attempting to update tab:", tab)
                tab.screen = pygame.Surface((tab.width, tab.height))

    def writeNewText(self, text, offset=(0, 0), tab = None):
        if type(tab) is int: tab = self.getTab(tab)
        if tab == None: tab = self
        # automatically create a TextSprite if text is string
        if type(text) is str:
            text_sprite = TextSprite(self)
            text_sprite.setFormatString("{}").setText(text)
            text_sprite.moveTo(tab.centerx, tab.centery)
            text = text_sprite
        if isinstance(text, TextSprite):
            tab._add_sprite(text)
        else: return None
        return text

# Screen which includes basic game logic
class Game(WindowScreen):
    def __init__(self, w = None, h = None, padding = None):
        super().__init__(w, h, padding)
        self.name = "game"

    # functions to override
    def _update(self):
        # game logic would go here
        return

    def _reset(self):
        # set to starting state
        return

    def _save(self):
        return

    def _load(self):
        return

    def _start(self):
        self.refresh()
        self._reset()

    def unpause(self):
        self._pause = False

    def pause(self):
        self._pause = True

    def start(self):
        self._window.start()

    def _game_loop(self):
        self._update()
        self.sprites.update()

    def _tick(self):
        if self._pause == False:
            self._game_loop()

# Screen manager
class Window:
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'singleton'):
            cls.singleton = super().__new__(cls, *args, **kwargs)
            cls.singleton.initialize()
        return cls.singleton

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name
        pygame.display.set_caption(self._name)

    def initialize(self):
        global WIDTH
        global HEIGHT
        self.name = "Nameless Window"
        self.vsync = 1
        self.games = set()
        self.screens = set()
        self.focused_screens= set()
        self.fps = 30
        self._init_window(WIDTH, HEIGHT)

    def _init_window(self, w, h):
        self._width = w
        self._height = h
        self.screen_ratio = self._width / self._height
        self._scale = 1
        self.base_background = pygame.Surface((w, h))
        self.base_background.fill(Color.white)
        self._resize_window(w, h)

    def _handle_events(self):
        for event in pygame.event.get():
            self._handle_event(event)
            for screen in self.focused_screens:
                screen._handle_event(event)

    def _handle_event(self, event):
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.VIDEORESIZE:
            self._resize_window(event.w, event.h)
        elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
            self._handle_key(event)

    def _handle_key(self, event):
        key = Key(event)
        if key == pygame.K_ESCAPE:
            self.quit()

    def _redraw(self):
        for screen in self.screens:
            screen._redraw()

    def _update_games(self):
        for game in self.games:
            game._tick()

    def _render_screens(self):
        for screen in self.screens:
            screen._render()
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
        for screen in self.screens:
            screen._resize(self._scale)
            self._update_screen_subsurface(screen)
        self.refresh()

    def _update_screen_subsurface(self, screen):
        try:
            screen.screen = self.window.subsurface(screen.rect)
        except ValueError as e:
            print("ValueError:", e)
            print("\twhile attempting to update screen:", screen.name)
            screen.screen = pygame.Surface((screen.width, screen.height))

    def rescale(self, w, h):
        scale = self._scale
        self._init_window(w, h)
        self._resize_window(w * scale, h * scale)

    def refresh(self):
        for screen in self.screens:
            screen.refresh()
        self._render_screens()

    def setName(name):
        self.name = name
        pygame.display.set_caption(self.name)

    def addGame(self, game: Game, position = (0, 0), focus = True):
        self.games.add(game)
        self.addScreen(game, position, focus)

    def addScreen(self, screen, position = (0, 0), focus = True):
        self.screens.add(screen)
        self.moveScreenTo(screen, *position)
        self.focus(screen, focus)
        return self

    def removeScreen(self, screen):
        self.screens.remove(screen)
        self.focused_screens.remove(screen)
        screen._position = (0, 0)
        return self

    def removeGame(self, game):
        self.games.remove(game)
        self.removeScreen(game)

    def focus(self, screen, focus):
        if focus: self.focused_screens.add(screen)
        else: self.focused_screens.remove(screen)

    def moveScreenTo(self, screen, x, y):
        screen._position = (x, y)
        self._update_screen_subsurface(screen)

    def moveScreen(self, screen, dx, dy):
        screen._position = (screen.position + dx,
                            screen.position + dy)
        self._update_screen_subsurface(screen)

    def moveScreenCenterTo(self, screen, cx, cy):
        screen._position = (cx - screen._width//2,
                            cy - screen._height//2)
        self._update_screen_subsurface(screen)

    def start(self):
        for game in self.games:
            game._start()
        self.clock = pygame.time.Clock()
        self.stop = False
        while not self.stop:
            self._tick()

    def quit(self):
        self.stop = True

    def _tick(self):
        self._handle_events()
        self._update_games()
        self._render_screens()
        last_tick = self.clock.tick(self.fps)


