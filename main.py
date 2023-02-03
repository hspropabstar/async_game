import time
import curses
import asyncio
import random
import sys
import os
from itertools import cycle
from numpy import repeat
from physics import update_speed
from obstacles import Obstacle, show_obstacles
from explosion import explode

sys.path.append(os.getcwd())

from curses_tools import draw_frame, read_controls, get_frame_size
from game_scenario import PHRASES, get_garbage_delay_tics

TIC_TIMEOUT = 0.1
OFFSET_FROM_BORDER = 2
GLOBAL_VARS_YEAR = 1957
GLOBAL_VARS_SPEED = 15
DEV_MODE = 1
SYMBOL = '+*.:'
NUMBER_OF_STARS = 80
GAME_OVER_FRAME = (
    os.path.join(os.getcwd(), 'game_over.txt')
)

coroutines_array = []
obstacles = []
obstacles_in_last_collision = []

async def fire(canvas,
               start_row,
               start_column,
               rows_speed=-0.3,
               columns_speed=0):

    row, column = start_row, start_column

    canvas.addstr(round(row), round(column), '*')
    await asyncio.sleep(0)

    canvas.addstr(round(row), round(column), 'O')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), ' ')

    row += rows_speed
    column += columns_speed

    symbol = '-' if columns_speed else '|'

    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - 1, columns - 1

    curses.beep()

    while 0 < row < max_row and 0 < column < max_column:
        check_collision = [obs.has_collision(round(row), round(column)) for obs in obstacles]
        if obstacles and any(check_collision):
            obstacle_to_explode = obstacles[check_collision.index(True)]
            obstacles_in_last_collision.append(obstacle_to_explode)
            await explode(canvas, obstacle_to_explode.row, obstacle_to_explode.column)
            return
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


async def blink(canvas, row, column, star_sleep, symbol='*'):
    while True:
        canvas.addstr(row, column, symbol, curses.A_DIM)
        await sleep(20)
        await sleep(star_sleep)

        canvas.addstr(row, column, symbol)
        await sleep(3)

        canvas.addstr(row, column, symbol, curses.A_BOLD)
        await sleep(5)

        canvas.addstr(row, column, symbol)
        await sleep(3)


async def sleep(count_sleep=1):
    for _ in range(count_sleep):
        await asyncio.sleep(0)


def read_animations(animation_dir, filter):
    animations = []
    for anim in os.listdir(animation_dir):
        if filter and anim.startswith(filter):
            with open(os.path.join(animation_dir, anim), 'r') as f:
                animations.append(f.read())

    return animations if len(animations) > 1 else animations[-1]


def check_border(
    text, start_row, start_column, canvas):
    rows, columns = get_frame_size(text)

    y, x = canvas.getmaxyx()
    max_row, max_column = y - 1, x - 1

    start_row = max(1, start_row)
    start_row = min(max_row - rows, start_row)

    start_column = max(0, start_column)
    start_column = min(max_column - columns, start_column)
        

    return start_column, start_row


async def animate_spaceship(canvas, spaceship_animations, start_row, start_column, row_speed, column_speed):
    animations = repeat(spaceship_animations, 2)
    for animation in cycle(animations):
        row_direction, column_direction, space = read_controls(canvas)

        row_speed, column_speed = update_speed(
                                      row_speed,
                                      column_speed,
                                      row_direction,
                                      column_direction
                                  )

        start_row, start_column = start_row + row_speed, start_column + column_speed

        start_column, start_row = check_border(
                animation, start_row,
                start_column, canvas
            )

        check_collision = [obs.has_collision(round(start_row), round(start_column)) for obs in obstacles]
        if obstacles and any(check_collision):
            await explode(canvas, start_row, start_column)
            coroutines_array.append(show_gameover(
                canvas,
                read_animations(os.path.join(os.getcwd(), 'animation'), 'game')
                )
            )
            global GLOBAL_VARS_EXIT
            GLOBAL_VARS_EXIT = True
            return

        if GLOBAL_VARS_YEAR >= 2020 and space:
            coroutines_array.append(
                fire(canvas,
                     start_row,
                     start_column + 2,
                     rows_speed=-0.3,
                     columns_speed=0
                )
        )
  
        draw_frame(
            canvas, start_row, start_column,
            animation, negative=False,
        )
      
        await sleep()
          
        draw_frame(
            canvas, start_row, start_column,
            animation, negative=True,
        )


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    rows_number, columns_number = canvas.getmaxyx()

    column = max(column, 0)
    column = min(column, columns_number - 1)

    row = 0

    y_frame_size, x_frame_size = get_frame_size(garbage_frame)

    obstacle = Obstacle(row, column, y_frame_size, x_frame_size)
    obstacles.append(obstacle)

    try:
        while row < rows_number:
            if obstacle in obstacles_in_last_collision:
                obstacles_in_last_collision.remove(obstacle)
                return
            draw_frame(canvas, row, column, garbage_frame)
            await sleep()
            draw_frame(canvas, row, column, garbage_frame, negative=True)
            obstacle.row, obstacle.column = row, column
            canvas.border()
            row += speed
    finally:
        obstacles.remove(obstacle)


