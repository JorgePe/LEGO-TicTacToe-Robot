# versions:
#   v3.1:   -
#   v3.0:   detects free cells in player storage column before returning
#             player used bricks back to initial arrangement
#           when dropping a magnet move to next line instead of line above
#             (more stable and all lines work equally)
#   v2.3:    reverse tiles over magnets instead of 2 plates
#             so adjust some z values
#           random choose who starts
#           code refactoring
#   v2.2:   faster and also reduce time lowering magnet by
#             splitting action in 2 movements:
#             - first move down fast to target angle just above brick
#             - then move down until stall 
#           use pointer to also show who is next
#           use LED
#   v2.1:   add motor to point to winner (suggested by my #1)
#   v2:     user input without IDE
#
# notes:
#           had to replace Y motor, Technic XL for Education Large
#             beause Y would increasingly move slow for positive directions

# game flow:
#   - start and finish each move at rest_pos
#   - pick_at ( (line, column))
#   - drop_at( (line, column) )

from pybricks.hubs import TechnicHub
from pybricks.tools import wait
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Stop, Direction, Button, Color
from urandom import randint

hub = TechnicHub()

color_run = Color.GREEN
color_player = Color.ORANGE
color_robot = Color.CYAN

# Y motors: Technic Counter clocwise / Education: default
#y_motor = Motor(Port.A, positive_direction=Direction.COUNTERCLOCKWISE )
y_motor = Motor(Port.A)
                                # ang>0 move towards user (increase line)
x_motor = Motor(Port.B)         # ang>0 move right
z_motor = Motor(Port.C)         # ang>0 move down
ptr_motor = Motor(Port.D)       # ang>0 point right (robot column)
                                # fisically limited with bricks to ~ -90..+90

z_limit = 618                   # distance to baseplate
z_brick = 390                   # distance to brick v2 (magnet + reverse tile)
#z_brick = 356                  # distance to brick v1 (magnet + 2 plates)
z_grid  = 482                   # distance to grid wall


# some timings
delay = 100                     # short delay after action completion
pick_delay = 250                # delay to expect the magnets to sticks
blink_times = [500, 500]        # on/off timings for blink effect (ms)
completion_time = 5000          # delay at game end before cleaning the board
parallel_delay = 10             # delay while waiting for 2 motors to complete
button_delay = 10               # delay while waiting for the button press

# check battery level
# lower than 8.3 strange things start to happen
# with 9V/6A PSU I get  9173

print('Batt: ', hub.battery.voltage())

# y_motor.control.limits( 1500, 2000, 400 )
print("Y Limits: ", y_motor.control.limits()) # max speed, accel, torque
# (1500, 2000, 233) XL
# (1000, 2000, 560) LE

print("Y Tolerances: ", y_motor.control.target_tolerances())  # speed, target
# (50, 20) XL
# (50, 11) LE
print("Y Max Voltage: ", y_motor.settings())
# (9000,) XL/LE

# decrease speed tolerance
# y_motor.control.target_tolerances(25, 20)
# decrease max voltage (does not allow increase)
# y_motor.settings(8900)

# check max speed of each motor
y_speed = y_motor.control.limits()[0]
x_speed = x_motor.control.limits()[0]
z_speed = z_motor.control.limits()[0]
ptr_speed = ptr_motor.control.limits()[0]

print('Max speeds: ', y_speed, x_speed, z_speed, ptr_speed)

# maximum duty cycles when using run_until_stalled()
z_duty = 17     # 14 18     # seems to deviate a lot with different battery levels
x_duty = 87     # 83
y_duty = 80     # 80
ptr_duty = 20

# pointer positions
ptr_player = -87            # player
ptr_robot = - ptr_player    # robot
ptr_center = 0              # neither one
ptr_half_player = -44
ptr_half_robot = - ptr_half_player

ptr_positions = [ptr_center,
    ptr_player,
    ptr_robot,
    ptr_half_player,
    ptr_half_robot
]

rest_pos = (0,2)            # rest position of the carriage (line, column)

# define 3x3 game grid
grid = [
    [' ', ' ', ' '],
    [' ', ' ', ' '],
    [' ', ' ', ' ']                
]


player_symbol = 'X'             # symbols used in the grid
robot_symbol =  'O'

player_column = 0               # columns used for player/robot storage
robot_column = 4



