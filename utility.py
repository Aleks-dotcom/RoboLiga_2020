#!/usr/bin/env python3

# Če želite na svojem računalniku namestiti knjižnico python-ev3dev 
# in uprorabljati "code auto-completition":
# pip install python-ev3dev
from ev3dev.ev3 import TouchSensor, Button, LargeMotor, MediumMotor, Sound
# Na EV3 robotu je potrebno namestiti paketa ujson in pycurl:
# sudo apt-get update
# sudo apt-get install python3-pycurl
# sudo apt-get install python3-ujson
import pycurl
import sys
import math
from io import BytesIO
from time import time, sleep
from enum import Enum
from collections import deque

# Funkcije lepote

def drop(motor_left, motor_right, motor_medium):
    motor_medium.run_timed(time_sp=1500, speed_sp=-700)
    sleep(3)
    

def lift(motor_left, motor_right, motor_medium):
    motor_medium.run_timed(time_sp=1500, speed_sp=700)
    sleep(3)

def drive(motor_left, motor_right, motor_medium):
    motor_left.run_timed(time_sp=4000, speed_sp=900)
    motor_right.run_timed(time_sp=4000, speed_sp=900)
    sleep(5)

def reverse(motor_left, motor_right, motor_medium):
    motor_left.run_timed(time_sp=4000, speed_sp=-900)
    motor_right.run_timed(time_sp=4000, speed_sp=-900)
    sleep(5)

def spin(motor_left, motor_right, motor_medium):
    motor_left.run_timed(time_sp=6000, speed_sp=1000)
    motor_right.run_timed(time_sp=6000, speed_sp=-1000)
    sleep(6)

def victory_dance(motor_left, motor_right, motor_medium):
    for i in range(5):
        Sound.speak("PARTY PARTY PARTY PARTY")
        motor_left.run_timed(time_sp=1500, speed_sp=900)
        motor_right.run_timed(time_sp=1500, speed_sp=-900)
        
        for j in range(3):
            motor_medium.run_timed(time_sp=250, speed_sp=900)
            sleep(0.25)
            motor_medium.run_timed(time_sp=250, speed_sp=-900)
            sleep(0.25)
        

        motor_left.run_timed(time_sp=1500, speed_sp=-900)
        motor_right.run_timed(time_sp=1500, speed_sp=900)
        
        for j in range(3):
            motor_medium.run_timed(time_sp=250, speed_sp=900)
            sleep(0.25)
            motor_medium.run_timed(time_sp=250, speed_sp=-900)
            sleep(0.25)


def laugh(motor_left, motor_right, motor_medium):
    Sound.speak("MUHUHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHA lol").wait()
    

def song(motor_left, motor_right, motor_medium):
    Sound.tone([
    (392, 350, 100), (392, 350, 100), (392, 350, 100), (311.1, 250, 100),
    (466.2, 25, 100), (392, 350, 100), (311.1, 250, 100), (466.2, 25, 100),
    (392, 700, 100), (587.32, 350, 100), (587.32, 350, 100),
    (587.32, 350, 100), (622.26, 250, 100), (466.2, 25, 100),
    (369.99, 350, 100), (311.1, 250, 100), (466.2, 25, 100), (392, 700, 100),
    (784, 350, 100), (392, 250, 100), (392, 25, 100), (784, 350, 100),
    (739.98, 250, 100), (698.46, 25, 100), (659.26, 25, 100),
    (622.26, 25, 100), (659.26, 50, 400), (415.3, 25, 200), (554.36, 350, 100),
    (523.25, 250, 100), (493.88, 25, 100), (466.16, 25, 100), (440, 25, 100),
    (466.16, 50, 400), (311.13, 25, 200), (369.99, 350, 100),
    (311.13, 250, 100), (392, 25, 100), (466.16, 350, 100), (392, 250, 100),
    (466.16, 25, 100), (587.32, 700, 100), (784, 350, 100), (392, 250, 100),
    (392, 25, 100), (784, 350, 100), (739.98, 250, 100), (698.46, 25, 100),
    (659.26, 25, 100), (622.26, 25, 100), (659.26, 50, 400), (415.3, 25, 200),
    (554.36, 350, 100), (523.25, 250, 100), (493.88, 25, 100),
    (466.16, 25, 100), (440, 25, 100), (466.16, 50, 400), (311.13, 25, 200),
    (392, 350, 100), (311.13, 250, 100), (466.16, 25, 100),
    (392.00, 300, 150), (311.13, 250, 100), (466.16, 25, 100), (392, 700)
    ]).wait()


