from mugic_pygame_helpers import *
# import mugic_helper

# Basic controls (keyboard)
# - up, left, down, right, rotleft, rotright
# p1 = wasdqe OR wasdzx or wasdcv
# p2 = arrows<> OR ijkluo


# PONG implementation
class Striker(GameSprite):
    def __init__(self, game):
        super().__init__(game)
        self.velocity = 0
        self.rot_velocity = 0

    def setup(self, color, wh, friction, speed, accel, rot_speed, rot_accel, power, grip, elasticity):
        self.speed = 15 * (speed/10.0)
        self.accel = 5 * (accel/10.0)
        self.rot_speed = 15 * (rot_speed/10.0)
        self.rot_accel = 1.5 * (rot_accel/10.0)
        self.color = color
        self.friction = 0.8 * (10.0/(10 + friction/10))
        self.elasticity = 1.0 - 0.6 / (elasticity/10.0 + 0.6)
        self.power = 8 * (power / 10.0)
        self.grip = 0.8 - 0.8/(grip/10.0 + 0.8)
        striker = pygame.Surface(wh, flags=pygame.SRCALPHA)
        striker.fill(self.color)
        self.setImage(striker)

    def _apply_friction(self):
        self.velocity *= self.friction
        self.rot_velocity *= 1 - ((1 - self.friction) / 2)
        if abs(self.velocity) < 1: self.velocity = 0
        if abs(self.rot_velocity) < 0.5: self.rot_velocity = 0

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
            text_size = 16
            self._draw_striker_bounce_text = list()
            text = self._draw_striker_bounce_text
            for i in range(2):
                new_text = display.writeNewText(
                    "...", tab=tab)
                text.append(new_text)
                new_text.setFontSize(text_size)
                new_text.moveTo(5, 5 + (text_size + 3) * i)
            text[0].setText("BOUNCE INFORMATION")
            text[1].setFormatString("ball speed: {:.2f}")
            text[1].setText(0)
        else:
            text = self._draw_striker_bounce_text
            text[1].setText(0)
            text[1].setColor(Color.white)

    def _reset(self):
        self.debugFunction(self._init_draw_striker_bounce)
        self.rotateTo(0)
        self.rot_velocity = 0
        self.velocity = 0
        self.debugDraw(self._draw_striker_bounce, None)

    def _draw_striker_bounce(self, display, ball, **bounce_data):
        # select the middle display tab
        display.refresh()
        tab = display.getTab(1)
        text = self._draw_striker_bounce_text
        # resize striker image to fit
        fit_scale = tab._height / self._height / 1.5
        fit_scale = fit_scale * 8 // 4 / 2
        # draw the striker onto the tab
        center = (tab.centerx, tab.centery + text[1].rect.y)
        center_position = (center[0] - self.rect.width//2 * fit_scale,
                           center[1] - self.rect.height//2 * fit_scale)
        # could use smoothscale_by instead (slower, but cleaner)
        tab.screen.blit(
                pygame.transform.scale_by(self.image, fit_scale),
                center_position)
        if ball == None: return # stop if no data
        # draw the ball onto the tab
        scale = self.game._scale
        ball_offset = bounce_data['offset'] * scale * fit_scale
        ball_position = (ball_offset +
                         (center[0] - ball.rect.width//2 * fit_scale,
                          center[1] - ball.rect.height//2 * fit_scale))
        tab.screen.blit(
                pygame.transform.scale_by(ball.image, fit_scale),
                ball_position)
        # write the data onto the tab
        text[1].setText(bounce_data['speed'])
        if bounce_data['critical'].magnitude() > 0:
            text[1].setColor(Color.red)
        elif bounce_data['rotate'].magnitude() > 0:
            if text[1].color != Color.green:
                text[1].setColor(Color.green)
        elif text[1].color != Color.white:
            text[1].setColor(Color.white)
        # draw the different vectors
        vector_scale = 3
        bounce_data['normal'] *= vector_scale * 10
        bounce_data['reflect'] *= vector_scale
        bounce_data['final'] *= vector_scale
        bounce_data['rotate'] *= vector_scale
        ball_center = ball_offset + center
        critical = bounce_data['critical'].magnitude() > 0
        pygame.draw.line(tab.screen, Color.magenta,
                         center, bounce_data['normal'] + center )
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

        return


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
        self.speed_value = speed
        self.speed_increase = 0
        self.min_speed = 10 * (speed/10.0)
        self.speed = self.min_speed
        self.mass = (mass / 10.0)
        self.rolling_friction = (
                0.1 *
                (speed/10.0) *
                (1 - 1.0 / (self.mass + 1)))
        self._substeps = 10 # use substepping for greater simulation accuracy
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

    def _unclipFromStriker(self, striker):
        backstep = -self.velocity
        backstep.normalize_ip()
        limit = 3 * self._substeps
        while pygame.sprite.collide_mask(self, striker):
            self.move(backstep.x * 2, backstep.y)
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
        for i in range(self._substeps):
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
        # first, move ball back until not clipping Striker
        self._unclipFromStriker(striker)
        final_vector = pygame.math.Vector2(0, 0)
        offset_vector = pygame.math.Vector2(
                self._cx - striker._cx,
                self._cy - striker._cy)
        # then calculate information about the collision
        striker_normal = self._normalizedStrikerImpactAngle(striker)
        direction = (-1 if self.velocity.x < 0 else 1)
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
        spin_mod = striker.velocity * striker.grip / self.mass * direction
        self.spin += (abs(striker_normal.x)) * spin_mod
        self.spin *= striker.elasticity
        # modification 3: striker rotation
        self.spin += striker.rot_velocity / 4
        rotate_hit_vector = self._rotateHitOnStriker(striker)
        final_vector += rotate_hit_vector
        # stuck-proofing
        # if final vector not pointing away from striker...
        # critical! - use offset_vector to correct (probably hit edge)
        critical = pygame.math.Vector2(0, 0)
        towards_striker = (offset_vector.x > 0) != (final_vector.x > 0)
        if towards_striker:
            new_offset = offset_vector.copy()
            new_offset.scale_to_length(striker.power * 1.2/self.mass)
            critical = new_offset
            final_vector = (rotate_hit_vector +
                            striker_hit_vector +
                            new_offset)
        # apply final calculated vector
        if final_vector.magnitude() == 0:
            self.velocity = striker_hit_vector + reflect_vector
        else:
            self.velocity = final_vector
        self.speed = self.velocity.magnitude()
        # put the bounce onto the display
        bounce_data = {"normal": striker_normal,
                       "offset": offset_vector,
                       "reflect": reflect_vector,
                       "final": self.velocity,
                       "rotate": rotate_hit_vector,
                       "critical": critical,
                       "speed": self.speed}
        striker.displayStrikerBounce(self, bounce_data)

    def _spin_effect(self):
        if abs(self.spin) < self.rolling_friction:
            self.spin = 0
            return
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
        for i in range(self._substeps):
            self.roll()
            self.bounceOnStrikers()
        self.bounceOnWalls()
        self.scoreOnPlayers()

class PongGame(Game):
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
        self.debug_screen_right = DisplayScreen(w, self.height)
        self.debug_screen_right.splitTabs(3)
        self._window.addScreen(self.debug_screen_left, (0, 0))
        self._window.addScreen(self.debug_screen_right, (w + self.width, 0))

    def _initialize_sprites(self):
        # initialize strikers
        striker_size = (30, 100)
        striker_speed = 10
        striker_accel = 10
        striker_rot_speed = 10
        striker_rot_accel = 10
        striker_color = Color.white
        striker_friction = 8
        striker_power = 12
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
        ball_speed = 5
        ball_color = Color.white
        ball_size = 8
        ball_mass = 15
        ball_parameters = (ball_speed,
                           ball_color,
                           ball_size,
                           ball_mass)
        self.ball = Ball(self).setup(*ball_parameters)
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
        # self._add_sprite(goal_sprite1, goal_sprite2)

        # setup score text
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

        # setup menu text
        self.menu_title_text = TextSprite(self)
        self._add_sprite(self.menu_title_text)
        self.menu_title_text.hide()
        self.menu_title_text.setFontSize(100)
        self.menu_title_text.bold = True

    def _update_score(self):
        self.s1_score_text.setText(self.s1_score)
        self.s2_score_text.setText(self.s2_score)

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
        self.menu_title_text.moveCenterTo(center, middle)
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

    def _handle_key(self, event):
        key = Key(event)
        if key in (pygame.K_UP, pygame.K_i):
            self.p1_up = key.down
        elif event.key in (pygame.K_DOWN, pygame.K_k):
            self.p1_dn = key.down
        elif event.key in (pygame.K_RIGHT, pygame.K_l):
            self.p1_rt = key.down
        elif event.key in (pygame.K_LEFT, pygame.K_j):
            self.p1_lt = key.down
        elif event.key in (pygame.K_COMMA, pygame.K_u):
            self.p1_lt = key.down
        elif event.key in (pygame.K_PERIOD, pygame.K_o):
            self.p1_rt = key.down
        elif event.key in (pygame.K_w,):
            self.p2_up = key.down
        elif event.key in (pygame.K_s,):
            self.p2_dn = key.down
        elif event.key in (pygame.K_a,):
            self.p2_lt = key.down
        elif event.key in (pygame.K_d,):
            self.p2_rt = key.down
        elif event.key in (pygame.K_q, pygame.K_z, pygame.K_c):
            self.p2_lt = key.down
        elif event.key in (pygame.K_e, pygame.K_x, pygame.K_v):
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
        self.ball._increase_speed(1/self.fps/self.SPEED_INCREASE_TIME)

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
    PONG = PongGame(WIDTH, HEIGHT)
    PONG.start()
    pygame.quit()

if __name__ == "__main__":
    print("running pypong!")
    main()