def initialize_game():  
    hub.light.on(color_run)

    # move magnet to topmost position and sets as zero
    z_motor.run_until_stalled(-z_speed, then=Stop.COAST_SMART, duty_limit=z_duty)
    z_motor.reset_angle(0)
    wait(delay)

    # move carriage to leftmost position and sets as zero
    x_motor.run_until_stalled(-x_speed, then=Stop.COAST_SMART, duty_limit=x_duty)
    x_motor.reset_angle(0)
    wait(delay)

    # move carriage to minimal y position (far from user) and sets as zero
    y_motor.run_until_stalled(-y_speed, then=Stop.COAST_SMART, duty_limit=y_duty)
    y_motor.reset_angle(0)
    wait(delay)

    # move pointer to leftmost position and sets as player position
    ptr_motor.run_until_stalled(-ptr_speed, then=Stop.COAST, duty_limit=ptr_duty)
    ptr_motor.reset_angle(ptr_player)
    wait(delay)

    # move pointer to middle position
    ptr_motor.run_target(ptr_speed, 0, then=Stop.HOLD)

    # moves carriage to rest position - where all moves should start and complete
    move_to(rest_pos)


def calc_x(column):
#    return(70 + column * 629)      # XL
    return(120 + column * 632)       # LE
                                    # values vary a lot with voltage
                                    # better use a 9V PSU
                                    # also with motors

def calc_y(line):
#    return(370 + line * 1040)      # XL
    return(375 + line * 1048)       # LE

def move_to(pos):
    # move carriage to position
    # pos[0] = line
    # pos[1] = column
    
    x_motor.run_target(x_speed, calc_x(pos[1]), then = Stop.COAST_SMART, wait=False)
    y_motor.run_target(y_speed, calc_y(pos[0]), then = Stop.COAST_SMART, wait=False)
    while not x_motor.done() or not y_motor.done():
        wait(parallel_delay)


def pick_at(pos):
    # move carriage to position and then pick brick
    # pos[0] = line
    # pos[1] = column

    move_to(pos)
    # move down to brick height
    z_motor.run_target(z_speed, z_brick, then=Stop.HOLD)
    wait(pick_delay)
    # move up to topmost
    z_motor.run_target(-z_speed, 0, then=Stop.HOLD)


def drop_at(pos):
    # move carriage to position and then drop brick
    # pos[0] = line
    # pos[1] = column

    move_to(pos)

    # move magnet down to brick height
    z_motor.run_target(z_speed, z_brick, then=Stop.HOLD)
    wait(delay)

    # move over y to a point between current line and the next line
    y_motor.run_target(y_speed, (calc_y(pos[0]) + calc_y(pos[0] + 1) ) / 2, then = Stop.HOLD)
    wait(delay)

    # move magnet up
    z_motor.run_target(-z_speed, 0, then=Stop.HOLD)


def check_victory():
    # checks for victory condition

    # check lines
    for l in range(0,3):
        if grid[l][0] == grid[l][1] \
                and grid[l][0] == grid[l][2] \
                and grid[l][0] != ' ':
            return True

    # columns
    for c in range(0,3):        
        if grid[0][c] == grid[1][c] \
                and grid[0][c] == grid[2][c] \
                and grid[0][c] != ' ':
            return(True)
    
    # diags
    if grid[0][0] == grid[1][1] \
            and grid[0][0] == grid[2][2] \
            and grid[0][0] != ' ':
        return(True)

    if grid[2][0] == grid[1][1] \
            and grid[2][0] == grid[0][2] \
            and grid[2][0] != ' ':
        return(True)

    return False


def free_position():
    # checks if there is at least one free position in the grid
    for l in grid:
        if ' ' in l:
            return True
    return False


def show_result(result):
    # makes a short dance over the top of a column according to
    # result:
    # - player_symbol
    # - robot_symbol
    # '' (or anything else) means a draw

    line = 0
    if (result == player_symbol) or (result == robot_symbol):
        # victory
        # move carriage and pointer and blink LED

        if result == player_symbol:
            column = player_column
            direction = +1  # dance to right
            color = color_player
            position = ptr_player
        else:
            column = robot_column
            direction = -1  # dance to left
            color = color_robot
            position = ptr_robot

        hub.light.blink(color, blink_times)
        for i in range(0,3):
            move_to( (line, column + direction))
            point_to(position)
            move_to( (line, column) )
            point_to(ptr_center)

    else:
        # draw
        # just move the pointer
        for i in range(0,3):
            point_to(ptr_half_player)
            wait(delay)
            point_to(ptr_half_robot)
            wait(delay)
        point_to(ptr_center)

    hub.light.on(color_run)


