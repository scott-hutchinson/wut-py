#!/usr/bin/python

import copy, termios, fcntl, locale, random, signal, sys, os
from time import sleep
from astar import astar
# from random import randint


class Actor(object):
    def __init__(self, x, y, data):
        self.x = x
        self.y = y
        self.data = data
        self.path = []
        self.energy = 0
        self.energy_level = 4


class Renderer(object):
    FILL_EMPTY = ' '
    FILL_UPPER = u'\u2580'
    FILL_LOWER = u'\u2584'


    def __init__(self, window_width, window_height):
        term_height, term_width = os.popen('stty size', 'r').read().split()

        self.term_width = int(term_width)
        self.term_height = int(term_height)
        self.window_width = window_width
        self.window_height = window_height
        self.x_offset = (self.term_width / 2) - (self.window_width / 2)
        self.y_offset = (self.term_height / 2) - (self.window_height / 4)
        self._buffer = [[0] * window_width for y in xrange(window_height)]
        self._background = [[0] * window_width for y in xrange(window_height)]


    def draw_object(self, object):
        for pixel in object.data:
            x = object.x + pixel[0]
            y = object.y + pixel[1]
            color = pixel[2]
            self.set_pixel(x, y, color)


    def set_pixel(self, x, y, color):
        if (x >= 0 and x < self.window_width
            and y >= 0 and y < self.window_height
        ):
            self._buffer[y][x] = color


    def erase(self):
        for y in range(self.window_height):
            for x in range(self.window_width):
                self._buffer[y][x] = 0


    def load_background(self):
        self._buffer = [y[:] for y in self._background]


    def randomize(self):
        for y in range(self.window_height):
            for x in range(self.window_width):
                self._background[y][x] = 0
                if random.randint(0, 5) == 0:
                    self._background[y][x] = random.randint(236, 240)


    def refresh(self):
        try:
            for y in range(0, self.window_height, 2):
                line = "\033[%s;%sH" % (
                    str(y/2 + self.y_offset),
                    str(self.x_offset)
                )

                sys.stdout.write(line)

                for x in range(self.window_width):
                    upper = self._buffer[y][x]
                    lower = self._buffer[y+1][x]

                    if upper != 0 and lower == 0:
                        self._set_fg_color(upper);
                        fill = self.FILL_UPPER.encode(encoding)
                    elif upper == 0 and lower != 0:
                        self._set_fg_color(lower);
                        fill = self.FILL_LOWER.encode(encoding)
                    elif upper != 0 and lower != 0:
                        if lower == upper:
                            self._set_bg_color(upper);
                            fill = self.FILL_EMPTY
                        else:
                            self._set_fg_color(lower);
                            self._set_bg_color(upper);
                            fill = self.FILL_LOWER.encode(encoding)
                    else:
                        fill = self.FILL_EMPTY


                    sys.stdout.write(fill)
                    self._disable_color()

            sys.stdout.flush()

        except IOError:
            pass


    def _set_fg_color(self, color):
        sys.stdout.write('\033[38;5;' + str(color) + 'm')


    def _set_bg_color(self, color):
        sys.stdout.write('\033[48;5;' + str(color) + 'm')


    def _disable_color(self):
        sys.stdout.write('\033[0m')


class Input(object):
    # KEY_MOUSE,                  \
    KEY_NONE,                   \
    KEY_ESC,                    \
    KEY_Q,                      \
    KEY_R,                      \
    KEY_H,                      \
    KEY_J,                      \
    KEY_K,                      \
    KEY_L,                      \
    KEY_Y,                      \
    KEY_U,                      \
    KEY_B,                      \
    KEY_N = range(-1, 11)
    # KEY_N = range(-2, 11)


    def __init__(self):
        self.key_map = {
            '\x1b': self.KEY_ESC,
            'q':    self.KEY_Q,
            'r':    self.KEY_R,

            'h':    self.KEY_H,
            'j':    self.KEY_J,
            'k':    self.KEY_K,
            'l':    self.KEY_L,
            'y':    self.KEY_Y,
            'u':    self.KEY_U,
            'b':    self.KEY_B,
            'n':    self.KEY_N,
        }

        self.fd = sys.stdin.fileno()
        self.orig_term = termios.tcgetattr(self.fd)
        self.orig_flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)

        self.mouse = {
            'state':  None,
            'button': None,
            'x':      None,
            'y':      None,
        }

        self.key = None


    def read(self):
        self.mouse = {
            'state':  None,
            'button': None,
            'x':      None,
            'y':      None,
        }

        self.key = None

        mouse_prefix = '\x1b[<'

        try:
            input_buffer = sys.stdin.read(256)

            if input_buffer.startswith(mouse_prefix):
                # self.key = self.KEY_MOUSE

                raw = input_buffer.split(mouse_prefix)
                raw.pop(0)
                raw = raw[0]

                state_raw = raw[-1:]
                if state_raw == 'M':
                    self.mouse['state'] = 1
                elif state_raw == 'm':
                    self.mouse['state'] = 0

                raw = raw[:-1]
                values = raw.split(';')

                self.mouse['button'] = int(values[0])
                self.mouse['x'] = int(values[1])
                self.mouse['y'] = int(values[2])

            else:
                self.key = self._get_key_alias(input_buffer[0])

        except IOError:
            pass


    def enable_raw(self):
        self.raw_term = copy.copy(self.orig_term)
        self.raw_term[0] = self.raw_term[0] & ~(termios.IXON)
        self.raw_term[3] = self.raw_term[3] & ~(termios.ICANON | termios.ECHO)
        termios.tcsetattr(self.fd, termios.TCSANOW, self.raw_term)

        self.raw_flags = self.orig_flags | os.O_NONBLOCK
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.raw_flags)


    def disable_raw(self):
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.orig_term)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.orig_flags)


    def enable_mouse(self):
        sys.stdout.write('\033[?1000h')
        sys.stdout.write('\033[?1006h')


    def disable_mouse(self):
        sys.stdout.write('\033[?1000l')


    def _get_key_alias(self, key):
        if key in self.key_map:
            return self.key_map[key]

        return None


