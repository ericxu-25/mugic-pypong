"""mugical_pong.py - Mugical Pong two player game"""
from pygame_helpers import *
from mugic_display import *
from mugic import *

# Basic Controls (keyboard)
# - up, left, down, right, rotleft, rotright
# p1 = wasdqe OR zx
# p2 = arrows<> OR ijkluo
# Basic Controls (Mugic)
# - point towards ceiling/floor to control up/down
# - twist right/left to change rotation
# - tilt fully down/up to continue to rotate
# - shake the Mugic launch striker forward
# - thrust Mugic forward (in pointing direction)

# TODO - fps independence


# PONG implementation
class Striker(GameSprite):
    def __init__(self, game=None):
        super().__init__(game)
        self.velocity = 0
        self.rot_velocity = 0
        self._CPU_RANDOM = random.randint(1, 30)
        self._controller = "Keyboard"
        self.impact_velocity = 0
        self._impact_accel = 0
        self._spring_x = None
        self._substeps = 10 # use substepping for greater simulation accuracy

    def setup(self, color, wh, friction, speed, accel, rot_speed, rot_accel, power, grip, elasticity, springiness):
        self.speed = 15 * (speed/10.0)
        self.accel = 5 * (accel/10.0)
        self.rot_speed = 15 * (rot_speed/10.0)
        self.rot_accel = 1.5 * (rot_accel/10.0)
        self.color = color
        self.friction = 0.8 * (10.0/(10 + friction/10))
        self.elasticity = 1.0 - 0.6 / (elasticity/10.0 + 0.6)
        self.springiness = 1.0 - 1.0 / (springiness/10.0 + 1.0)
        self.power = 8 * (power / 10.0)
        self.grip = (1.0 - 1.0/(grip/10.0 + 1))
        striker = pygame.Surface(wh, flags=pygame.SRCALPHA)
        striker.fill(self.color)
        self.setImage(striker)

    def _apply_friction(self):
        self.velocity *= self.friction
        self.rot_velocity *= 1 - ((1 - self.friction) / 2)
        self.impact_velocity *= 1 - ((1 - self.friction) / 2)
        if abs(self.velocity) < 1: self.velocity = 0
        if abs(self.rot_velocity) < 0.5: self.rot_velocity = 0

    def _apply_impact_spring(self):
        # useful ref: https://gafferongames.com/post/spring_physics/
        if self._spring_x is None: return
        if abs(self.impact_velocity) < 0.1: self.impact_velocity = 0
        # use Hooke's law to simulate a spring
        distance = self._spring_x - self.centerx
        if abs(distance) < 1:
            self._impact_accel = 0
        else:
            spring_force = abs((distance) * self.springiness) / 4
            # apply dampening
            spring_force -= abs(self.impact_velocity) * (1-self.springiness)
            spring_force = max(0, spring_force)
            self._impact_accel = spring_force * sign(distance)
        # apply the spring changes
        self.impact_velocity += self._impact_accel / self._substeps

    def update(self):
        for _ in range(self._substeps):
            self.move(0, self.velocity / self._substeps)
            self._apply_impact_spring()
            self.move(self.impact_velocity / self._substeps, 0)
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

    def _moveRight(self):
        self.impact_velocity += self.accel

    def _moveLeft(self):
        self.impact_velocity -= self.accel

    def _rotateRight(self):
        self.rot_velocity -= self.rot_accel
        if abs(self.rot_velocity) >= self.rot_speed:
            self.rot_velocity = -self.rot_speed

    def _rotateLeft(self):
        self.rot_velocity += self.rot_accel
        if abs(self.rot_velocity) >= self.rot_speed:
            self.rot_velocity = self.rot_speed

    def _rotate(self):
        self.rotation += self.rot_velocity
        self.rotateTo(self.rotation)

    def _moveTowardsPoint(self, targetY):
        ret_val = True
        if(self.centery > targetY + self.speed + self.accel):
            self._moveUp()
            ret_val = False
        elif(self.centery < targetY - self.speed - self.accel):
            self._moveDown()
            ret_val = False
        elif abs(self.centery - targetY) < self.accel:
            self.centery = targetY
        return ret_val

    def _moveTowardsNormal(self):
        return self._moveTowardsPoint(self.game.height//2)

    def _rotateTowardsAngle(self, angle):
        # 180 b/c symmetrical
        offset = (angle - self.rotation + 360) % 180
        threshold = self.rot_speed * 1.2
        if (180 - offset) < threshold or offset < threshold:
            self.rotateTo(angle)
            self.rot_velocity = 0
            return True
        elif offset > 90:
            self._rotateRight()
            return False
        else:
            self._rotateLeft()
            return False

    def _rotateTowardsNormal(self):
        return self._rotateTowardsAngle(0)

    def _rotateTowardsBall(self):
        ball = self.game.ball
        db = abs(self._x - ball._x)
        if db > self._width + self._CPU_RANDOM * 6:
            return
        if db < self._width + self._CPU_RANDOM * 1.3:
            return
        if ball.centery < self.centery:
            if self.x > ball.x:
                self._rotateLeft()
            else: self._rotateRight()
        else:
            if self.x > ball.x:
                self._rotateRight()
            else:
                self._rotateLeft()

    def _moveTowardsBall(self):
        return self._moveTowardsPoint(self.game.ball.centery)

    def _launchTowardsBall(self):
        ball = self.game.ball
        db = abs(self._x - ball._x)
        if db > self.height - self._CPU_RANDOM//2:
            return
        if self._x - ball._x < 0:
            self._moveRight()
        else:
            self._moveLeft()


    def _CPUMovement(self):
        ball = self.game.ball
        db = abs(self._x - ball._x)
        if db > self.game._width//2:
            self._rotateTowardsNormal()
            if db > self.game._width //2:
                self._CPU_RANDOM = random.randint(1, 30)
            elif self._CPU_RANDOM % 4 == 0:
                self._moveTowardsNormal()
            return
        self._moveTowardsPoint(ball.centery + (self._CPU_RANDOM - 15) // 3)
        if self._CPU_RANDOM % 4 != 0:
            self._rotateTowardsBall()
        if self._CPU_RANDOM % 3 == 0:
            self._launchTowardsBall()

    def _snapToEdge(self):
        if self.top < self.game.top:
            self.top = self.game.top
        elif self.bottom > self.game.bottom:
            self.bottom = self.game.bottom
        if self.left < self.game.left:
            self.left = self.game.left
        elif self.right > self.game.right:
            self.right = self.game.right
        self._update_position()

    def displayStrikerBounce(self, ball, bounce_data):
        self.debugDraw(self._draw_striker_bounce, ball, **bounce_data)

    def _init_draw_striker_bounce(self):
        display = self._debug_screen
        tab = display.getTab(1)
        if tab == None:
            print("error getting tab to draw striker information")
            return
        # initialize the text sprites if they haven't been yet
        if not hasattr(self, '_draw_striker_bounce_text'):
            text_size = 20
            self._draw_striker_bounce_text = list()
            text = self._draw_striker_bounce_text
            for i in range(4):
                new_text = display.writeNewText(
                    "...", tab=tab)
                text.append(new_text)
                new_text.setFontSize(text_size)
                new_text.moveTo(10, 10 + (text_size + 3) * i)
            text[0].setText("BOUNCE INFORMATION")
            text[1].setFormatString("ball speed: {:.2f}")
            text[1].setText(0)
            text[2].setFormatString("ball spin: {:.2f}")
            text[2].setText(0)
            text[3].setFormatString("Controller: {}")
            text[3].setText("Keyboard")
        else:
            text = self._draw_striker_bounce_text
            text[1].setText(0)
            text[1].setColor(Color.white)

    def _reset(self):
        self.debugFunction(self._init_draw_striker_bounce)
        self.rotateTo(0)
        self.rot_velocity = 0
        self.velocity = 0
        self.impact_velocity = 0
        if self._spring_x is not None:
            self.centerx = self._spring_x
        self._CPU_RANDOM = random.randint(1, 30)
        self.debugDraw(self._draw_striker_bounce, None)

    def _draw_striker_bounce(self, display, ball, **bounce_data):
        # select the middle display tab
        tab = display.getTab(1)
        tab.refresh()
        text = self._draw_striker_bounce_text
        # resize striker image to fit
        fit_scale = tab._height / self._height / 2
        # draw the striker onto the tab
        center = (tab.centerx * self.scale,  (tab.centery + text[1].rect.y) * self.scale)
        center_position = (center[0] - self.rect.width//2 * fit_scale,
                           center[1] - self.rect.height//2 * fit_scale)
        # using smoothscale_by instead (slower, but cleaner than scale_by)
        tab.screen.blit(
                pygame.transform.smoothscale_by(self.image, fit_scale),
                center_position, special_flags=self.blendmode)
        if ball == None: return # stop if no data
        # draw the ball onto the tab
        scale = self.game._scale
        ball_offset = bounce_data['offset'] * scale * fit_scale
        ball_position = ball_offset + center - \
                (ball.rect.width//2 * fit_scale,
                 ball.rect.height//2 * fit_scale)
        tab.screen.blit(
                pygame.transform.smoothscale_by(ball.image, fit_scale),
                ball_position, special_flags=ball.blendmode)
        # write the data onto the tab
        text[1].setText(bounce_data['speed'])
        text[2].setText(bounce_data['spin'])
        if bounce_data['critical'].magnitude() > 0:
            text[1].setColor(Color.red)
        elif bounce_data['rotate'].magnitude() > 0:
            if text[1].color != Color.green:
                text[1].setColor(Color.green)
        elif text[1].color != Color.white:
            text[1].setColor(Color.white)
        # draw the different vectors
        vector_scale = 5
        bounce_data['normal'] *= vector_scale * 10 * scale
        bounce_data['impact'] *= vector_scale * scale
        bounce_data['reflect'] *= vector_scale * scale
        bounce_data['final'] *= vector_scale * scale
        bounce_data['rotate'] *= vector_scale * scale
        ball_center = ball_offset + center
        critical = bounce_data['critical'].magnitude() > 0
        pygame.draw.line(tab.screen, Color.magenta,
                         center, bounce_data['normal'] + center )
        pygame.draw.line(tab.screen, Color.magenta,
                         center, bounce_data['impact'] + center,
                         width=5)
        pygame.draw.line(tab.screen, Color.cyan,
                         center, bounce_data['offset'] + center )
        pygame.draw.line(tab.screen, Color.blue,
                         center, bounce_data['reflect'] + center )
        pygame.draw.line(tab.screen, Color.red,
                         ball_center, bounce_data['final'] + ball_center,
                         width = (2 if not critical else 5))
        pygame.draw.line(tab.screen, Color.green,
                         ball_center, bounce_data['rotate'] + ball_center,
                         width = 5)
        # set controller text
        text[3].setText(self.controller)
        return

    @property
    def controller(self): return self._controller

    @controller.setter
    def controller(self, string):
        self._controller = string
        text = self._draw_striker_bounce_text
        # draw the controller text
        text[3].setText(self.controller)


    def move(self, x, y):
        super().move(x, y)
        if not self.inBounds():
            self._snapToEdge()
            self.velocity = 0
            self.impact_velocity = 0
        # put a limit on the maximum spring distance
        if self._spring_x and abs(self._spring_x - self.centerx) > self.game.width//2:
            self.impact_velocity = 0
            self._centerx = self._spring_x + self.game.width//2 * sign(self.game.width//2 - self._spring_x)

class Ball(GameSprite):
    def __init__(self, game=None):
        super().__init__(game)
        self.spin = 0
        self.velocity = pygame.math.Vector2(1, 0)

    def setup(self, speed, color, r, mass):
        self.speed_value = speed / 2
        self.speed_increase = 0
        self.min_speed = max(10 * (speed/20.0 + 1), 1)
        self.speed = self.min_speed
        self.mass = (mass / 10.0)
        self.rolling_friction = (
                0.1 *
                (speed/20.0) *
                (1 - 1.0 / (self.mass + 1)))
        self._substeps = 30
        self.color = color
        self.r = r
        ball = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA, 32)
        pygame.draw.circle(ball, self.color\
                , (r, r), r)
        self.setImage(ball)
        return self

    def _increase_speed(self, amount=1):
        self.speed_increase += amount
        self.min_speed = max(10 * ((self.speed_value + self.speed_increase)/10.0), 1)
        self.rolling_friction = (
                0.1 *
                (self.min_speed/10.0) *
                (1 - 1.0 / (self.mass + 1)))

    def _reset_speed_increase(self):
        self._increase_speed(-self.speed_increase)

    def _bounce(self, wall_normal):
        self.velocity.reflect_ip(wall_normal)
        # if too vertical, bounce more horizontal
        if abs(self.velocity.x*5) < abs(self.velocity.y) \
                and abs(self.spin) < 1:
            self.velocity.x = self.velocity.x * (1+ self.spin) * 2
            direction = -1 if self._x > self.game.centerx else 1
            if abs(self.velocity.x) < 0.1:
                self.velocity.x = self.min_speed * direction
            self.spin -= direction * self.velocity.y // 4
            self.speed = self.velocity.magnitude()

    def bounceOnWalls(self):
        next_y = self._y + self.velocity.y
        next_x = self._x + self.velocity.x
        floor = self.game.bottom
        right = self.game.right
        if next_y <= 0:
            self._y = 0
            self._bounce(pygame.math.Vector2(0, -1))
        elif next_y + self.height >= floor:
            self._y = floor - self.height
            self._bounce(pygame.math.Vector2(0, 1))
        if next_x <= 0:
            self._x = 0
            self._bounce(pygame.math.Vector2(1, 0))
        elif next_x + self.width >= right:
            self._x = right - self.width
            self._bounce(pygame.math.Vector2(-1, 0))

    def scoreOnPlayers(self):
        goals = self.game.goals # dict(striker, goal_rect)
        hitbox = self._rect
        for striker, zone in goals.items():
            if zone.colliderect(hitbox):
                self.game._scoreOnPlayer(striker)

    def bounceOnStrikers(self):
        for striker in self.game.strikers:
            if pygame.sprite.collide_mask(self, striker):
                self._bounceOnStriker(striker)

    def _unclipFromStriker(self, striker, striker_normal):
        backstep = striker_normal
        limit = self._substeps
        self.move(striker.impact_velocity, striker.velocity)
        while pygame.sprite.collide_mask(self, striker):
            self.move(backstep.x, backstep.y)
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
        striker_normal.normalize_ip()
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
        for _ in range(self._substeps):
            future_striker_image = pygame.transform.rotate(
                    striker.image, 2 * striker.rot_velocity/self._substeps)
            future_striker_mask = pygame.mask.from_surface(
                    future_striker_image)
            mask_offset = pygame.math.Vector2(
                    striker.rect.centerx - future_striker_image.get_width()/2,
                    striker.rect.centery - future_striker_image.get_height()/2)
            mask_offset -= pygame.math.Vector2(self.rect.x, self.rect.y)
            hitting = self.mask.overlap(future_striker_mask, mask_offset)
            if hitting == None:
                continue
            else:
                break
        if hitting == None:
            return final_vector
        # then, determine the direction and angle of the hit
        striker_rot_hit_vector = striker_normal
        future_offset = offset_vector.rotate(striker.rot_velocity)
        rot_hit_speed = ((future_offset - offset_vector).magnitude()
                         * striker.elasticity / self.mass * 1.2)
        if striker_rot_hit_vector.length() == 0:
            return final_vector
        striker_rot_hit_vector.scale_to_length(rot_hit_speed)
        # decrease striker rotational speed by hit speed
        striker.rot_velocity -= sign(striker.rot_velocity) * rot_hit_speed * self.mass
        final_vector += striker_rot_hit_vector
        return final_vector

    def _bounceOnStriker(self, striker):
        # calculate information about the collision
        striker_normal = self._normalizedStrikerImpactAngle(striker)
        direction = (-1 if self.velocity.x < 0 else 1)
        offset_vector = pygame.math.Vector2(
                self._cx - striker._cx,
                self._cy - striker._cy)
        final_vector = pygame.math.Vector2(0, 0)
        # first, move ball back until not clipping Striker
        self._unclipFromStriker(striker, striker_normal)
        # reflect off the striker
        reflect_vector = self.velocity.copy().reflect(striker_normal)
        reflect_vector.scale_to_length(self.speed * striker.elasticity)
        final_vector = reflect_vector.copy()
        # apply modifications based on the striker's attributes
        # modification 1: striker power
        striker_hit_vector = striker_normal.copy()
        striker_hit_vector.scale_to_length(striker.power)
        final_vector += striker_hit_vector
        # modification 2: striker vertical movement (spin)
        spin_mod = striker.velocity * striker.grip / self.mass * direction / 2.0
        self.spin += (abs(striker_normal.x)) * spin_mod
        # modification 3: striker rotation
        self.spin += striker.rot_velocity * striker.grip / 2.0
        rotate_hit_vector = self._rotateHitOnStriker(striker)
        final_vector += rotate_hit_vector
        # modification 4: stuck proofing
        # correct bounce if not towards the center and away from the striker
        towards_striker = (offset_vector.x > 0) != (final_vector.x > 0)
        towards_center = (self.game._width//2 - self._cx) * final_vector.x >= 0
        if towards_striker or not towards_center:
            new_offset = offset_vector.copy()
            new_offset.scale_to_length(striker.power)
            final_vector = (rotate_hit_vector +
                            striker_hit_vector +
                            new_offset)
        # modification 5: striker horizontal impact
        striker_impact = striker.impact_velocity
        if sign(striker_impact) == sign(final_vector.x):
            striker_impact = abs(striker_impact) * striker_normal * striker.elasticity
            final_vector += striker_impact / self.mass * striker.springiness * 2
        else: striker_impact = pygame.math.Vector2(0,0)
        # modification 6: critical hit!
        # increase power by 10% if the ball hit the striker corner
        # which can be detected with towards_striker
        critical = pygame.math.Vector2(0, 0)
        if towards_striker:
            final_vector *= 1.1
            critical = final_vector
        # apply the equal and opposite force to the striker
        striker.impact_velocity -= final_vector.x
        striker.velocity -= final_vector.y
        # put the bounce onto the display
        # apply final calculated vector
        final_vector /= self.mass
        if isclose(final_vector.magnitude(), 0):
            self.velocity = striker_hit_vector + reflect_vector
            if isclose(self.velocity.magnitude(), 0):
                self.velocity = striker_hit_vector
        else:
            self.velocity = final_vector
        self.speed = self.velocity.magnitude()
        # apply a log_scale to the spin (keeps it around 3)
        self.spin = math.log(abs(self.spin)+1) * 3 * sign(self.spin)
        # apply an extra layer of friction onto the striker
        striker._apply_friction()
        bounce_data = {"normal": striker_normal,
                       "impact": striker_impact,
                       "offset": offset_vector,
                       "reflect": reflect_vector,
                       "final": self.velocity,
                       "rotate": rotate_hit_vector,
                       "critical": critical,
                       "speed": self.speed,
                       "spin": self.spin}
        striker.displayStrikerBounce(self, bounce_data)

    def _spin_effect(self):
        if abs(self.spin) < self.rolling_friction:
            self.spin = 0
            return
        elif abs(self.spin) > 2:
            self.spin = 1.8 * sign(self.spin)
        angle_change = self.spin / self.speed / self.mass / self.rolling_friction / 3
        self.velocity.rotate_ip(angle_change/self._substeps)
        spin_friction = (self.rolling_friction/self._substeps)
        self.spin -= spin_friction / 2 * sign(self.spin)

    def roll(self):
        self.speed -= self.rolling_friction/self._substeps
        if self.speed < self.min_speed:
            self.speed = self.min_speed
        if isclose(self.velocity.length(), 0):
            self.velocity = pygame.math.Vector2(1, 0)
        self.velocity.scale_to_length(self.speed)
        self.move(float(self.velocity.x/self._substeps),
                  float(self.velocity.y/self._substeps))
        self._spin_effect()

    def update(self):
        for _ in range(self._substeps):
            self.roll()
            self.bounceOnStrikers()
        self.bounceOnWalls()
        self.scoreOnPlayers()

class PongGame(Game):
    # configuration values
    striker_size = (40, 140)
    striker_speed = 20
    striker_accel = 10
    striker_rot_speed = 10
    striker_rot_accel = 10
    striker_color = Color.white
    striker_friction = 8
    striker_power = 12
    striker_grip = 10
    striker_elasticity = 10
    striker_springiness = 10
    ball_speed = 10
    ball_color = Color.white
    ball_size = 10
    ball_mass = 15

    def __init__(self, w, h = None, padding=(2, 2, 2, 2)):
        side_width = w//16 * 3
        adjusted_width = w - side_width*2
        super().__init__(adjusted_width, h, padding=padding)
        self.base_background.fill(Color.black)
        self.name = "pong"
        self.fps = 60 # note that a different fps radically changes the game
        # increase ball speed by 1 every 5 seconds
        self.SPEED_INCREASE_TIME = 3
        self._initialize_screens(side_width)
        self._initialize_sprites()
        self._initialize_menu_sprites()
        self._initialize_controls()
        self._window.addGame(self, (side_width, 0))
        self._window.name = "Mugical Pong"

    def _initialize_screens(self, w):
        self.debug_screen_left = DisplayScreen(w, self.height)
        self.debug_screen_left.splitTabs(3)
        # left side chooses blueish colors
        for tab in self.debug_screen_left.tabs:
            color = Color.randomBetween(0.7, 0.8, 1, 0.8)
            tab.base_background.fill(color)
        self.debug_screen_right = DisplayScreen(w, self.height)
        self.debug_screen_right.splitTabs(3)
        # right side chooses purplish colors
        for tab in self.debug_screen_right.tabs:
            color = Color.randomBetween(0.8, 0.9, 1, 0.8)
            tab.base_background.fill(color)
        self._window.addScreen(self.debug_screen_left, (0, 0))
        self._window.addScreen(self.debug_screen_right, (w + self.abs_width, 0))

    def _initialize_sprites(self):
        # initialize strikers
        striker_parameters = (
                self.striker_color,
                self.striker_size,
                self.striker_friction,
                self.striker_speed,
                self.striker_accel,
                self.striker_rot_speed,
                self.striker_rot_accel,
                self.striker_power,
                self.striker_grip,
                self.striker_elasticity,
                self.striker_springiness)
        self.striker_left = Striker(self)
        self.striker_right = Striker(self)
        self.striker_left.setup(*striker_parameters)
        self.striker_right.setup(*striker_parameters)
        self._add_sprite(self.striker_left)
        self._add_sprite(self.striker_right)
        self.strikers = pygame.sprite.Group()
        self.strikers.add(self.striker_left, self.striker_right)
        self.striker_right._debug = True
        self.striker_right._debug_screen = self.debug_screen_right
        self.striker_left._debug = True
        self.striker_left._debug_screen = self.debug_screen_left

        # initialize ball
        ball_parameters = (self.ball_speed,
                           self.ball_color,
                           self.ball_size,
                           self.ball_mass)
        self.ball = Ball().setup(*ball_parameters)
        self._add_sprite(self.ball)

        # setup striker goals
        goal_length = 5
        self.goals = {self.striker_left: None,
                      self.striker_right: None}
        self.goals[self.striker_left] = pygame.Rect(
                (0, 0),
                (goal_length, self._height))

        self.goals[self.striker_right] = pygame.Rect(
                (self._width - goal_length, 0),
                (goal_length, self._height))

        # if you want to see the goals
        goal_sprite1 = GameSprite(self)
        goal_sprite1._rect = self.goals[self.striker_left]
        goal_sprite2 = GameSprite(self)
        goal_sprite2._rect = self.goals[self.striker_right]
        #self._add_sprite(goal_sprite1, goal_sprite2)

        # setup score text
        score_text_size = 100
        self.s1_score_text = TextSprite().setFormatString("{}")
        self.s2_score_text = TextSprite().setFormatString("{}")
        self.s1_score_text.setFontSize(score_text_size)
        self.s2_score_text.setFontSize(score_text_size)
        self._add_sprite(self.s1_score_text)
        self._add_sprite(self.s2_score_text)
        self.s1_score = 0
        self.s2_score = 0
        self._update_score()

    def _initialize_menu_sprites(self):
        # setup menu sprites
        self.menu_title_text = TextSprite(self)
        self.menu_title_text.layer = 5
        self._add_sprite(self.menu_title_text)
        self.menu_title_text.hide()
        self.menu_title_text.setFontSize(100)
        self.menu_title_text.setFormatString("{}")
        self.menu_title_text.bold = True
        self.menu_subtitle_text = TextSprite(self)
        self.menu_subtitle_text.layer = 5
        self._add_sprite(self.menu_subtitle_text)
        self.menu_subtitle_text.hide()
        self.menu_subtitle_text.setFontSize(40)
        self.menu_subtitle_text.setFormatString("{}")
        self.menu_subtitle_text.setColor(Color.white)
        #self.menu_subtitle_text.italic = True
        self.menu_background_sprite = Sprite(self)
        self.menu_background_sprite.layer = 3
        self._add_sprite(self.menu_background_sprite)
        self.menu_background_sprite.moveTo(0, 0)
        menu_background = pygame.Surface(self.screen_rect.size)
        menu_background.fill(Color.black)
        self.menu_background_sprite.setImage(menu_background)
        self.menu_background_sprite.hide()

    def _update_menu_text_position(self):
        middle = self._height // 4 + 20
        center = self._width // 2
        self.menu_title_text.moveCenterTo(center, middle)
        self.menu_subtitle_text.moveCenterTo(center, middle)
        self.menu_subtitle_text.y = (self.menu_title_text.y
                                     + self.menu_title_text.height)

    def _draw_menu_screen(self, title_text, subtitle_text, background=None):
        self.menu_title_text.setText(title_text)
        self.menu_subtitle_text.setText(subtitle_text)
        self.menu_title_text.show()
        self.menu_subtitle_text.show()
        self._update_menu_text_position()
        if background is not None:
            self.menu_background_sprite.show()
        if type(background) is tuple: # solid color background
            self.menu_background_sprite.base_image.fill(background)
            self.menu_background_sprite._update_image()
        elif isinstance(background, pygame.Surface): # image background
            menu_background = pygame.Surface(self.screen_rect.size)
            fit_scale = self.screen_rect.height/background.get_height()
            background = pygame.transform.smoothscale_by(background, fit_scale)
            centered = ((self.screen_rect.width - background.get_width())//2, 0)
            self.menu_background_sprite.base_image.blit(background, centered)
            self.menu_background_sprite._update_image()
        self._draw_sprites()

    def _hide_menu_screen(self):
        self.menu_title_text.hide()
        self.menu_subtitle_text.hide()
        self.menu_background_sprite.hide()

    def _update_score(self):
        self.s1_score_text.setText(self.s1_score)
        self.s2_score_text.setText(self.s2_score)

    def _reset(self):
        middle = self._height // 2
        top_middle = self._height // 4
        center = self._width // 2
        left = self._width // 8
        right = self._width - left
        center_left = self._width // 6
        center_right = self._width - center_left
        self.striker_left.moveCenterTo(left, middle)
        self.striker_right.moveCenterTo(right, middle)
        self.striker_left._spring_x = left
        self.striker_right._spring_x = right
        self.striker_left._reset()
        self.striker_right._reset()
        self.ball.moveCenterTo(center, middle)
        if self.s1_score - self.s2_score == 0:
            server = random.choice((-1, 1))
        elif self.s1_score > self.s2_score: server = 1
        else: server = -1
        self.ball.velocity = pygame.math.Vector2(server, 0)
        self.ball._reset_speed_increase()
        self.ball.speed = self.ball.min_speed
        self.ball.spin = 0
        self.s1_score_text.moveCenterTo(center_left,
                                        top_middle)
        self.s2_score_text.moveCenterTo(center_right,
                                        top_middle)
        self._update_score()

    def _restart(self):
        self.s1_score = 0
        self.s2_score = 0
        self._reset()

    def _initialize_controls(self):
        self.p1_up = False
        self.p1_dn = False
        self.p1_lt = False
        self.p1_rt = False
        self.p1_lm = False
        self.p1_rm = False
        self.p2_up = False
        self.p2_dn = False
        self.p2_lt = False
        self.p2_rt = False
        self.p2_lm = False
        self.p2_rm = False
        self.p1_CPU = False
        self.p2_CPU = False

    def _handle_key(self, event):
        key = Key(event)
        # arrow keys/ijkl & ,.uo for player 1
        if key in (pygame.K_UP, pygame.K_i):
            self.p1_up = key.down
        elif event.key in (pygame.K_DOWN, pygame.K_k):
            self.p1_dn = key.down
        elif event.key in (pygame.K_RIGHT, pygame.K_l):
            self.p1_rt = key.down
        elif event.key in (pygame.K_LEFT, pygame.K_j):
            self.p1_lt = key.down
        elif event.key in (pygame.K_COMMA, pygame.K_u):
            self.p1_lm = key.down
        elif event.key in (pygame.K_PERIOD, pygame.K_o):
            self.p1_rm = key.down
        # wasd & qezxcv for player 2
        elif event.key in (pygame.K_w,):
            self.p2_up = key.down
        elif event.key in (pygame.K_s,):
            self.p2_dn = key.down
        elif event.key in (pygame.K_a,):
            self.p2_lt = key.down
        elif event.key in (pygame.K_d,):
            self.p2_rt = key.down
        elif event.key in (pygame.K_q, pygame.K_z):
            self.p2_lm = key.down
        elif event.key in (pygame.K_e, pygame.K_x):
            self.p2_rm = key.down
        # p to pause
        elif key in (pygame.K_p,) and key.down:
            self.togglePause()
        # r to restart
        elif key in (pygame.K_r,) and key.down:
            self._restart()
        # 1,2 to toggle CPU on left and right player
        elif key in (pygame.K_1, ) and key.down:
            self.p2_CPU = not self.p2_CPU
            self._update_controller_info()
        elif key in (pygame.K_2, ) and key.down:
            self.p1_CPU = not self.p1_CPU
            self._update_controller_info()

    def _update_controller_info(self):
        self.striker_right.controller = ("CPU" if self.p1_CPU else "Keyboard")
        self.striker_left.controller = ("CPU" if self.p2_CPU else "Keyboard")

    def _handle_p1_controls(self):
        if self.p1_CPU:
            self.striker_right._CPUMovement()
            return
        if self.p1_up:
            self.striker_right._moveUp()
        if self.p1_dn:
            self.striker_right._moveDown()
        if self.p1_rt and self.p1_lt:
            self.striker_right._rotateTowardsNormal()
        elif self.p1_rt:
            self.striker_right._rotateRight()
        elif self.p1_lt:
            self.striker_right._rotateLeft()
        if self.p1_lm:
            self.striker_right._moveLeft()
        if self.p1_rm:
            self.striker_right._moveRight()

    def _handle_p2_controls(self):
        if self.p2_CPU:
            self.striker_left._CPUMovement()
            return
        if self.p2_up:
            self.striker_left._moveUp()
        if self.p2_dn:
            self.striker_left._moveDown()
        if self.p2_rt and self.p2_lt:
            self.striker_left._rotateTowardsNormal()
        elif self.p2_rt:
            self.striker_left._rotateRight()
        elif self.p2_lt:
            self.striker_left._rotateLeft()
        if self.p2_lm:
            self.striker_left._moveLeft()
        if self.p2_rm:
            self.striker_left._moveRight()

    def _increase_ball_speed(self):
        self.ball._increase_speed(1/self.fps/self.SPEED_INCREASE_TIME)

    def _update(self):
        self._handle_p1_controls()
        self._handle_p2_controls()
        self._increase_ball_speed()

    def _scoreOnPlayer(self, player):
        if player == self.striker_left:
            self.s2_score += 1
        elif player == self.striker_right:
            self.s1_score += 1
        self._update_score()
        self._reset()

    def pause(self):
        super().pause()
        title_text = "PAUSED"
        subtitle_text = "Press P to continue"
        self._draw_menu_screen(title_text, subtitle_text, background=None)

    def unpause(self):
        super().unpause()
        self._hide_menu_screen()

# PONG GAME but with Mugic Controls
class MugicPongGame(PongGame):
    # configuration values
    ball_speed = 8
    striker_power = 15
    striker_speed = 30
    ball_mass = 20
    striker_grip = 10
    striker_size = (50, 160)
    ball_size = 15

    def __init__(self, w, h, padding=(2, 2, 2, 2), port1=4000, port2=4001):
        super().__init__(w, h, padding)
        self.mugic_player_1 = MugicDevice(port=port1)
        self.mugic_player_2 = MugicDevice(port=port2)
        self._init_mugic_image()
        self._init_mugic_text()
        self._current_screen = None
        self._frame_count = 0
        # apply game background to game screen
        if self._game_background is not None:
            centered = ((self.width - self._game_background.get_width())//2, 0)
            self.base_background.blit(self._game_background, centered)
            self._refresh_background()
            for tab in [*self.debug_screen_left.tabs, *self.debug_screen_right.tabs]:
                tab_position = tab._screen.get_abs_offset()
                tab_position = [-p/self.scale for p in tab_position]
                tab.base_background.blit(self._game_background, tab_position)
                tab._refresh_background()
                tab.refresh()

    def _stop(self):
        super()._stop()
        self.mugic_player_1.close()
        self.mugic_player_2.close()

    def _initialize_sprites(self):
        super()._initialize_sprites()
        # update ball to use ball image
        ball = load_image(resource_path('assets/ball.png'), convert_alpha=True)
        if ball is not None:
            self.ball.setImage(ball)
            self.ball.resize(self.ball.r*2)
        # create pointer sprites
        self.pointer_right = GameSprite(self)
        self.pointer_right.setImage(self.striker_right.base_image.copy())
        self.pointer_right.base_image.fill(Color.darkgrey)
        self.pointer_right.layer = -1
        self.pointer_right.hide()
        self.pointer_left = GameSprite(self)
        self.pointer_left.setImage(self.striker_left.base_image.copy())
        self.pointer_left.base_image.fill(Color.darkgrey)
        self.pointer_left.layer = -1
        self.pointer_left.hide()
        self._add_sprite(self.pointer_right, self.pointer_left)
        # initialize title screen and gamescreen background
        mugical_background = resource_path('assets/mugical_title_bg.jpg')
        self._title_background = load_image(mugical_background, self.size)
        game_background = resource_path('assets/mugical_game_bg.jpg')
        self._game_background= load_image(game_background, self.size)
        self._initialize_credit_screen_sprites()

    # internal class - a bouncing sprite
    class _BounceSprite(GameSprite):
        def __init__(self, screen, collision_group=None):
            super().__init__(screen)
            self.velocity = pygame.math.Vector2(1, 0)
            self.speed = (5 * random.random() + 1)
            self.velocity.rotate_ip(random.random() * 360)
            self.collision_group = collision_group

        def _bounce(self, wall_normal):
            self.velocity.reflect_ip(wall_normal)

        def bounceOffOthers(self):
            if self.collision_group is None: return False
            ret_val = False
            for sprite in self.collision_group:
                if not pygame.sprite.collide_rect(self, sprite): continue
                ret_val = True
                offset_vector = pygame.math.Vector2(sprite._cx-self._cx,
                                                    sprite._cy-self._cy)
                if offset_vector.magnitude() < 1: continue
                self.velocity = offset_vector * -1
                self.velocity.rotate_ip(60 * (random.random() - 0.5))
                self.move(*(offset_vector.normalize() * -1))
                sprite.speed = (self.speed + sprite.speed) / 2.1
                if random.random() > 0.9: self.speed = (8 * random.random()) + 2
                elif sprite.speed < 0.5: self.speed = (3 * random.random()) + 1
                else: self.speed = sprite.speed
            self.velocity.normalize_ip()
            return ret_val

        def update(self):
            Ball.bounceOnWalls(self)
            self.bounceOffOthers()
            self.move(*(self.velocity * self.speed))

    class _ControllableBounceSprite(_BounceSprite):
        def __init__(self, *args):
            super().__init__(*args)
            self._p1 = False
            self._p2 = False

        def update(self):
            self.speed = 10
            if self._p1:
                pointing = abs(self.game.p1_y)/self.game.height
                if self.game.p1_up or pointing < 0.3 and pointing > 0.01: self.move(0, -15)
                if self.game.p1_dn or pointing > 0.7: self.move(0, 15)
            elif self._p2:
                pointing = abs(self.game.p2_y)/self.game.height
                if self.game.p2_up or pointing < 0.3 and pointing > 0.01: self.move(0, -15)
                if self.game.p2_dn or pointing > 0.7: self.move(0, 15)
            if self.bottom > self.game.bottom:
                self.bottom = self.game.bottom
            if self.top < self.game.top:
                self.top = self.game.top

    def _initialize_credit_screen_sprites(self):
        # load image assets
        group_photo = resource_path('assets/team_mugical.jpg')
        mari_kimura= resource_path('assets/mari_kimura.jpg')
        mugic_photo= resource_path('assets/mugic.jpg')
        team_logo = resource_path('assets/mugical_logo.png')
        ball = resource_path('assets/ball.png')
        bryan_cat = resource_path('assets/bryan_cat.jpg')
        bg = resource_path('assets/mugical_title_bg.jpg')
        loaded_credit_images = list()
        for image_path in [group_photo, mari_kimura, mugic_photo, team_logo, ball, bryan_cat, bg]:
            try:
                image = pygame.image.load(image_path)
                if image_path not in (ball, ):
                    height = random.random() * 50 + 150
                else: height = None
                loaded_credit_images.append((image.convert_alpha(), height))
            except FileNotFoundError:
                logging.warning(f"Could not load {image_path} for credit page!")
        loaded_credit_images.append((self.ball.base_image.copy(), None))
        team_member_headshots = [resource_path(f"assets/{name}.jpg") for name in (
            "eric", "aj", "shreya", "kaitlyn", "melody", "bryan")]
        for image_path in team_member_headshots:
            image = load_image(image_path)
            if image is None: continue
            height = random.random() * 50 + 75
            loaded_credit_images.append((image, height))
        # create image sprites
        self.credit_images = pygame.sprite.Group()
        for image, height in loaded_credit_images:
            image_sprite = self._BounceSprite(self, self.credit_images)
            image_sprite.moveCenterTo(*self.center)
            image_sprite.layer = 4
            self.addSprite(image_sprite)
            image_sprite.hide()
            if height is not None:
                fit_scale = height/image.get_height()
                image = pygame.transform.smoothscale_by(image, fit_scale)
            image_sprite.setImage(image)
            self.credit_images.add(image_sprite)

        # create credit screen strikers
        _striker = self.striker_right.base_image.copy()
        credit_striker_1 = self._ControllableBounceSprite(self, self.credit_images)
        credit_striker_1.setImage(_striker)
        credit_striker_1._p2 = True
        credit_striker_1.layer = 4
        credit_striker_1.hide()
        self.credit_images.add(credit_striker_1)
        credit_striker_1.moveCenterTo(self.width//10, self.height//2)
        self.addSprite(credit_striker_1)

        credit_striker_2 = self._ControllableBounceSprite(self, self.credit_images)
        credit_striker_2.layer = 4
        credit_striker_2.hide()
        credit_striker_2.setImage(_striker)
        credit_striker_2._p1 = True
        self.credit_images.add(credit_striker_2)
        credit_striker_2.moveCenterTo(self.width - self.width//10, self.height//2)
        self.addSprite(credit_striker_2)

    def _initialize_controls(self):
        super()._initialize_controls()
        self.p1_jolt = False
        self.p1_y = 0
        self.p1_x = 0
        self.p1_rotx = 0
        self.p1_roty = 0
        self.p1_rotz = 0
        self.p1_moving = 0
        self.p1_thrust = 0
        self.p1_swing = 0
        self.p2_jolt = False
        self.p2_y = 0
        self.p2_x = 0
        self.p2_rotx = 0
        self.p2_roty = 0
        self.p2_rotz = 0
        self.p2_moving = 0
        self.p2_thrust = 0
        self.p2_swing = 0

    def _update_controller_info(self):
        self.striker_right.controller = (
                "CPU" if self.p1_CPU else "Keyboard" if not self.mugic_player_1.connected()
                else str(self.mugic_player_1))
        self.striker_left.controller = (
                "CPU" if self.p2_CPU else "Keyboard" if not self.mugic_player_2.connected()
                else str(self.mugic_player_1))

    def _handle_mugic_controls(self):
        # we query a bunch of useful data from both mugics; not everything
        # is used though
        if not self.p1_CPU and self.mugic_player_1.connected():
            m1 = self.mugic_player_1
            m1_data = m1.next()
            # disable keyboard
            self.p1_rt = False
            self.p1_lt = False
            self.p1_up = False
            self.p1_dn = False
            self.p1_rm = False
            self.p1_lm = False
            # control position with the pointing angle
            m1_point = m1.pointingAt(m1_data)
            # fit the pointing values (-1 to 1) to screen position
            targetY = self._height//2 - int(m1_point[2] * self._height//2 * 1.2)
            targetX = self._width//2 + int(m1_point[1] * self._width//2)
            self.p1_y = targetY
            self.p1_x = targetX
            self.p1_thrust = m1.thrustAccel()
            self.p1_swing = m1.swingAccel()
            self.p1_rotx, self.p1_roty, self.p1_rotz = IMU.euler(m1_data) or (0, 0, 0)
            self.p1_moving = m1.moving(threshold=0.1, datagram=m1_data)
            # control rotation with the tilt
            self.p1_rt = m1._facing(axis=2, direction=140, threshold=40, datagram=m1_data)
            self.p1_lt = m1._facing(axis=2, direction=-140, threshold=40, datagram=m1_data)
            # detect jolt
            self.p1_jolt = m1.jolted(20)

        if not self.p2_CPU and self.mugic_player_2.connected():
            m2 = self.mugic_player_2
            m2_data = m2.next()
            # disable keyboard
            self.p2_rt = False
            self.p2_lt = False
            self.p2_up = False
            self.p2_dn = False
            self.p2_rm = False
            self.p2_lm = False
            # control position with the pointing angle
            m2_point = m2.pointingAt(m2_data)
            targetY = self._height//2 - int(m2_point[2] * self._height//2 * 1.2)
            targetX = self._width//2 + int(m2_point[1] * self._width//2)
            self.p2_y = targetY
            self.p2_x = targetX
            self.p2_thrust = m2.thrustAccel()
            self.p2_swing = m2.swingAccel()
            self.p2_rotx, self.p2_roty, self.p2_rotz = IMU.euler(m2_data) or (0, 0, 0)
            self.p2_moving = m2.moving(datagram=m2_data)
            # control rotation with the tilt
            self.p2_rt = m2._facing(axis=2, direction=140, threshold=40, datagram=m2_data)
            self.p2_lt = m2._facing(axis=2, direction=-140, threshold=40, datagram=m2_data)
            # detect jolt
            self.p2_jolt = m2.jolted(20)

    def _controls(self):
        # Mugic player 1 controls
        if self.mugic_player_1.connected() and not self.p1_CPU:
            # match pointer to actual mugic pointing position
            self.pointer_right.show()
            self.pointer_right.centery = self.p1_y
            self.pointer_right.rotateTo(self.striker_right.rotation)
            # aim assist - if close enough to ball move towards it
            close_to_ball = self.pointer_right.distanceTo(self.ball) < self._height // 5
            pointer_close = abs(self.pointer_right.centery - self.ball.centery) < self._height//6
            striker_close = abs(self.striker_right.centery - self.ball.centery) < self._height//6
            if close_to_ball and striker_close and not self.p1_jolt:
                self.striker_right._moveTowardsBall()
            else: # normally, just move towards pointing position
                for _ in range(3):
                    self.striker_right._moveTowardsPoint(self.p1_y)
            # on thrust - swing forward
            thrusting = abs(self.p1_thrust) > abs(self.p1_swing)
            if thrusting:
                self.p1_thrust = max(0, self.p1_thrust - 3) * 4
                self.striker_right.impact_velocity -= min(self.p1_thrust, 8)
                # if thrust is powerful enough, add light homing
                if pointer_close and self.p1_thrust > 8:
                    for _ in range(4):
                        self.striker_right._moveTowardsBall()
            # otherwise if jolted, launch forward
            elif self.p1_jolt:
                self.striker_right.impact_velocity -= 15
                # scale based on distance from ball - launches further if the ball is further
                self.striker_right.impact_velocity -= abs(20 * (self.pointer_right.x - self.ball.x)/self._width)
                self.p1_rotz = -self.striker_right.rotation

            # handle rotations
            if not (self.p1_rt or self.p1_lt):
                self.striker_right._rotateTowardsAngle(-self.p1_rotz)
            else:
                if self.p1_rt:
                    self.striker_right._rotateRight()
                if self.p1_lt:
                    self.striker_right._rotateLeft()
        else: # if not connected, use normal controls
            self.pointer_right.hide()
            self._handle_p1_controls()

        # Mugic player 2 controls - just a mirror of above
        if self.mugic_player_2.connected() and not self.p2_CPU:
            # match pointer to actual mugic pointing position
            self.pointer_left.show()
            self.pointer_left.centery = self.p2_y
            self.pointer_left.rotateTo(self.striker_left.rotation)
            # aim assist - if close enough to ball move towards it
            close_to_ball = self.pointer_left.distanceTo(self.ball) < self._height // 4
            pointer_close = abs(self.pointer_left.centery - self.ball.centery) < self._height//6
            striker_close = abs(self.striker_left.centery - self.ball.centery) < self._height//6
            if close_to_ball and striker_close and not self.p2_jolt:
                self.striker_left._moveTowardsBall()
            else: # normally, just move towards pointing position
                for _ in range(3):
                    self.striker_left._moveTowardsPoint(self.p2_y)
            # on thrust - swing forward
            thrusting = abs(self.p2_thrust) > abs(self.p2_swing)
            if thrusting:
                self.p2_thrust = max(0, self.p2_thrust - 3) * 4
                self.striker_left.impact_velocity += min(self.p2_thrust, 8)
                # if thrust is powerful enough, add light homing
                if pointer_close and self.p2_thrust > 8:
                    for _ in range(4):
                        self.striker_left._moveTowardsBall()
            # otherwise if jolted, launch forward
            elif self.p2_jolt:
                self.striker_left.impact_velocity += 15
                # scale based on distance from ball - launches further if the ball is further
                self.striker_left.impact_velocity += abs(20 * (self.pointer_left.x - self.ball.x)/self._width)
                self.p2_rotz = -self.striker_left.rotation # lock rotation

            # handle rotations
            if not (self.p2_rt or self.p2_lt):
                self.striker_left._rotateTowardsAngle(-self.p2_rotz)
            else:
                if self.p2_rt:
                    self.striker_left._rotateRight()
                if self.p2_lt:
                    self.striker_left._rotateLeft()
        else: # if not connected, use normal controls
            self.pointer_left.hide()
            self._handle_p2_controls()


    def _handle_events(self):
        super()._handle_events()
        if self._frame_count % 3 == 0:
            self._handle_mugic_controls()

    def _init_mugic_image(self):
        self.p1_mugic_display = MugicDisplay(self.mugic_player_1)
        self.p2_mugic_display = MugicDisplay(self.mugic_player_2)
        p1_tab1 = self.debug_screen_left.getTab(0)
        p2_tab1 = self.debug_screen_right.getTab(0)
        p1_tab1.background.set_colorkey(Color.black)
        p2_tab1.background.set_colorkey(Color.black)

    def _insert_mugic_image(self):
        p1_tab1 = self.debug_screen_right.getTab(0)
        mugic_p1_image = self.p1_mugic_display.getImage(p1_tab1.abs_width, p1_tab1.abs_height)
        p1_tab1.refresh()
        p1_tab1._screen.blit(mugic_p1_image, (0, 0))
        p2_tab1 = self.debug_screen_left.getTab(0)
        mugic_p2_image = self.p2_mugic_display.getImage(p2_tab1.abs_width, p2_tab1.abs_height)
        p2_tab1.refresh()
        p2_tab1._screen.blit(mugic_p2_image, (0, 0))

    def _init_mugic_text(self):
        instruction_text = "Instructions: H \n P to pause \n R to reset"
        self.p1_mugic_text = self.debug_screen_right.writeNewText("NO CONNECTION", tab=2)
        self.p2_mugic_text = self.debug_screen_left.writeNewText(instruction_text, tab=2)
        p1_txt, p2_txt = self.p1_mugic_text, self.p2_mugic_text
        p1_txt.move(15, 10)
        p2_txt.move(15, 10)
        p1_txt.setFontSize(30)
        p2_txt.setFontSize(30)
        p1_txt.setFontType(MONOSPACE)
        p2_txt.setFontType(MONOSPACE)

    def _insert_mugic_text(self):
        p1_txt, p2_txt = self.p1_mugic_text, self.p2_mugic_text
        if self.mugic_player_1.connected():
            p1_txt.setText(self.p1_mugic_display.text)
            if p1_txt._fontsize > 17: # to override default font size
                p1_txt.setFontSize(17)
        if self.mugic_player_2.connected():
            p2_txt.setText(self.p2_mugic_display.text)
            if p2_txt._fontsize > 17:
                p2_txt.setFontSize(17)
        return

    def _calibrate_mugics(self):
        self.mugic_player_1.calibrate()
        self.mugic_player_2.calibrate()
        if not self.p1_CPU and self.mugic_player_1.connected():
            self.striker_right.controller = str(self.mugic_player_1)
        if not self.p2_CPU and self.mugic_player_2.connected():
            self.striker_left.controller = str(self.mugic_player_2)

    def unpause(self):
        super().unpause()
        self._current_screen = "game"

    # additional keyboard controls
    def _handle_key(self, event):
        super()._handle_key(event)
        key = Key(event)
        # space to calibrate both
        if key in (pygame.K_SPACE, ):
            self._calibrate_mugics()
        # m to open title screen
        if key in (pygame.K_m,) and key.down:
            if self._current_screen == "title":
                self.unpause()
            else: self._title_screen()
        # h to open instruction screen
        if key in (pygame.K_h, ) and key.down:
            if self._current_screen == "instruction":
                self.unpause()
            else: self._instruction_screen()
        # c to open credits
        if key in (pygame.K_c, ) and key.down:
            if self._current_screen == "credits":
                self.unpause()
            else: self._credits_screen()

    # override so pause only pauses the game sprites - can still see Mugic info
    def _tick(self):
        if self._pause:
            self._update()
            if self._current_screen == "credits":
                self.credit_images.update()
            return
        super()._tick()

    def _title_screen(self):
        self.pause()
        self._current_screen = "title"
        title_text = "MUGICAL BALL" if self._title_background is None else ""
        subtitle_text = "press P to start, H for instructions, C for credits"
        self._draw_menu_screen(title_text, subtitle_text,
                               background=self._title_background\
                                       or Color.randomBetween(0.8, 1.0, 0.6) )

    def _instruction_screen(self):
        self.pause()
        self._current_screen = "instruction"
        title_text = "INSTRUCTIONS"
        instruction_text = \
"""Keyboard Controls:
* right side - arrow keys,. or ijkluo
* left side - wasdqe

Mugic Controls:
* spacebar to calibrate
* press 1 or 2 to activate CPU
* point up/down to move striker
* twist right/left to rotate striker
* stab in pointing direction to swing
* shake to launch striker

Press P to continue, R to reset
Press M to return to Menu
Press C to view Credits
"""
        self._draw_menu_screen(title_text, instruction_text,
                               background=self._title_background or Color.black)

    def _credits_screen(self):
        self.pause()
        self._current_screen = "credits"
        title_text = "CREDITS"
        credits_text = \
"""UCI Informatics Senior Capstone 2024-25
    INF 191AB - Professor D. Denenberg
Team Mugical
    Developer: Eric Xu
    Art and UI: Melody Chan-Yoeun
    QA Tester: Bryan Matta Villatoro
    Layout Design: Kaitlyn Ngoc Chau Tran
    Theming: Shreya Padisetty
    Networks: Aj Singh
    Emotional Support: Bryan's Cat
Project Sponsor:
    Mari Kimura, MugicMotion
Git Repo:
    github.com/ericxu-25/mugic-pypong
    github.com/ericxu-25/Mugical
"""
        self._draw_menu_screen(title_text, credits_text,
                               background=self._title_background \
                                       or Color.randomBetween(0.6, 0.9, 0.6))

    def _draw_menu_screen(self, *args, **kwargs):
        if self._current_screen in ("credits", "title") and self._title_background is not None:
            self.menu_title_text.color = (247, 177, 155)
        else: self.menu_title_text.color = Color.white
        super()._draw_menu_screen(*args, **kwargs)
        if self._current_screen != "credits":
            for image_sprite in self.credit_images: image_sprite.hide()
        else:
            for image_sprite in self.credit_images: image_sprite.show()

    def _hide_menu_screen(self):
        super()._hide_menu_screen()
        for image_sprite in self.credit_images: image_sprite.hide()

    def start(self):
        # when starting the game, show the title screen
        self._title_screen()
        super().start()

    def _update(self):
        # drawing is expensive, so we only do it every few frames
        if self._frame_count % 20 == 0:
            self._insert_mugic_image()
        # rendering the data output can also slow us down
        if self._frame_count % 10 == 0:
            self._insert_mugic_text()
        self._frame_count += 1
        if self._pause:
            if self._frame_count == 60:
                self._calibrate_mugics()
            return
        # control handling
        self._controls()
        self._increase_ball_speed()

    def _reset(self):
        super()._reset()
        self.pointer_right.centerx = self.striker_right.centerx
        self.pointer_left.centerx = self.striker_left.centerx

# MAIN
def main():
    parser = argparse.ArgumentParser(
            description='Mugic demo project')
    parser.add_argument('port1', type=int, default=4000, nargs="?",
                        help="port of the first mugic device to connect to, default 4000")
    parser.add_argument('port2', type=int, default=4001, nargs="?",
                        help="port of the second mugic device to connect to, default 4001")
    parser.add_argument('--legacy', action='store_true',
                        help="play the version without Mugic controls")
    args = parser.parse_args()

    # disable warnings
    #logging.basicConfig(level=logging.ERROR)
    # define base resolution
    WIDTH, HEIGHT = 1920, 1080
    Window().rescale(WIDTH, HEIGHT)
    Window().resize(0.5)
    pygame.init()
    if args.legacy:
        PONG = PongGame(WIDTH, HEIGHT)
    else:
        PONG = MugicPongGame(WIDTH, HEIGHT, port1=args.port1, port2=args.port2)
    PONG.start()
    pygame.quit()

if __name__ == "__main__":
    main()
