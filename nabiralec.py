#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" 
Program za vodenje robota EV3 po seznamu tock na poligonu.
[Robo liga FRI 2020: Cebelnjak]
"""

__author__ = "Laboratory for adaptive systems and parallel processing"
__copyright__ = "Copyright 2020, UL FRI - LASPP"
__credits__ = ["Laboratory for adaptive systems and parallel processing"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Nejc Ilc"
__email__ = "nejc.ilc@fri.uni-lj.si"
__status__ = "Active"


# Če želite na svojem računalniku namestiti knjižnico python-ev3dev 
# in uprorabljati "code auto-completition":
# pip install python-ev3dev
from ev3dev.ev3 import TouchSensor, Button, LargeMotor, MediumMotor, Sound
# Na EV3 robotu je potrebno namestiti paketa ujson in pycurl:
# sudo apt-get update
# sudo apt-get install python3-pycurl
# sudo apt-get install python3-ujson
import pycurl
import ujson
import sys
import math
from io import BytesIO
from time import time, sleep
from enum import Enum
from collections import deque

# Nastavitev najpomembnjših parametrov
# ID robota. Spremenite, da ustreza številki označbe, ki je določena vaši ekipi.
ROBOT_ID = 25
# Naslov IP igralnega strežnika.
SERVER_IP = "192.168.2.3/game/"
# Datoteka na igralnem strežniku s podatki o tekmi.

kletka = ""
if len(sys.argv) > 2:
    GAME_ID = sys.argv[1]
    kletka = str(sys.argv[2])
    print('kletka: {}\ngame_id: {}'.format(GAME_ID,kletka))
else:
	print('You didnt provid a game id and kletka...\n[Usage] python3 nabiralec.py <game_id> <kletka>')
	sys.exit(0) 

# Priklop motorjev na izhode.
MOTOR_LEFT_PORT = 'outD'
MOTOR_RIGHT_PORT = 'outA'
MOTOR_MEDIUM_PORT = 'outB'

# Najvišja dovoljena hitrost motorjev (teoretično je to 1000).
SPEED_MAX = 900
# Najvišja dovoljena nazivna hitrost motorjev pri vožnji naravnost.
# Naj bo manjša kot SPEED_MAX, da ima robot še možnost zavijati.
SPEED_BASE_MAX = 800
SPEED_REVERSE_MAX = 700

# Parametri za PID
# Obračanje na mestu in zavijanje med vožnjo naravnost

#1.5 - 0.3 - 0.1 so bili zanimivi za rikverc
PID_TURN_KP = 1.6
PID_TURN_KI = .15
PID_TURN_KD = .4
PID_TURN_INT_MAX = 100
#ŠPAGET - smo dodali testing ločene pid vrednosti za rikverc only(s kocko težje obračat)
PID_TURN_REVERSE_KP = 1.5
PID_TURN_REVERSE_KI = .15
PID_TURN_REVERSE_KD = .25
#not really
# Nazivna hitrost pri vožnji naravnost.
PID_STRAIGHT_KP = .5
PID_STRAIGHT_KI = .35
PID_STRAIGHT_KD = 0.007
PID_STRAIGHT_INT_MAX = 50

# Dolžina FIFO vrste za hranjenje meritev (oddaljenost in kot do cilja).
HIST_QUEUE_LENGTH = 3

# Razdalje - tolerance
# Dovoljena napaka v oddaljenosti do cilja [mm].
DIST_EPS = 170
# Dovoljena napaka pri obračanju [stopinje].
DIR_EPS = 10
# Bližina cilja [mm].
DIST_NEAR = 250
# Koliko sekund je robot lahko stanju vožnje naravnost v bližini cilja
# (oddaljen manj kot DIST_NEAR), preden sprožimo varnostni mehanizem
# in ga damo v stanje obračanja na mestu.
TIMER_NEAR_TARGET = 5.5


cage_lifted = True

SONG_LYRICS = " "
hives_in_control = 0
class State(Enum):
    """
    Stanja robota.
    """

    def __str__(self):
        return str(self.name)
    IDLE = 0
    TURN = 1
    DRIVE_STRAIGHT = 2
    LOAD_NEXT_TARGET = 3
    CLOSE = 4
    OPEN = 5
    FETCH_2ND_HIVE = 6


class Connection():
    """
    Objekt za vzpostavljanje povezave s strežnikom.
    """

    def __init__(self, url: str):
        """
        Inicializacija nove povezave.

        Argumenti:
        url: pot do datoteke na strežniku (URL)
        """
        self._url = url
        self._buffer = BytesIO()
        self._pycurlObj = pycurl.Curl()
        self._pycurlObj.setopt(self._pycurlObj.URL, self._url)
        self._pycurlObj.setopt(self._pycurlObj.CONNECTTIMEOUT, 10)
        self._pycurlObj.setopt(self._pycurlObj.WRITEDATA, self._buffer)

    def request(self, debug=False):
        """
        Nalaganje podatkov s strežnika.
        """
        # Počistimo pomnilnik za shranjevanje sporočila
        self._buffer.seek(0, 0)
        self._buffer.truncate()
        # Pošljemo zahtevek na strežnik
        self._pycurlObj.perform()
        # Dekodiramo sporočilo
        msg = self._buffer.getvalue().decode()
        # Izluščimo podatke iz JSON
        try:
            return ujson.loads(msg)
        except ValueError as err:
            if debug:
                print('Napaka pri razclenjevanju datoteke JSON: ' + str(err))
                print('Sporocilo streznika:')
                print(msg)
            return -1

    def test_delay(self, num_iters: int = 10):
        """
        Merjenje zakasnitve pri pridobivanju podatkov o tekmi s strežnika. 
        Zgolj informativno.
        """
        sum_time = 0
        for _ in range(num_iters):
            start_time = time()
            if self.request(True) == -1:
                robot_die()
            elapsed_time = time() - start_time
            sum_time += elapsed_time
        return sum_time / num_iters


class PID():
    """
    Implementacija algoritma za regulacijo PID.
    Nekaj virov za razjasnitev osnovnega načela delovanja:
        - https://en.wikipedia.org/wiki/PID_controller
        - https://www.csimn.com/CSI_pages/PIDforDummies.html
        - https://blog.opticontrols.com/archives/344
        - https://www.youtube.com/watch?v=d2AWIA6j0NU
    """

    def __init__(
            self,
            setpoint: float,
            Kp: float,
            Ki: float = None,
            Kd: float = None,
            integral_limit: float = None):
        """
        Ustvarimo nov regulator PID s pripadajočimi parametri.

        Argumenti:
        setpoint: ciljna vrednost regulirane spremenljivke
        Kp: ojačitev proporcionalnega dela regulatorja.
            Visoke vrednosti pomenijo hitrejši odziv sistema,
            vendar previsoke vrednosti povzročijo oscilacije in nestabilnost.
        Ki: ojačitev integralnega člena regulatorja.
            Izniči napako v ustaljenem stanju. Zmanjša odzivnost.
        Kd: ojačitev odvoda napake.
            Zmanjša čas umirjanja in poveča odzivnost.
        integral_limit: najvišja vrednost integrala
        """
        self._setpoint = setpoint
        self._Kp = Kp
        self._Ki = Ki
        self._Kd = Kd
        self._integral_limit = integral_limit
        self._error = None
        self._time = None
        self._integral = None
        self._value = None

    def reset(
            self,
            setpoint: float = None,
            Kp: float = None,
            Ki: float = None,
            Kd: float = None,
            integral_limit: float = None):
        """
        Ponastavitev regulatorja. 
        Lahko mu tudi spremenimo katero od vrednosti parametrov.
        Napaka, integral napake in čas se ponastavijo.
        """
        if setpoint is not None:
            self._setpoint = setpoint
        if Kp is not None:
            self._Kp = Kp
        if Ki is not None:
            self._Ki = Ki
        if Kd is not None:
            self._Kd = Kd
        if integral_limit is not None:
            self._integral_limit = integral_limit
        self._error = None
        self._time = None
        self._integral = None
        self._value = None

    def update(self, measurement: float) -> float:
        """
        Izračunamo vrednost izhoda regulatorja (regulirna veličina) 
        glede na izmerjeno vrednost regulirane veličine (measurement) 
        in ciljno vrednost (setpoint).

        Argumenti:
        measurement: s tipali izmerjena vrednost regulirane veličine

        Izhodna vrednost:
        regulirna veličina, s katero želimo popraviti delovanje sistema 
        (regulirano veličino), da bo dosegel ciljno vrednost
        """
        if self._value is None:
            # Na začetku še nimamo zgodovine meritev, zato inicializiramo
            # integral in vrnemo samo proporcionalni člen.
            self._value = measurement
            # Zapomnimo si začetni čas.
            self._time = time()
            # Ponastavimo integral napake.
            self._integral = 0
            # Napaka = ciljna vrednost - izmerjena vrednost regulirane veličine.
            self._error = self._setpoint - measurement
            return self._Kp * self._error
        else:
            # Sprememba časa
            time_now = time()
            delta_time = time_now - self._time
            self._time = time_now
            # Izmerjena vrednost regulirane veličine.
            self._value = measurement
            # Napaka = ciljna vrednost - izmerjena vrednost regulirane veličine.
            error = self._setpoint - self._value

            # Proporcionalni del
            P = self._Kp * error

            # Integralni in odvodni člen sta opcijska.
            if self._Ki is None:
                I = 0
            else:
                # Integral se poveča za (sprememba napake) / (sprememba časa).
                self._integral += error * delta_time
                # Ojačitev integralnega dela.
                I = self._Ki * self._integral
                if self._integral_limit is not None:
                    # Omejimo integralni del.
                    I = max(min(I, self._integral_limit),
                            (-1)*(self._integral_limit))

            if self._Kd is None:
                D = 0
            else:
                # Odvod napake z ojačitvijo.
                D = self._Kd * (error - self._error) / delta_time
            # Posodobimo napako.
            self._error = error
            # Vrnemo regulirno veličino, sestavljeno iz proporcionalnega,
            # integralnega in odvodnega člena.
            return P + I + D


class Point():
    """
    Točka na poligonu.
    """
    #sandi solution za infinite loop pri comparisonu v nasem endgame manevru -cene
    def __init__(self, position, name = 'SATAN'):
        self.x = position['x']
        self.y = position['y']
        self.name = name

    def __str__(self):
        return '('+str(self.x)+', '+str(self.y)+')'


class Node():
    # TODO: a <update_node()> dela pravilno? A se nam splaca popraulat tocka <self.point> ni na sredini noda ampak v spodnem kotu
    def __init__(self, position):
        self.point = Point(position)
        self.free = True

        self.h = 0
        self.g = 0
        self.f = 0

    def __str__(self):
        return "pos: {}, free: {}".format(str(self.point), str(self.free))

    def update_node(self):
        global game_state
        if not game_state or game_state == -1:
            return
        
        dist = 1000
        for id, hive in game_state['objects']['hives'].items():
            if hive["type"] == "HIVE_DISEASED":

                hp = Point(hive["position"])
                dist = get_distance(self.point, hp)

        self.free = dist > 200



class Chunk():
    def __init__(self, size_x, size_y, offset_x, offset_y, node_amount):
        self.node_sqrt = math.floor(math.sqrt(node_amount))
        self.node_size = int(size_x / self.node_sqrt)
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.size_x  = size_x
        self.size_y = size_y

        # so we can calculate what is within perticular chunk
        self.boundary_min_x = self.size_x * self.offset_x
        self.boundary_max_x = self.boundary_min_x + self.size_x
        self.boundary_min_y =  self.size_y * self.offset_y
        self.boundary_max_y = self.boundary_min_y + self.size_y
        #center of the chunk, if ever needed ;)
        #self.center = Point({'x':(self.boundary_max_x - self.boundary_min_x )/2,'y':(self.boundary_max_y- self.boundary_min_y)/2})
        self.nodes = [None] * self.node_sqrt


        for x in range(self.node_sqrt):
            self.nodes[x] = [None] * self.node_sqrt
            for y in range(self.node_sqrt):
                self.nodes[x][y] = Node({"x": offset_x * size_x + self.node_size*x, "y": offset_y * size_y + self.node_size*y})

    def __str__(self):
        res = ""
        for x in range(self.node_sqrt):
            for y in range(self.node_sqrt):
                res += "\t id:" + str(self.offset_x) + str(self.offset_y) + str(self.nodes[x][y]) + "\n"
        
        return res


    def diseased_in_chunk(self):
        global game_state
        in_chunk = False
        x_range = (self.boundary_min_x,self.boundary_max_x)
        y_range = (self.boundary_min_y,self.boundary_max_y)

        if not game_state or game_state == -1:
            return 
        
        for id, hive in game_state['objects']['hives'].items():
            if hive["type"] == "HIVE_DISEASED":

                hp = Point(hive["position"])

                if hp.x - 60 > x_range[1]:
                    in_chunk = False
                elif hp.x + 60 < x_range[0]:
                    in_chunk = False
                elif hp.y + 60 < y_range[0]:
                    in_chunk = False
                elif hp.y - 60 > y_range[1]:
                    in_chunk = False
                else:
                    in_chunk = True

        return in_chunk

        
    def map_chunk(self):

        update_chunk()
        final_map = self.nodes

        for x in range(self.node_sqrt):
            for y in range(self.node_sqrt):
                if self.nodes[x][y].free:
                    final_map[x][y] = '0'
                else: 
                    final_map[x][y] = '1'

        return final_map


    def update_chunk(self):
        for x in range(self.node_sqrt):
            for y in range(self.node_sqrt):
                self.nodes[x][y].update_node()


class Grid():
    # grid_size => lines on x and y axis    
    def __init__(self, grid_size, node_amount):
        self.x_amount = grid_size["x"]
        self.y_amount = grid_size["y"]

        self.x_size = int(3500 / self.x_amount)
        self.y_size = int(2000 / self.y_amount)

        #self.total_chunks = grid_size["x"] * grid_size["y"]
        self.chunks = [None] * self.x_amount

        for x in range(self.x_amount):
            self.chunks[x] = [None] * self.y_amount
            for y in range(self.y_amount):
                self.chunks[x][y] = Chunk(self.x_size, self.y_size, x, y, node_amount)

    
    def __str__(self):
        res = ""
        for x in range(self.x_amount):
            for y in range(self.y_amount):
                res += str(self.chunks[x][y]) + "\n"

        return res

    def get_chunks(self):
        res = []
        for x in range(self.x_amount):
            for y in range(self.y_amount):
                res.append(self.chunks[x][y])
        
        return res

def get_angle(p1, a1, p2) -> float:
    """
    Izračunaj kot, za katerega se mora zavrteti robot, da bo obrnjen proti točki p2.
    Robot se nahaja v točki p1 in ima smer (kot) a1.
    """
    a = math.degrees(math.atan2(p2.y-p1.y, p2.x - p1.x))
    a_rel = a - a1
    if abs(a_rel) > 180:
        if a_rel > 0:
            a_rel = a_rel - 360
        else:
            a_rel = a_rel + 360

    return a_rel


def get_distance(p1: Point, p2: Point) -> float:
    """
    Evklidska razdalja med dvema točkama na poligonu.
    """
    return math.sqrt((p2.x-p1.x)**2 + (p2.y-p1.y)**2)


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


def beep(duration=1000, freq=440):
    """
    Potrobi s frekvenco `freq` za čas `duration`. Klic ne blokira.
    """
    Sound.tone(freq, duration)
    # Če želimo, da blokira, dokler se pisk ne konča.
    #Sound.tone(freq, duration).wait()


def robot_die():
    """
    Končaj s programom na robotu. Ustavi motorje.
    """
    print('KONEC')
    motor_left.stop(stop_action='brake')
    motor_right.stop(stop_action='brake')
   
    drop_cage(motor_medium)

    

    """
    Sound.play_song((
        ('E4', 's'),
        ('E4', 'e'),
        ('E4', 'e'),
        ('C4', 's'),
        ('E4', 'e'),
        ('G4', 'q'),
        ('G3', 'e')))
    """
    
    sys.exit(0)



#-------- FUNKCIJE -------------
"""
def use_double_kibla(hives, curent_hive, HIVE_IGNORE_LIST):
    if curent_hive:
        if len(hives) > 1:
            return 1
    else: 
        return 0    