def load_collision_map(background, width, height):
    return [[ 1 if background[y][x] != 0 else 0 for x in range(width) ] for y in range(height)]


def rasterize_line(x0, y0, x1, y1):
    coords = []

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)

    if x0 < x1:
        sx = 1
    else:
        sx = -1

    if y0 < y1:
        sy = 1
    else:
        sy = -1

    if dx > dy:
        err = (dx) / 2
    else:
        err = (-dy) / 2

    while True:
        coords.append((x0, y0))

        if x0 == x1 and y0 == y1:
            break

        e2 = err

        if e2 > -dx:
            err -= dy
            x0 += sx

        if e2 < dy:
            err += dx
            y0 += sy

    return coords

def path_make_relative(path, start_x, start_y):
    relative_path = []

    prev_x = start_x;
    prev_y = start_y;

    for coord in path:
        new_x = coord[0] - prev_x;
        new_y = coord[1] - prev_y;

        prev_x = coord[0];
        prev_y = coord[1];

        relative_path.append((new_x, new_y))
        # sys.stdout.write(str((new_x, new_y)) + "\n")

    return relative_path


def path_reverse_coords(path):
    reversed_coords = []

    for point in path:
        x = point[1]
        y = point[0]

        reversed_coords.append((x, y))

    return reversed_coords


def path_simplify(path, start_x, start_y):
    indices = []

    prev_x = start_x
    prev_y = start_y

    state = 0

    # sys.stdout.write("\n")
    i = 0
    for point in path:
        delta = (point[0] - prev_x, point[1] - prev_y)
        # delta = (point[0], point[1])

        # sys.stdout.write(str(delta) + "\n")

        if (state == 0
            and (delta == (-1, 0) or delta == (1, 0))
        ):
            state = 1
            pop_index = i
        elif (state == 1
              and (delta == (0, -1) or delta == (0, 1))
        ):
            state = 0
            indices.append(pop_index)
            pop_index = -1

        elif (state == 0
              and (delta == (0, -1) or delta == (0, 1))
        ):
            state = 2
            pop_index = i
        elif (state == 2
              and (delta == (-1, 0) or delta == (1, 0))
        ):
            state = 0
            indices.append(pop_index)
            pop_index = -1

        else:
            state = 0


        prev_x = point[0]
        prev_y = point[1]

        i += 1


    # remove nodes in reversed order to prevent misaligned reads/writes
    for index in reversed(indices):
        # sys.stdout.write("REMOVING: " + index + "\n")
        path.pop(index)

    return path


def path_normalize(path, start_x, start_y):
    path.reverse()
    path = path_reverse_coords(path)
    path = path_simplify(path, start_x, start_y)
    path = path_make_relative(path, start_x, start_y)
    return path


def get_path_to(start, end, collision_map, width, height):
    if (end[0] < 0 or end[0] >= width
        or end[1] < 0 or end[1] >= height
    ):
        return []

    if collision_map[end[1]][end[0]] == 1:
        return []

    path = astar(collision_map,
                 width, height,
                 (start[1], start[0]),
                 (end[1], end[0]))

    if path:
        return path_normalize(path, start[0], start[1])

    return []


def in_bounds(point, x, y, width, height):
    return (point[0] >= x
            and point[0] < x + width
            and point[1] >= y
            and point[1] < y + height)