def darth_vader(motor_left, motor_right, motor_medium):
    Sound.tone([
    (392, 350, 100), (392, 350, 100), (392, 350, 100), (311.1, 250, 100),
    (466.2, 25, 100), (392, 350, 100), (311.1, 250, 100), (466.2, 25, 100),
    (392, 700, 100), (587.32, 350, 100), (587.32, 350, 100),
    (587.32, 350, 100), (622.26, 250, 100), (466.2, 25, 100),
    (369.99, 350, 100), (311.1, 250, 100), (466.2, 25, 100), (392, 700, 100),
    (784, 350, 100), (392, 250, 100), (392, 25, 100), (784, 350, 100),
    (739.98, 250, 100), (698.46, 25, 100), (659.26, 25, 100),
    (622.26, 25, 100), (659.26, 50, 400), (415.3, 25, 200), (554.36, 350, 100),
    (523.25, 250, 100), (493.88, 25, 100), (466.16, 25, 100), (440, 25, 100),
    (466.16, 50, 400), (311.13, 25, 200), (369.99, 350, 100),
    (311.13, 250, 100), (392, 25, 100), (466.16, 350, 100), (392, 250, 100),
    (466.16, 25, 100), (587.32, 700, 100), (784, 350, 100), (392, 250, 100),
    (392, 25, 100), (784, 350, 100), (739.98, 250, 100), (698.46, 25, 100),
    (659.26, 25, 100), (622.26, 25, 100), (659.26, 50, 400), (415.3, 25, 200),
    (554.36, 350, 100), (523.25, 250, 100), (493.88, 25, 100),
    (466.16, 25, 100), (440, 25, 100), (466.16, 50, 400), (311.13, 25, 200),
    (392, 350, 100), (311.13, 250, 100), (466.16, 25, 100),
    (392.00, 300, 150), (311.13, 250, 100), (466.16, 25, 100), (392, 700)
    ])

    motor_medium.run_timed(time_sp=500, speed_sp=200)
    sleep(1)

    motor_left.run_timed(time_sp=5000, speed_sp=200)
    motor_right.run_timed(time_sp=5000, speed_sp=200)

    for j in range(20):
        motor_medium.run_timed(time_sp=100, speed_sp=500)
        sleep(0.1)
        motor_medium.run_timed(time_sp=100, speed_sp=-500)
        sleep(0.1)

    motor_left.run_timed(time_sp=5000, speed_sp=-200)
    motor_right.run_timed(time_sp=5000, speed_sp=200)

    for j in range(20):
        motor_medium.run_timed(time_sp=100, speed_sp=500)
        sleep(0.1)
        motor_medium.run_timed(time_sp=100, speed_sp=-500)
        sleep(0.1)

    motor_left.run_timed(time_sp=5000, speed_sp=200)
    motor_right.run_timed(time_sp=5000, speed_sp=-200)

    for j in range(20):
        motor_medium.run_timed(time_sp=100, speed_sp=500)
        sleep(0.1)
        motor_medium.run_timed(time_sp=100, speed_sp=-500)
        sleep(0.1)


    sleep(1)

    motor_medium.run_timed(time_sp=5000, speed_sp=-900)

    sleep(7)

    motor_medium.run_timed(time_sp=500, speed_sp=900)


    

utilities = {
    "drive": drive,
    "reverse": reverse,
    "lift": lift,
    "drop": drop,
    "spin": spin,
    "dance": victory_dance,
    "laugh": laugh,
    "song": song,
    "empire": darth_vader
}

if len(sys.argv) <= 1:
    print("No arguments passed: [ drive | reverse | drop | lift | spin ]")
    sys.exit(1)

if len(sys.argv) > 2:
    print("Too many arguments: [ drive | reverse | drop | lift | spin ]")
    sys.exit(1)

function = sys.argv[1]
if function not in utilities:
    print("Wrong argument: [ drive | reverse | drop | lift | spin ]")
    sys.exit(1)


# Priklop motorjev na izhode.
MOTOR_LEFT_PORT = 'outD'
MOTOR_RIGHT_PORT = 'outA'
MOTOR_MEDIUM_PORT = 'outB'


def init_large_motor(port: str) -> LargeMotor:
    """
    Preveri, ali je motor priklopljen na izhod `port`.
    Vrne objekt za motor (LargeMotor).
    """
    motor = LargeMotor(port)
    while not motor.connected:
        print('\nPriklopi motor na izhod ' + port +
              ' in pritisni ter spusti gumb DOL.')
        wait_for_button('down')
        motor = LargeMotor(port)
    return motor


def init_medium_motor(port: str) -> MediumMotor:
    """
    Preveri, ali je motor priklopljen na izhod `port`.
    Vrne objekt za motor (MediumMotor).
    """
    motor = MediumMotor(port)
    while not motor.connected:
        print('\nPriklopi motor na izhod ' + port +
              ' in pritisni ter spusti gumb DOL.')
        wait_for_button('down')
        motor = MediumMotor(port)
    return motor


def init_sensor_touch() -> TouchSensor:
    """
    Preveri, ali je tipalo za dotik priklopljeno na katerikoli vhod. 
    Vrne objekt za tipalo.
    """
    sensor = TouchSensor()
    while not sensor.connected:
        print('\nPriklopi tipalo za dotik in pritisni ter spusti gumb DOL.')
        wait_for_button('down')
        sensor = TouchSensor()
    return sensor


def wait_for_button(btn_name: str = 'down'):
    """
    Čakaj v zanki dokler ni gumb z imenom `btn_name` pritisnjen in nato sproščen.
    """
    while not getattr(btn, btn_name):
        pass
    flag = False
    while getattr(btn, btn_name):
        if not flag:
            flag = True


def robot_die():
    """
    Končaj s programom na robotu. Ustavi motorje.
    """
    print('KONEC')
    motor_left.stop(stop_action='brake')
    motor_right.stop(stop_action='brake')

    Sound.play_song((
        ('D4', 'e'),
        ('C4', 'e'),
        ('A3', 'h')))

    sys.exit(0)




# -----------------------------------------------------------------------------
# NASTAVITVE TIPAL, MOTORJEV
# -----------------------------------------------------------------------------
# Nastavimo tipala in gumbe.
btn = Button()
#sensor_touch = init_sensor_touch()
#print('OK!')

# Nastavimo velika motorja. Priklopljena naj bosta na izhoda A in D.
print('Priprava motorjev ... ', end='')
motor_left = init_large_motor(MOTOR_LEFT_PORT)
motor_right = init_large_motor(MOTOR_RIGHT_PORT)
motor_medium = init_medium_motor(MOTOR_MEDIUM_PORT)


SONG_LYRICS = "Executing function " + function
Sound.speak(SONG_LYRICS).wait()

utilities[function](motor_left, motor_right, motor_medium)
sleep(1)
robot_die()