"""
def set_near_values():
    global reverse
    global DIST_NEAR
    global DIR_ESP
    if reverse:
        DIR_ESP = 20
        DIST_NEAR = 3000
    else:
        DIR_ESP = 10
        DIST_NEAR = 250


def get_next_healthy(rp, hives, team_my_tag, HIVE_IGNORE_LIST):
    best_cost = (0, 99999, None)
    for id, data in hives.items():
        if data["type"] == "HIVE_HEALTHY" and (id not in HIVE_IGNORE_LIST):

            hp = Point(data["position"])
            cost = get_distance(rp, hp) / (data["points"][team_my_tag] ** 0.6)

            if cost < best_cost[1]:
                best_cost = (id, cost, hp)
    
    return best_cost[0], best_cost[-1]


def get_next_diseaset(rp, hives, team_my_tag, HIVE_IGNORE_LIST):
    best_cost = (0, 99999, None)
    for id, data in hives.items():
        if data["type"] == "HIVE_DISEASED" and (id not in HIVE_IGNORE_LIST):

            hp = Point(data["position"])
            cost = get_distance(rp, hp) / (data["points"][team_my_tag] ** 0.5)

            if cost < best_cost[1]:
                best_cost = (id, cost, hp)
    
    return best_cost[0], best_cost[-1]


def drop_cage(motor_medium):
    global cage_lifted
    print("Dropping cage: "+str(cage_lifted))
    if (not cage_lifted):
        return
    cage_lifted = False
    motor_medium.run_timed(time_sp=500, speed_sp=-500)
    sleep(2)
    

def lift_cage(motor_medium):
    global cage_lifted
    print("Lifting cage: "+str(cage_lifted))
    if (cage_lifted):
        return
    cage_lifted = True
    motor_medium.run_timed(time_sp=605, speed_sp=500)
    sleep(2)

def reverse_robot(motor_left, motor_right):
    global reverse
    if reverse:
        motor_left.run_timed(time_sp=1000, speed_sp=450)
        motor_right.run_timed(time_sp=1000, speed_sp=450)
    else:
        motor_left.run_timed(time_sp=1000, speed_sp=-450)
        motor_right.run_timed(time_sp=1000, speed_sp=-450)
    sleep(2)

#sm se menu z folkam in praujo da C ne nardi dost razlike tko da dejmo najprej u pythonu probat            
def poc_astar(maze, start, end):

    # Create start and end node
    start_node = Node(None, start)
    start_node.g = start_node.h = start_node.f = 0
    end_node = Node(None, end)
    end_node.g = end_node.h = end_node.f = 0

    # Initialize both open and closed list
    open_list = []
    closed_list = []

    # Add the start node
    open_list.append(start_node)

    # Loop until you find the end
    while len(open_list) > 0:

        # Get the current node
        current_node = open_list[0]
        current_index = 0
        for index, item in enumerate(open_list):
            if item.f < current_node.f:
                current_node = item
                current_index = index

        # Pop current off open list, add to closed list
        open_list.pop(current_index)
        closed_list.append(current_node)

        # Found the goal
        if current_node == end_node:
            path = []
            current = current_node
            while current is not None:
                path.append(current.position)
                current = current.parent
            return path[::-1] # Return reversed path

        # Generate children
        children = []
        for new_position in [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)]: # Adjacent squares

            # Get node position
            node_position = (current_node.position[0] + new_position[0], current_node.position[1] + new_position[1])

            # Make sure within range
            if node_position[0] > (len(maze) - 1) or node_position[0] < 0 or node_position[1] > (len(maze[len(maze)-1]) -1) or node_position[1] < 0:
                continue

            # Make sure walkable terrain
            if maze[node_position[0]][node_position[1]] != 0:
                continue

            # Create new node
            new_node = Node(current_node, node_position)

            # Append
            children.append(new_node)

        # Loop through children
        for child in children:

            # Child is on the closed list
            for closed_child in closed_list:
                if child == closed_child:
                    continue

            # Create the f, g, and h values
            child.g = current_node.g + 1
            child.h = ((child.position[0] - end_node.position[0]) ** 2) + ((child.position[1] - end_node.position[1]) ** 2)
            child.f = child.g + child.h

            # Child is already in the open list
            for open_node in open_list:
                if child == open_node and child.g > open_node.g:
                    continue

            # Add the child to the open list
            open_list.append(child)


# -----------------------------------------------------------------------------
# NASTAVITVE TIPAL, MOTORJEV IN POVEZAVE S STREŽNIKOM
# -----------------------------------------------------------------------------
# Nastavimo tipala in gumbe.
print('Priprava tipal ... ', end='', flush=True)
btn = Button()
#sensor_touch = init_sensor_touch()
#print('OK!')

# Nastavimo velika motorja. Priklopljena naj bosta na izhoda A in D.
print('Priprava motorjev ... ', end='')
motor_left = init_large_motor(MOTOR_LEFT_PORT)
motor_right = init_large_motor(MOTOR_RIGHT_PORT)
motor_medium = init_medium_motor(MOTOR_MEDIUM_PORT)
print('OK!')

if "DVIGNI" in kletka:
    cage_lifted = False
    lift_cage(motor_medium)
elif "SPUSTI" in kletka:
    cage_lifted = True
    drop_cage(motor_medium)
else:
    pass


# Nastavimo povezavo s strežnikom.
url = SERVER_IP + GAME_ID
print('Vspostavljanje povezave z naslovom ' + url + ' ... ', end='', flush=True)
conn = Connection(url)
print('OK!')

# Informativno izmerimo zakasnitev pri pridobivanju podatkov (povprečje num_iters meritev)
print('Zakasnitev v komunikaciji s streznikom ... ', end='', flush=True)
print('%.4f s' % (conn.test_delay(num_iters=10)))


# -----------------------------------------------------------------------------
# PRIPRAVA NA TEKMO
# -----------------------------------------------------------------------------
# Pridobimo podatke o tekmi.
game_state = conn.request()
MY_HIVE = None
OP_HIVE = None

RICH_LINE = None

HIVE_IGNORE_LIST = []
MAX_MOVED_FOR = 120

# Ali naš robot sploh tekmuje? Če tekmuje, ali je team1 ali team2?
if ROBOT_ID == game_state['teams']['team1']['id']:
    team_my_tag = 'team1'
    team_op_tag = 'team2'
    MY_HIVE = Point({"x": 100, "y": 1000})
    OP_HIVE = Point({"x": 3400, "y": 1000})
    RICH_LINE = 2600
elif ROBOT_ID == game_state['teams']['team2']['id']:
    team_my_tag = 'team2'
    team_op_tag = 'team1'
    MY_HIVE = Point({"x": 3400, "y": 1000})
    OP_HIVE = Point({"x": 100, "y": 1000})
    RICH_LINE = 900
else:
    print('Robot ne tekmuje.')
    robot_die()
print('Robot tekmuje in ima interno oznako "' + team_my_tag + '"')
"""
# Endgame maneuver za čiščenje baze od grdih panjev, ki rabi tedve start / end točki; -cene
ENDGAME_START = Point({"x": 250, "y": 250}, "ENDGAME_START")
ENDGAME_END = Point({"x": 250, "y": 1750}, "ENDGAME_END")
"""
# -----------------------------------------------------------------------------
# GLAVNA ZANKA
# -----------------------------------------------------------------------------
print('Izvajam glavno zanko. Prekini jo s pritiskon na tipko DOL.')
print('Cakam na zacetek tekme ...')



#Sound.speak(SONG_LYRICS)

# Začetno stanje.
state = State.IDLE
# Prejšnje stanje.
state_old = -1
# Indeks trenutne ciljne lokacije.
target_idx = 0
last_valid_target_idx = 0
collecting = False
diseaset = False

# Izberi cilj
robot_pos = None
target = None
target_moved_for = 0
reset_target = True

for robot_data in game_state['objects']['robots'].values():
    if robot_data['id'] == ROBOT_ID:
        robot_pos = Point(robot_data['position'])

if robot_pos:
    target_idx, target = get_next_healthy(robot_pos, game_state['objects']['hives'], team_my_tag, HIVE_IGNORE_LIST)
    if target == None:
        target_idx, target = get_next_diseaset(robot_pos, game_state['objects']['hives'], team_my_tag, HIVE_IGNORE_LIST)
        if target == None:
            target_idx = 0
            target = robot_pos
            collecting = False
        else:
            reset_target = False
            diseaset = True
            collecting = True
    else:
        reset_target = False
        diseaset = False
        collecting = True


# Regulator PID za obračanje na mestu.
# setpoint=0 pomeni, da naj bo kot med robotom in ciljem (target_angle) enak 0.
# Naša regulirana veličina je torej kar napaka kota, ki mora biti 0.
# To velja tudi za regulacijo vožnje naravnost.
#ŠPAGET ŠPAGET


PID_turn_reverse = PID(
    setpoint=0,
    Kp=PID_TURN_REVERSE_KP,
    Ki=PID_TURN_REVERSE_KI,
    Kd=PID_TURN_REVERSE_KD,
    integral_limit=PID_TURN_INT_MAX)
     
PID_turn = PID(
    setpoint=0,
    Kp=PID_TURN_KP,
    Ki=PID_TURN_KI,
    Kd=PID_TURN_KD,
    integral_limit=PID_TURN_INT_MAX)

# PID za vožnjo naravnost - regulira nazivno hitrost za oba motorja,
# ki je odvisna od oddaljenosti od cilja.
# setpoint=0 pomeni, da mora biti razdalja med robotom in ciljem enaka 0.
PID_frwd_base = PID(
    setpoint=0,
    Kp=PID_STRAIGHT_KP,
    Ki=PID_STRAIGHT_KI,
    Kd=PID_STRAIGHT_KD,
    integral_limit=PID_STRAIGHT_INT_MAX)

# PID za obračanje med vožnjo naravnost.
# setpoint=0 pomeni, da naj bo kot med robotom in ciljem (target_angle) enak 0.
PID_frwd_turn = PID(
    setpoint=0,
    Kp=PID_TURN_KP,
    Ki=PID_TURN_KI,
    Kd=PID_TURN_KD,
    integral_limit=PID_TURN_INT_MAX)

# Hitrost na obeh motorjih.
speed_right = 0
speed_left = 0

# Zgodovina (okno) zadnjih nekaj vrednosti meritev kota in razdalje.
# Implementirana je kot vrsta FIFO.
robot_dir_hist = deque([180.0] * HIST_QUEUE_LENGTH)
robot_dist_hist = deque([math.inf] * HIST_QUEUE_LENGTH)

initial_set = False
found = False
bogatenje = False

# Merimo čas obhoda zanke. Za visoko odzivnost robota je zelo pomembno,
# da je ta čas čim krajši.
t_old = time()
reverse = False  #attemptam nek ŠPAGET code rn
do_main_loop = True

next_chunk = None

grid = Grid({"x": 7, "y": 4}, 25)
for chunk in grid.get_chunks():
    chunk.update_chunk()

#print(str(grid))

"""
#ŠPAGETNA KODA debug pid/multiplier setter
modifier = 10
speed_right = 100
speed_left = -100