def move_actor(actor, delta, collision_map, width, height):
    if (in_bounds((actor.x + delta[0], actor.y + delta[1]), 0, 0, width, height)
        and collision_map[actor.y + delta[1]][actor.x + delta[0]] != 1
    ):
        actor.x += delta[0]
        actor.y += delta[1]
        return True

    return False


def hide_cursor():
    sys.stdout.write('\033[?25l')

def show_cursor():
    sys.stdout.write('\033[?25h')

def enable_alt_buffer():
    sys.stdout.write('\033[?1049h')

def disable_alt_buffer():
    sys.stdout.write('\033[?1049l')

def clear_screen():
    sys.stdout.write('\033[2J')


def signal_handler(signal, frame):
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)

    input = Input()

    hide_cursor()
    enable_alt_buffer()
    clear_screen()
    input.enable_raw()
    input.enable_mouse()

    renderer = Renderer(80, 60)
    renderer.randomize()

    collision_map = load_collision_map(renderer._background,
                                       renderer.window_width,
                                       renderer.window_height)

    player = Actor(0, 1, [
        (0, -1, 220),
        (0, 0, 220),
    ])

    enemy = Actor(30, 30, [
        (0, -1, 200),
        (0, 0, 200),
    ])
    enemy.energy_level = 10

    enemy.path = get_path_to((enemy.x, enemy.y),
                             (player.x, player.y),
                             collision_map,
                             renderer.window_width,
                             renderer.window_height)

    dirty = True

    try:
        while 1:
            if dirty:
                dirty = False
                # renderer.erase()
                renderer.load_background()
                renderer.draw_object(player)
                renderer.draw_object(enemy)
                renderer.refresh()

            input.read()

            if (input.key == input.KEY_Q
                or (input.mouse['button'] == 1 and input.mouse['state'] == 0)
            ):
                sys.exit(0)


            elif input.key == input.KEY_R or input.key == input:
                player.path = []
                renderer.randomize()
                collision_map = load_collision_map(renderer._background,
                                                   renderer.window_width,
                                                   renderer.window_height)
                player.x = 0
                player.y = 1
                enemy.x = random.randint(renderer.window_width/2,
                                         renderer.window_width-1)
                enemy.y = random.randint(renderer.window_height/2,
                                         renderer.window_height-1)
                enemy.path = get_path_to((enemy.x, enemy.y),
                                         (player.x, player.y),
                                         collision_map,
                                         renderer.window_width,
                                         renderer.window_height)
                dirty = True


            elif input.key == input.KEY_H:
                player.path = [(-1, 0)]
            elif input.key == input.KEY_L:
                player.path = [(1, 0)]
            elif input.key == input.KEY_J:
                player.path = [(0, 1)]
            elif input.key == input.KEY_K:
                player.path = [(0, -1)]
            elif input.key == input.KEY_Y:
                player.path = [(-1, -1)]
            elif input.key == input.KEY_U:
                player.path = [(1, -1)]
            elif input.key == input.KEY_B:
                player.path = [(-1, 1)]
            elif input.key == input.KEY_N:
                player.path = [(1, 1)]


            elif input.mouse['state'] == 0:
                click_x = None
                click_y = None
                if input.mouse['button'] == 0:
                    click_x = input.mouse['x'] - renderer.x_offset
                    click_y = (input.mouse['y'] - renderer.y_offset) * 2
                elif input.mouse['button'] == 16:
                    click_x = input.mouse['x'] - renderer.x_offset
                    click_y = (input.mouse['y'] - renderer.y_offset) * 2 + 1

                if click_x != None and click_y != None:
                    player.path = get_path_to((player.x, player.y),
                                              (click_x, click_y),
                                              collision_map,
                                              renderer.window_width,
                                              renderer.window_height)



            if player.energy == player.energy_level:
                player.energy = 0

                if player.path:
                    point = player.path.pop(0)
                    if (move_actor(player,
                                   point,
                                   collision_map,
                                   renderer.window_width,
                                   renderer.window_height)
                    ):
                        dirty = True
                        enemy.path = get_path_to((enemy.x, enemy.y),
                                                 (player.x, player.y),
                                                 collision_map,
                                                 renderer.window_width,
                                                 renderer.window_height)

            if enemy.energy == enemy.energy_level:
                enemy.energy = 0

                if enemy.path:
                    point = enemy.path.pop(0)
                    enemy.x += point[0]
                    enemy.y += point[1]
                    dirty = True


            sleep(0.01)

            player.energy += 1
            enemy.energy += 1


    finally:
        input.disable_mouse()
        input.disable_raw()
        disable_alt_buffer()
        show_cursor()


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, '')
    encoding = locale.getpreferredencoding()
    main()