def check_user_input():
    # waits for player to move its brick and press button
    # then moves carriage over all free cells in the grid
    # until it finds the player new brick

    # Disable the stop button.
    hub.system.set_stop_button(None)

    point_to(ptr_player)
    hub.light.blink(color_player, blink_times)

    while not hub.buttons.pressed():
        wait(button_delay)

    wait(delay)                 # might need more
    point_to(ptr_center)
    hub.light.on(color_run)

    # Enable the stop button again.
    hub.system.set_stop_button(Button.CENTER)

    # check new brick
    for l in range(0,3):
        for c in range(0,3):
            # only check free cells
            if grid[l][c] == " ":
                move_to( (l+1, c+1) )
                # first move down fast to just above expected brick
                z_motor.run_target(z_speed, z_brick - 50, then=Stop.COAST_SMART)
                wait(delay)
                
                # then move down until stalled
                height = z_motor.run_until_stalled(z_speed, then=Stop.COAST, duty_limit=z_duty-4)
                wait(delay)

                if (z_brick -50) < height < (z_brick +50):
                    # there is a brick here
                    grid[l][c] = player_symbol
                    print(f"Player: ({l},{c})")

                    # leave it there by moving carriage
                    # to between current line and next line
                    y_motor.run_target(y_speed, (calc_y(l+2) + calc_y(l+1) ) / 2, then = Stop.HOLD)
                    wait(delay)
                    # moves magnet up
                    z_motor.run_target(-z_speed, 0, then=Stop.HOLD)
                    wait(delay)
                    move_to(rest_pos)
                    return
                else:
                    # there isn't a brick here
                    # moves magnet up
                    z_motor.run_target(-z_speed, 0, then=Stop.HOLD)
                    wait(delay)

    # not supposed to get here
    print("Oops!")
    move_to_rest()


def point_to(position):
    # move pointer to position
    if position in ptr_positions:
        ptr_motor.run_target(ptr_speed, position, then=Stop.COAST)


def robot_move():
    # executes robot move

    point_to(ptr_robot)
    hub.light.blink(color_robot, blink_times)    
    while True:
        line = randint(0,2)
        column = randint(0,2)
        if grid[line][column] == ' ':
            grid[line][column] = robot_symbol
            break
    print(f"Robot: ({line},{column})")

    # convert grid coords to board coords
    line = line + 1
    column = column + 1

    pick_at( (robot_line, robot_column))
    drop_at( (line, column))
    point_to(ptr_center)


def scan_player_storage():
    # scans player storage column to know the content of each cell
    # returns a list with all cells

    player_storage = [' '] * 5

    for l in range(0,5):
        move_to( (l,player_column) )

        # first move down fast to just above expected brick
        z_motor.run_target(z_speed, z_brick - 50, then=Stop.COAST_SMART)
        wait(delay)
        
        # then move down until stalled
        height = z_motor.run_until_stalled(z_speed, then=Stop.COAST, duty_limit=z_duty-4)
        wait(delay)

        if (z_brick -50) < height < (z_brick +50):
            # there is a brick here
            player_storage[l] = player_symbol

            # leave it there by moving carriage
            # to between current line and next line
            y_motor.run_target(y_speed, (calc_y(l+1) + calc_y(l) ) / 2 , then = Stop.HOLD)
            wait(delay)
            
        else:
            # there isn't a brick here
            player_storage[l] = ' '

        # moves magnet up
        z_motor.run_target(-z_speed, 0, then=Stop.HOLD)
        wait(delay)

    return(player_storage)


def clean_board():
    # pick all used bricks and move them to player/robot columns

    # check wich cells are free for player bricks
    player_storage = scan_player_storage()

    # no need to scan robot storage column because bricks were
    # taken in order by the robot

    player_line = 0
    robot_line = 0
    for l in range(0,3):
        for c in range(0,3):       
            if grid[l][c] != ' ':
                pick_at( (l+1, c+1) )
                if grid[l][c] == player_symbol:
                    # find next cell available
                    while player_storage[player_line] != ' ':
                        player_line += 1
                    drop_at( (player_line, player_column))
                    player_line += 1
                else:
                    # for the robot bricks, just drom them in sequence
                    drop_at( (robot_line, robot_column))
                    robot_line += 1

    move_to(rest_pos)


#### main ####

initialize_game()
player_line = 0      # next move use brick at this line
robot_line = 0

# decide who starts
if randint(0,1) == 0:
    player_turn = True
    print("Player starts")
else:
    player_turn = False
    print("Robot starts")

while True:

    # is it still possible to play?
    if not free_position():
        # no - declare draw and finish
        print("No one wins!")
        show_result('')
        break
    
    # yes it is, keep playing until someone wins
    if player_turn == True:
        check_user_input()
        if check_victory():
            print("Player wins!")
            show_result(player_symbol)
            break
        player_line += 1
    else:
        robot_move()
        if check_victory():
            print("Robot wins!")
            show_result(robot_symbol)
            break
        robot_line += 1

    player_turn = not player_turn

    hub.light.on(color_run)
    move_to(rest_pos) 

   
wait(completion_time)
clean_board()

# game over