while do_main_loop:
    # Izračunane hitrosti zapišemo na motorje.
    motor_right.run_forever(speed_sp=speed_right)
    motor_left.run_forever(speed_sp=speed_left)
    print("vrtimo se pri hitrosti " + str(speed_right))
    sleep(5)
    speed_right += modifier
    speed_left -= modifier
    motor_right.stop
    motor_left.stop
    sleep(2)
    if input("Jumpstart y?") == 'y':
        prev_right = speed_right
        prev_left = speed_left
        speed_right = -800
        speed_left = 800
        motor_right.run_forever(speed_sp=speed_right)
        motor_left.run_forever(speed_sp=speed_left)
        sleep(0.7)
        speed_right = prev_right
        speed_left = prev_left

                                                
#END OF ŠPAGETd
"""
#Sound.play('primo_victoria.wav')

while do_main_loop and not btn.down:
    try:
        time_now = time()
        loop_time = time_now - t_old
        t_old = time_now

        # Zaznaj spremembo stanja.
        if state != state_old:
            state_changed = True
        else:
            state_changed = False
        state_old = state
        # -cene experimental
        #print(state, reverse)
        # Osveži stanje tekme.
        game_state = conn.request()
        if game_state == -1:
            print('Napaka v paketu, ponovni poskuss ...')
        else:
            game_on = game_state['gameOn']
            time_left = game_state['timeLeft']

            # Pridobi pozicijo in orientacijo svojega robota;
            # najprej pa ga poišči v tabeli vseh robotov na poligonu.
            robot_pos = None
            robot_dir = None
            for robot_data in game_state['objects']['robots'].values():
                if robot_data['id'] == ROBOT_ID:
                    robot_pos = Point(robot_data['position'])
                    robot_dir = robot_data['dir'] + 180 if  reverse else robot_data['dir']

            # Ali so podatki o robotu veljavni? Če niso, je zelo verjetno,
            # da sistem ne zazna oznake na robotu.
            robot_alive = (robot_pos is not None) and (robot_dir is not None)

            
            # Če tekma poteka in je oznaka robota vidna na kameri,
            # potem izračunamo novo hitrost na motorjih.
            # Sicer motorje ustavimo.

            if game_on and robot_alive:


                # Razdalja med robotom in ciljem.
                target_dist = get_distance(robot_pos, target)
                # Kot med robotom in ciljem.
                target_angle = get_angle(robot_pos, robot_dir, target)
                
                if target_idx != 0 and robot_pos:
                    if target_idx in game_state['objects']['hives']:
                        target_moved_for = get_distance(target, Point(game_state['objects']['hives'][target_idx]["position"]))

                
                if target_moved_for > MAX_MOVED_FOR:

                    motor_right.stop(stop_action='brake')
                    motor_left.stop(stop_action='brake')

                    if target_idx not in HIVE_IGNORE_LIST:
                        HIVE_IGNORE_LIST.append(target_idx)
                        if len(HIVE_IGNORE_LIST) >= 2:
                            HIVE_IGNORE_LIST.pop(0)

                    reset_target = True
                    state = State.LOAD_NEXT_TARGET

                # Spremljaj zgodovino meritev kota in oddaljenosti.
                # Odstrani najstarejši element in dodaj novega - princip FIFO.
                robot_dir_hist.popleft()
                robot_dir_hist.append(target_angle)
                robot_dist_hist.popleft()
                robot_dist_hist.append(target_dist)

                if state == State.IDLE:
                    # Stanje mirovanja - tu se odločamo, kaj bo robot sedaj počel.
                    speed_right = 0
                    speed_left = 0
                    # Preverimo, ali je robot na ciljni točki.
                    # Če ni, ga tja pošljemo.
                    if target_dist > DIST_EPS:
                        print("This happened")
                        state = State.TURN
                        robot_near_target_old = False
                    else:
                        state = State.LOAD_NEXT_TARGET
                        found = True
                        print("Found je bil set na True v line 1043")
                        reverse = False
                        set_near_values()


                elif state == State.LOAD_NEXT_TARGET:
                    print("distance = " + str(DIST_EPS) + " hives="+str(hives_in_control) + "reset = " + str(reset_target)+ " collecting = " + str(collecting) + "bog="+ str(bogatenje))
                    if reset_target:
                        print("Reset9jg")
                        lift_cage(motor_medium)
                        collecting = False
                        
                    # ce smo nasli panj gremo domov in obratno
                    if collecting:
                        print("Collectamo!")
                        if not reset_target:
                            print("Not reset targetamo!")
                            if found:
                                print("Foundamo!")
                                drop_cage(motor_medium)
                                print("found and distance = " + str(DIST_EPS))
                                hives_in_control = 1
                                DIST_EPS = 170

                                bogatenje = not bogatenje                

                                if target_idx:
                                    HIVE_IGNORE_LIST.append(target_idx)

                                #hives_in_control += 1
                                found = False

                        if diseaset:
                            target_idx = 0
                            target = OP_HIVE
                            bogatenje = False


                        else:

                            if hives_in_control == 1:
                                if not bogatenje:
                                    if last_valid_target_idx not in HIVE_IGNORE_LIST:
                                        HIVE_IGNORE_LIST.append(last_valid_target_idx)
                                    target_idx = 0
                                    target = MY_HIVE
                                    reverse = True
                                    set_near_values()
                                else:
                                    target_idx = 0
                                    target = Point({"x": RICH_LINE, "y": robot_pos.y})
                                    bogatenje = True
                                    if (team_my_tag == 'team1' and robot_pos.x > target.x) or (team_my_tag == 'team2' and robot_pos.x < target.x):
                                        if last_valid_target_idx not in HIVE_IGNORE_LIST:
                                            HIVE_IGNORE_LIST.append(last_valid_target_idx)
                                        bogatenje = False
                                        hives_in_control = 1
                                        target = MY_HIVE
                                        reverse = True
                                        set_near_values()
                        
                    else:
                        if not reset_target:
                            HIVE_IGNORE_LIST.clear()
                            if not diseaset:
                                lift_cage(motor_medium)

                            if diseaset:
                                print("diseased smo pripeljali v opp bazo in zdej se diseaset = false")
                                #experimental -cene
                                #reverse_robot(motor_left, motor_right)
                                #diseaset = False
                                #zaenkrat se zaklenimo v njihovo bazo -tbd- -cene
                                motor_left.stop(stop_action='brake')
                                motor_right.stop(stop_action='brake')
                                #do what next??
                                while True:
                                    print("a")


                            HIVE_IGNORE_LIST.append(last_valid_target_idx)
                            reverse = False
                            set_near_values()
                            state = State.IDLE
                            reset_target = True
                            target_idx = 0
                            last_valid_target_idx = 0
                            continue

                        target_idx, target = get_next_healthy(robot_pos, game_state['objects']['hives'], team_my_tag, HIVE_IGNORE_LIST)
                        if target == None:
                            target_idx, target = get_next_diseaset(robot_pos, game_state['objects']['hives'], team_my_tag, HIVE_IGNORE_LIST)
                            if target == None:
                                target_idx = 0
                                target = robot_pos
                                HIVE_IGNORE_LIST.clear()
                                #experimental change -cene
                                #robot_die()
                            else:
                                diseaset = True
                        else:
                            diseaset = False

                        last_valid_target_idx = target_idx
                        collecting = True

                    if (hives_in_control == 1 and not bogatenje):
                        hives_in_control = 0
                        collecting = False

                    reset_target = False
                    state = State.IDLE
                    
                    """
                    #check za endgame maneuver -cene
                    #if kibla dol, porihtaj prej
                    if game_state['timeLeft'] < 120:
                        #špageti -cene
                        pogoj = True
                        try:
                            for panj in game_state['objects']['hives']:
                                    if panj['type'] == "HIVE_HEALTHY":
                                        pogoj = False
                                        break
                        except TypeError:
                            pogoj = False

                        if pogoj:
                            print("mimo pogoja target_name:  ",target.name)
                            if target.name == "ENDGAME_START":
                                target = ENDGAME_END
                            else:
                                target = ENDGAME_START
                    print("Current target: ",(target.x,target.y, target.name))
                    print("Time: ", game_state['timeLeft'])
                    """

                elif state == State.TURN:
                    #ŠPAGET
                    if reverse:
                        obracalec = PID_turn_reverse
                    else:
                        obracalec = PID_turn
                    # Obračanje robota na mestu, da bo obrnjen proti cilju.
                    if state_changed:
                        # Če smo ravno prišli v to stanje, najprej ponastavimo PID.
                        #PID_turn.reset()
                        obracalec.reset()

                    # Ali smo že dosegli ciljni kot?
                    # Zadnjih nekaj obhodov zanke mora biti absolutna vrednost
                    # napake kota manjša od DIR_EPS.
                    err = [abs(a) > DIR_EPS for a in robot_dir_hist]

                    if sum(err) == 0:
                        # Vse vrednosti so znotraj tolerance, zamenjamo stanje.
                        speed_right = 0
                        speed_left = 0
                        state = State.DRIVE_STRAIGHT
                    else:
                        # Reguliramo obračanje.
                        # Ker se v regulatorju trenutna napaka izračuna kot:
                        #   error = setpoint - measurement,
                        # dobimo negativno vrednost, ko se moramo zavrteti
                        # v pozitivno smer.
                        # Primer:
                        #   Robot ima smer 90 stopinj (obrnjen je proti "severu").
                        #   Cilj se nahaja na njegovi levi in da ga doseže,
                        #   se mora obrniti za 90 stopinj.
                        #       setpoint=0
                        #       target_angle = measurement = 90
                        #       error = setpoint - measurement = -90
                        #       u = funkcija, odvisna od error in parametrov PID.
                        #   Če imamo denimo Kp = 1, Ki = Kd = 0, potem bo u = -90.
                        #   Robot se mora zavrteti v pozitivno smer,
                        #   torej z desnim kolesom naprej in levim nazaj.
                        #   Zato:
                        #   speed_right = -u
                        #   speed_left = u
                        #   Lahko bi tudi naredili droben trik in bi rekli:
                        #       measurement= -target_angle.
                        #   V tem primeru bi bolj intuitivno nastavili
                        #   speed_right = u in speed_left = -u.
                        #ŠPAGET u = PID_turn.update(measurement=target_angle)
                        u = obracalec.update(measurement=target_angle)
                        scale = 2.5
                        speed_right = -u if hives_in_control == 0 else -u *scale 
                        speed_left = u if hives_in_control == 0 else u *scale
                        #ma raj ne
                        """
                        if reverse:
                            if speed_right < 0:
                                speed_right *= 0.3
                                speed_left *= 2
                            else:
                                speed_right *= 2
                                speed_left *= 0.3
                                """
                elif state == State.DRIVE_STRAIGHT:
                    # Vožnja robota naravnost proti ciljni točki.
                    # Vmes bi radi tudi zavijali, zato uporabimo dva regulatorja.
                    if state_changed:
                        # Ponastavi regulatorja PID.
                        PID_frwd_base.reset()
                        PID_frwd_turn.reset()
                        timer_near_target = TIMER_NEAR_TARGET

                    # Ali smo blizu cilja?
                    robot_near_target = target_dist < DIST_NEAR
                    if not robot_near_target_old and robot_near_target:
                        # Vstopili smo v bližino cilja.
                        # Začnimo odštevati varnostno budilko.
                        timer_near_target = TIMER_NEAR_TARGET
                    if robot_near_target:
                        timer_near_target = timer_near_target - loop_time
                    robot_near_target_old = robot_near_target

                    # Ali smo že na cilju?
                    # Zadnjih nekaj obhodov zanke mora biti razdalja do cilja
                    # manjša ali enaka DIST_EPS.
                    err_eps = [d > DIST_EPS for d in robot_dist_hist]
                    if sum(err_eps) == 0:
                        # Razdalja do cilja je znotraj tolerance, zamenjamo stanje.
                        speed_right = 0
                        speed_left = 0
                        state = State.IDLE
                    elif timer_near_target < 0:
                        # Smo morda blizu cilja in je varnostna budilka potekla?
                        speed_right = 0
                        speed_left = 0
                        state = State.TURN
                    else:
                        u_turn = PID_frwd_turn.update(measurement=target_angle)
                        # Ker je napaka izračunana kot setpoint - measurement in
                        # smo nastavili setpoint na 0, bomo v primeru u_base dobili
                        # negativne vrednosti takrat, ko se bo robot moral premikati
                        # naprej. Zato dodamo minus pri izračunu hitrosti motorjev.
                        u_base = PID_frwd_base.update(measurement=target_dist)
                        # Omejimo nazivno hitrost, ki je enaka za obe kolesi,
                        # da imamo še manevrski prostor za zavijanje.
                        u_base = min(max(u_base, -SPEED_BASE_MAX), SPEED_BASE_MAX)
                        d = -1 if reverse else 1
                        speed_right = -u_base*d - u_turn 
                        speed_left = -u_base*d + u_turn 
                        if reverse:
                            if speed_right < speed_left:
                                speed_right *= 1.85
                                speed_left *= 0.6
                            else:
                                speed_right *= 0.6
                                speed_left *= 1.85
                # Omejimo vrednosti za hitrosti na motorjih.
                speed_right = round(
                                min(
                                    max(speed_right, -SPEED_MAX),
                                    SPEED_MAX)
                                )
                speed_left = round(
                                min(
                                    max(speed_left, -SPEED_MAX),
                                    SPEED_MAX)
                                )
                # Izračunane hitrosti zapišemo na motorje.
                motor_right.run_forever(speed_sp=speed_right)
                motor_left.run_forever(speed_sp=speed_left)

            else:
                # Robot bodisi ni viden na kameri bodisi tekma ne teče, 
                # zato ustavimo motorje.
                motor_left.stop(stop_action='brake')
                motor_right.stop(stop_action='brake')

    except KeyboardInterrupt as e:
        print('bye :)')
        robot_die()
# Konec programa
robot_die()
