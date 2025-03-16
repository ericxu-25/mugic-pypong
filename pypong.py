from mugic_pygame_helpers import *
from mugic_helper import *
from mugic import *

# Basic Controls (keyboard)
# - up, left, down, right, rotleft, rotright
# p1 = wasdqe OR zx
# p2 = arrows<> OR ijkluo
# Basic Controls (Mugic)
# - point towards ceiling/floor to control up/down
# - twist right/left to change rotation
# - tilt fully down/up to continue to rotate
# - shake the Mugic to bring it back to the center


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
            spring_force = abs((distance) * self.springiness * 60.0/self.game.fps) / 4
            # apply dampening
            spring_force -= abs(self.impact_velocity) * 60.0/self.game.fps * (1-self.springiness)
            spring_force = max(0, spring_force)
            self._impact_accel = spring_force * sign(distance)
        # apply the spring changes
        self.impact_velocity += self._impact_accel / self._substeps

    def update(self):
        _x_to_ball = self.centerx - self.game.ball.centerx
        for _ in range(self._substeps):
            self.move(0, self.velocity * 60.0/self.game.fps / self._substeps)
            self._apply_impact_spring()
            # ensure we don't glitch past the ball
            if sign(_x_to_ball) == sign(self.centerx - self.game.ball.centerx):
                self.move(self.impact_velocity * 60.0/self.game.fps / self._substeps, 0)
                _x_to_ball = self.centerx - self.game.ball.centerx
            else:
                print("glitched!")
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
        self.rotation += self.rot_velocity * 60.0/self.game.fps
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

    def _CPUMovement(self):
        ball = self.game.ball
        db = abs(self._x - ball._x)
        if db > self.game._width//2:
            self._rotateTowardsNormal()
            if db > self.game._width * 0.7:
                self._CPU_RANDOM = random.randint(1, 30)
            elif self._CPU_RANDOM % 4 == 0:
                self._moveTowardsNormal()
            return
        self._moveTowardsPoint(ball.centery + (self._CPU_RANDOM - 15) // 3)
        if self._CPU_RANDOM % 4 != 0:
            self._rotateTowardsBall()

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
                new_text.moveTo(5, 5 + (text_size + 3) * i)
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
        self._CPU_RANDOM = random.randint(1, 30)
        self.debugDraw(self._draw_striker_bounce, None)

    def _draw_striker_bounce(self, display, ball, **bounce_data):
        # select the middle display tab
        display.refresh()
        tab = display.getTab(1)
        text = self._draw_striker_bounce_text
        # resize striker image to fit
        fit_scale = tab._height / self._height / 2
        # draw the striker onto the tab
        center = (tab.centerx * self.scale,  (tab.centery + text[1].rect.y) * self.scale)
        center_position = (center[0] - self.rect.width//2 * fit_scale * self.scale,
                           center[1] - self.rect.height//2 * fit_scale * self.scale)
        # using smoothscale_by instead (slower, but cleaner than scale_by)
        tab.screen.blit(
                pygame.transform.smoothscale_by(self.image, fit_scale * self.scale),
                center_position)
        if ball == None: return # stop if no data
        # draw the ball onto the tab
        scale = self.game._scale
        ball_offset = bounce_data['offset'] * scale * fit_scale
        ball_position = (ball_offset +
                         (center[0] - ball.rect.width//2 * fit_scale * self.scale,
                          center[1] - ball.rect.height//2 * fit_scale * self.scale))
        tab.screen.blit(
                pygame.transform.scale_by(ball.image, fit_scale * self.scale),
                ball_position)
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
        bounce_data['normal'] *= vector_scale * 10
        bounce_data['impact'] *= vector_scale
        bounce_data['reflect'] *= vector_scale
        bounce_data['final'] *= vector_scale
        bounce_data['rotate'] *= vector_scale
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

class Ball(GameSprite):
    def __init__(self, game=None):
        super().__init__(game)
        self.spin = 0
        self.velocity = pygame.math.Vector2(1, 0)

    def setup(self, speed, color, r, mass):
        self.speed_value = speed
        self.speed_increase = 0
        self.min_speed = 10 * (speed/10.0)
        self.speed = self.min_speed
        self.mass = (mass / 10.0)
        self.rolling_friction = (
                0.1 *
                (speed/10.0) *
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
        self.min_speed = 10 * ((self.speed_value + self.speed_increase)/10.0)
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
            self.velocity.x = self.velocity.x * 2
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
        if striker.rot_velocity > 0: striker.rot_velocity -= rot_hit_speed
        else: striker.rot_velocity += rot_hit_speed
        final_vector += striker_rot_hit_vector
        return final_vector

    def _bounceOnStriker(self, striker):
        # calculate information about the collision
        striker_normal = self._normalizedStrikerImpactAngle(striker)
        direction = (-1 if self.velocity.x < 0 else 1)
        # first, move ball back until not clipping Striker
        self._unclipFromStriker(striker, striker_normal)
        final_vector = pygame.math.Vector2(0, 0)
        offset_vector = pygame.math.Vector2(
                self._cx - striker._cx,
                self._cy - striker._cy)
        # reflect off the striker
        reflect_vector = self.velocity.copy().reflect(striker_normal)
        reflect_vector.scale_to_length(self.speed * striker.elasticity)
        final_vector = reflect_vector.copy()
        # apply modifications based on the striker's attributes
        # modification 1: striker power
        striker_hit_vector = striker_normal.copy()
        striker_hit_vector.scale_to_length(striker.power/self.mass)
        final_vector += striker_hit_vector
        # modification 2: striker relative movement (spin)
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
            new_offset.scale_to_length(striker.power / self.mass)
            final_vector = (rotate_hit_vector +
                            striker_hit_vector +
                            new_offset)
        # modification 5: striker horizontal impact
        striker_impact = striker.impact_velocity
        if sign(striker_impact) == sign(final_vector.x):
            striker_impact = abs(striker_impact) * striker_normal * striker.elasticity
            final_vector += striker_impact / 2
        else: striker_impact = pygame.math.Vector2(0,0)
        # modification 6: critical hit!
        # increase power by 10% if the ball hit the striker corner
        # which can be detected with towards_striker
        critical = pygame.math.Vector2(0, 0)
        if towards_striker:
            final_vector *= 1.1
            critical = final_vector
        # apply final calculated vector
        if final_vector.magnitude() == 0:
            self.velocity = striker_hit_vector + reflect_vector
        else:
            self.velocity = final_vector
        self.speed = self.velocity.magnitude()
        # apply a log_scale to the spin (keeps it around 3)
        self.spin = math.log(abs(self.spin)+1) * 3 * sign(self.spin)
        # apply an extra layer of friction onto the striker
        striker._apply_friction()
        # apply the equal and opposite force to the striker
        striker.impact_velocity -= final_vector.x
        striker.velocity -= final_vector.y
        # put the bounce onto the display
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
        if self.spin > 0: self.spin -= spin_friction
        else: self.spin += spin_friction

    def roll(self):
        self.speed -= self.rolling_friction/self._substeps
        if self.speed < self.min_speed:
            self.speed = self.min_speed
        fps_ratio = 60.0/self.game.fps
        self.velocity.scale_to_length(self.speed * fps_ratio)
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
    ball_speed = 5
    ball_color = Color.white
    ball_size = 10
    ball_mass = 15

    def __init__(self, w, h = None):
        adjusted_width = w * 2 // 3
        side_width = (w - adjusted_width) / 2.0
        super().__init__(adjusted_width, h, padding=(20, 20, 10, 10))
        self.base_background.fill(Color.black)
        self.name = "pong"
        self.fps = 60
        # increase ball speed by 1 every 5 seconds
        self.SPEED_INCREASE_TIME = 3
        self._initialize_screens(side_width)
        self._initialize_sprites()
        self._initialize_controls()
        self._window.addGame(self, (side_width, 0))
        self._window.name = "Mugical Pong"

    def _initialize_screens(self, w):
        self.debug_screen_left = DisplayScreen(w, self.height)
        self.debug_screen_left.splitTabs(3)
        # left side chooses blueish colors
        for tab in self.debug_screen_left.tabs:
            tab.base_background.fill(Color.randomBetween(0.7, 0.8, 1, 0.8))
        self.debug_screen_right = DisplayScreen(w, self.height)
        self.debug_screen_right.splitTabs(3)
        # right side chooses purplish colors
        for tab in self.debug_screen_right.tabs:
            tab.base_background.fill(Color.randomBetween(0.8, 0.9, 1, 0.8))
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

        # setup menu sprites
        self.menu_title_text = TextSprite(self)
        self.menu_title_text.layer = 4
        self._add_sprite(self.menu_title_text)
        self.menu_title_text.hide()
        self.menu_title_text.setFontSize(80)
        self.menu_title_text.setFormatString("{}")
        self.menu_title_text.bold = True
        self.menu_subtitle_text = TextSprite(self)
        self.menu_subtitle_text.layer = 4
        self._add_sprite(self.menu_subtitle_text)
        self.menu_subtitle_text.hide()
        self.menu_subtitle_text.setFontSize(30)
        self.menu_subtitle_text.setFormatString("{}")
        self.menu_subtitle_text.italic = True
        self.menu_background_sprite = Sprite(self)
        self.menu_background_sprite.layer = 3
        self._add_sprite(self.menu_background_sprite)
        self.menu_background_sprite.moveTo(0, 0)
        menu_background = pygame.Surface(self.screen_rect.size)
        menu_background.fill(Color.black)
        self.menu_background_sprite.setImage(menu_background)
        self.menu_background_sprite.hide()

    def _update_menu_text_position(self):
        middle = self._height // 4
        center = self._width // 2
        self.menu_title_text.moveCenterTo(center, middle)
        self.menu_subtitle_text.moveCenterTo(center, middle)
        self.menu_subtitle_text.y = (self.menu_title_text.y
                                     + self.menu_title_text.height + 10)

    def _draw_menu_screen(self, title_text, subtitle_text, background=False):
        self.menu_title_text.setText(title_text)
        self.menu_subtitle_text.setText(subtitle_text)
        self.menu_title_text.show()
        self.menu_subtitle_text.show()
        self._update_menu_text_position()
        if background:
            self.menu_background_sprite.show()
        if type(background) is tuple:
            menu_background = pygame.Surface(self.screen_rect.size)
            menu_background.fill(background)
            self.menu_background_sprite.setImage(menu_background)
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
        center_left = self._width // 4
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
        if self.p1_rt:
            self.striker_right._rotateRight()
        if self.p1_lt:
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
        if self.p2_rt:
            self.striker_left._rotateRight()
        if self.p2_lt:
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
    ball_speed = 4
    striker_power = 9
    ball_mass = 20
    striker_grip = 10
    striker_size = (40, 130)
    ball_size = 12

    def __init__(self, w, h):
        super().__init__(w, h)
        self.mugic_player_1 = MugicDevice(port=4000)
        self.mugic_player_2 = MugicDevice(port=4001)
        self._init_mugic_variables()
        self._init_mugic_image()
        self._init_mugic_text()
        self._current_screen = None

    def _initialize_sprites(self):
        super()._initialize_sprites()
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

    def _init_mugic_variables(self):
        self.p1_jolt = False
        self.p1_y = 0
        self.p1_x = 0
        self.p1_rotx = 0
        self.p1_roty = 0
        self.p1_rotz = 0
        self.p1_moving = 0
        self.p2_jolt = False
        self.p2_y = 0
        self.p2_x = 0
        self.p2_rotx = 0
        self.p2_roty = 0
        self.p2_rotz = 0
        self.p2_moving = 0
        self._frame_count = 0

    def _update_controller_info(self):
        self.striker_right.controller = (
                "CPU" if self.p1_CPU else "Keyboard" if not self.mugic_player_1.connected()
                else str(self.mugic_player_1))
        self.striker_left.controller = (
                "CPU" if self.p2_CPU else "Keyboard" if not self.mugic_player_2.connected()
                else str(self.mugic_player_1))

    def _handle_mugic_controls(self):
        if not self.p1_CPU and self.mugic_player_1.connected():
            m1 = self.mugic_player_1
            m1_data = m1.next()
            # disable keyboard
            self.p1_rt = False
            self.p1_lt = False
            self.p1_up = False
            self.p1_dn = False
            # control position with the pointing angle
            m1_point = m1.pointingAt(m1_data)
            # fit the pointing values (-1 to 1) to screen position
            targetY = self._height//2 - int(m1_point[2] * self._height//2)
            targetX = self._width//2 - int(m1_point[1] * self._width//2)
            self.p1_y = targetY
            self.p1_x = m1.thrustAccel()
            if abs(self.p1_x) < 2: self.p1_x = 0
            else: self.p1_x *= 2
            self.p1_rotx, self.p1_roty, self.p1_rotz = IMU.euler(m1_data) or (0, 0, 0)
            self.p1_moving = m1.moving(datagram=m1_data)
            # control rotation with the tilt
            self.p1_rt = m1._facing(axis=2, direction=120, threshold=20, datagram=m1_data)
            self.p1_lt = m1._facing(axis=2, direction=-120, threshold=20, datagram=m1_data)
            # detect jolt
            if m1.jolted(20):
                self.p1_jolt = True

        if not self.p2_CPU and self.mugic_player_2.connected():
            m2 = self.mugic_player_2
            m2_data = m2.next()
            # disable keyboard
            self.p2_rt = False
            self.p2_lt = False
            self.p2_up = False
            self.p2_dn = False
            # control position with the pointing angle
            m2_point = m2.pointingAt(m2_data)
            targetY = self._height//2 - int(m2_point[2] * self._height//2)
            targetX = self._width//2 - int(m2_point[1] * self._width//2)
            self.p2_y = targetY
            self.p2_x = m2.thrustAccel()
            if abs(self.p2_x) < 2: self.p2_x = 0
            else: self.p2_x *= 2
            self.p2_rotx, self.p2_roty, self.p2_rotz = IMU.euler(m2_data) or (0, 0, 0)
            self.p2_moving = m2.moving(datagram=m2_data)
            # control rotation with the tilt
            self.p2_rt = m2._facing(axis=2, direction=120, threshold=20, datagram=m2_data)
            self.p2_lt = m2._facing(axis=2, direction=-120, threshold=20, datagram=m2_data)
            # detect jolt
            if m2.jolted(20):
                self.p2_jolt = True

    def _controls(self):
        # Mugic player 1 controls
        if self.mugic_player_1.connected() and not self.p1_CPU:
            self.pointer_right.show()
            self.striker_right.impact_velocity += self.p1_x/4
            for _ in range(2):
                self.striker_right._moveTowardsPoint(self.p1_y)
            self.striker_right._moveTowardsPoint(self.p1_y)
            self.pointer_right.centery = self.p1_y
            self.pointer_right.rotateTo(self.striker_right.rotation)
            if not (self.p1_rt or self.p1_lt):
                self.striker_right._rotateTowardsAngle(-self.p1_rotz)
            else:
                if self.p1_rt:
                    self.striker_right._rotateRight()
                if self.p1_lt:
                    self.striker_right._rotateLeft()
            self.p1_jolt = not (self.striker_right._moveTowardsBall())
        else:
            self.pointer_right.hide()
            self._handle_p1_controls()
        # Mugic player 2
        if self.mugic_player_2.connected() and not self.p2_CPU:
            self.pointer_left.show()
            self.striker_left.impact_velocity += self.p2_x/4
            for _ in range(2):
                self.striker_left._moveTowardsPoint(self.p2_y)
            self.pointer_left.centery = self.p2_y
            self.pointer_left.rotateTo(self.striker_left.rotation)
            if not (self.p2_rt or self.p2_lt):
                self.striker_left._rotateTowardsAngle(-self.p2_rotz)
            else:
                if self.p2_rt:
                    self.striker_left._rotateRight()
                if self.p2_lt:
                    self.striker_left._rotateLeft()
            self.p2_jolt = not (self.striker_left._moveTowardsBall())
        else:
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
        p1_tab1.base_background.fill(Color.black)
        p2_tab1 = self.debug_screen_right.getTab(0)
        p2_tab1.base_background.fill(Color.black)
        p1_tab1._refresh_background()
        p2_tab1._refresh_background()

    def _insert_mugic_image(self):
        p1_tab1 = self.debug_screen_right.getTab(0)
        mugic_p1_image = self.p1_mugic_display.getImage(p1_tab1.abs_width, p1_tab1.abs_height)
        p1_tab1.background.fill(Color.black)
        p1_tab1.background.blit(mugic_p1_image, (0, 0))
        p2_tab1 = self.debug_screen_left.getTab(0)
        mugic_p2_image = self.p2_mugic_display.getImage(p2_tab1.abs_width, p2_tab1.abs_height)
        p2_tab1.background.fill(Color.black)
        p2_tab1.background.blit(mugic_p2_image, (0, 0))
        p1_tab1.refresh()
        p2_tab1.refresh()

    def _init_mugic_text(self):
        instruction_text = "Instructions: H \n P to pause \n R to reset"
        self.p1_mugic_text = self.debug_screen_right.writeNewText("NO CONNECTION", tab=2)
        self.p2_mugic_text = self.debug_screen_left.writeNewText(instruction_text, tab=2)
        p1_txt, p2_txt = self.p1_mugic_text, self.p2_mugic_text
        p1_txt.move(5, 2)
        p2_txt.move(5, 2)
        p1_txt.setFontSize(20)
        p2_txt.setFontSize(30)
        p1_txt.setFontType(MONOSPACE)
        p2_txt.setFontType(MONOSPACE)

    def _insert_mugic_text(self):
        p1_txt, p2_txt = self.p1_mugic_text, self.p2_mugic_text
        if p1_txt._fontsize > 16: # to override default font size
            p1_txt.setFontSize(16)
            p2_txt.setFontSize(16)
        if self.mugic_player_1.connected():
            p1_txt.setText(self.p1_mugic_display.text)
        if self.mugic_player_2.connected():
            p2_txt.setText(self.p2_mugic_display.text)
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
            return
        super()._tick()

    def _title_screen(self):
        self.pause()
        self._current_screen = "title"
        title_text = "MUGICAL PONG"
        subtitle_text = "press P to start, H for instructions, C for credits"
        self._draw_menu_screen(title_text, subtitle_text, background=Color.random())

    def _instruction_screen(self):
        self.pause()
        self._current_screen = "instruction"
        title_text = "INSTRUCTIONS"
        instruction_text = \
"""Keyboard Controls:
* right side - arrow keys,. or ijkluo
* left side - wasdqe

Mugic Controls:
* spacebar to calibrate; 1 or 2 to activate CPU
* point up/down to move striker
* twist right/left to rotate striker

- Press P to continue, R to reset
- Press M to return to Menu
"""
        self._draw_menu_screen(title_text, instruction_text, background=Color.black)

    def _credits_screen(self):
        self.pause()
        self._current_screen = "credits"
        title_text = "CREDITS"
        credits_text = \
"""
Team Mugical (2024-2025)
UCI Informatics Senior Capstone Group
Members:
    Eric Xu, Melody Chan-Yoeun,
    Bryan Matta Villatoro,
    Shreya Padisetty, Aj Singh

Project Sponsor:
    Mari Kimura, MugicMotion
"""
        self._draw_menu_screen(title_text, credits_text, background=Color.randomBetween(0.2, 0.4, 0.6))

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
        self.pointer_right.x = self.striker_right.x
        self.pointer_left.x = self.striker_left.x

# MAIN
def main():
    # disable warnings
    logging.basicConfig(level=logging.ERROR)
    # define base resolution
    WIDTH, HEIGHT = 1920, 1080
    Window().rescale(WIDTH, HEIGHT)
    Window().resize(0.8)
    pygame.init()
    #PONG = PongGame(WIDTH, HEIGHT)
    PONG = MugicPongGame(WIDTH, HEIGHT)
    PONG.start()
    pygame.quit()

if __name__ == "__main__":
    print("running pypong!")
    main()