async def fill_orbit_with_garbage(canvas, garbage_animations):
    y, x = canvas.getmaxyx()
    max_row, max_column = y - 1, x - 1

    while True:
        garbage_time_out = get_garbage_delay_tics(GLOBAL_VARS_YEAR)
        garbage_frame = garbage_animations[random.randint(0, len(garbage_animations) - 1)]
        rows_frame, columns_frame = get_frame_size(garbage_frame)
        column = random.randint(OFFSET_FROM_BORDER + columns_frame, max_column - columns_frame)
        garbage_coroutine = fly_garbage(canvas, column, garbage_frame)
        coroutines_array.append(garbage_coroutine)
        if not garbage_time_out:
            await sleep(30)
        else:
            await sleep(garbage_time_out)


async def show_gameover(canvas, frame):
    window_height, window_width = canvas.getmaxyx()
    window_height, window_width = window_height - 1, window_width - 1

    message_size_y, message_size_x = get_frame_size(frame)
    message_pos_y = round(window_height / 2) - round(message_size_y / 2)
    message_pos_x = round(window_width / 2) - round(message_size_x / 2)
    while True:
        draw_frame(canvas, message_pos_y, message_pos_x, frame)
        await sleep(30)
        exit()


async def print_info(canvas):
    phrase = PHRASES.get(GLOBAL_VARS_YEAR)
    while True:
        phrase = PHRASES.get(GLOBAL_VARS_YEAR) or phrase
        canvas.addstr(1, 1, '{}: {}'.format(GLOBAL_VARS_YEAR, phrase))
        canvas.refresh()
        await sleep(1)


def draw(canvas):
    y, x = canvas.getmaxyx()
    y, x = y - 1, x - 1

    global OFFSET_FROM_BORDER, NUMBER_OF_STARS, SYMBOL

    canvas.nodelay(True)
    curses.curs_set(False)
    coordinates = []
  
    garbage_animations = read_animations(os.path.join(os.getcwd(), 'garbage_animation'), 'trash')
    spaceship_animations = read_animations(os.path.join(os.getcwd(), 'animation'), 'rocket')
   
    while len(coordinates) < NUMBER_OF_STARS:
        cur_coordinates = (
            random.randint(OFFSET_FROM_BORDER, y - OFFSET_FROM_BORDER),
            random.randint(OFFSET_FROM_BORDER, x - OFFSET_FROM_BORDER),
        )
        if cur_coordinates not in coordinates:
            coordinates.append(cur_coordinates)


    coroutines_array.extend(
        [blink(canvas, *coordinates[i], i, random.choice(list(SYMBOL)))
        for i in range(NUMBER_OF_STARS)]
    )
    coroutines_array.extend([
        animate_spaceship(canvas, spaceship_animations, y // 2, x // 2, 0, 0),
        fill_orbit_with_garbage(canvas, garbage_animations),
        print_info(canvas),
        ]
    )

    if DEV_MODE:
        coroutines_array.append(
            show_obstacles(canvas, obstacles)
        )

    game_ticks = 0
    while True:
        curses.curs_set(False)
        for coroutine in coroutines_array.copy():
            try:
                coroutine.send(None)
            except StopIteration:
                coroutines_array.remove(coroutine)

        game_ticks += 1
        if game_ticks % GLOBAL_VARS_SPEED == 0:
            global GLOBAL_VARS_YEAR
            GLOBAL_VARS_YEAR += 1
        canvas.border()  
        canvas.refresh()
        time.sleep(TIC_TIMEOUT)


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(draw)
