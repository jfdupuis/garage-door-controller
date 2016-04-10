# Info collected from

BCM = 11
BOARD = 10

PUD_DOWN = 21
PUD_OFF = 20
PUD_UP = 22


RISING = 31
FALLING = 32
BOTH = 33

SERIAL = 40
SPI = 41
I2C = 42
HARD_PWM = 43

HIGH = 1
LOW = 0

IN = 1
OUT = 0

UNKNOWN = -1

RPI_INFO = {'P1_REVISION': 3, 'REVISION': 'a22082', 'RAM': '1024M', 'TYPE': 'Pi 3 Model B', 'PROCESSOR': 'BCM2837', 'MANUFACTURER': 'Embest'}
RPI_REVISION = 3

#VERSION = '0.6.2'

# Rev 2
GPIO_BOARD_NAMES = [
    "3v3","5v",
    "GPIO2","5V",
    "GPIO3","GND",
    "GPIO4","GPIO14",
    "GND","GPIO15",
    "GPIO17","GPIO18",
    "GPIO27","GND",
    "GPIO22","GPIO23",
    "3V3","GPIO24",
    "GPIO10","GND",
    "GPIO9","GPIO25",
    "GPIO11","GPIO8",
    "GND","GPIO7",
    "I2C","I2C",
    "GPIO5","GND",
    "GPIO6","GPIO12",
    "GPIO13","GND",
    "GPIO19","GPIO16",
    "GPIO26","GPIO20",
    "GND","GPIO21"
]


#REV = 0  # Board revision 1.0
#REV = 1  # Board revision 2.0
REV = 2  # Board Model B+, Pi2B, Pi3

# The GPIO.BOARD option specifies that you are referring to the pins by the number of the pin the the plug - i.e the numbers printed on the board.
# The GPIO.BCM option means that you are referring to the pins by the "Broadcom SOC channel" number, these are the numbers after "GPIO".
gpiomode = UNKNOWN;
pintogpio = [
    [-1, -1, -1, 0, -1, 1, -1, 4, 14, -1, 15, 17, 18, 21, -1, 22, 23, -1, 24, 10, -1, 9, 25, 11, 8, -1, 7],
    [-1, -1, -1, 2, -1, 3, -1, 4, 14, -1, 15, 17, 18, 27, -1, 22, 23, -1, 24, 10, -1, 9, 25, 11, 8, -1, 7],
    [-1, -1, -1, 2, -1, 3, -1, 4, 14, -1, 15, 17, 18, 27, -1, 22, 23, -1, 24, 10, -1, 9, 25, 11, 8, -1, 7, -1, -1, 5, -1, 6, 12, 13, -1, 19, 16, 26, 20, -1, 21]
]

direction = [UNKNOWN for _ in range(len(GPIO_BOARD_NAMES))]
state = [LOW for _ in range(len(GPIO_BOARD_NAMES))]

output_callback = [None for _ in range(len(GPIO_BOARD_NAMES))]

# class PWM():

def getGPIOName(channel):
    if gpiomode == BOARD:
        return GPIO_BOARD_NAMES[channel]
    else:
        return "GPIO{0}".format(channel)


def convertBoardToGPIO(channel):
    if channel > len(pintogpio[REV]):
        raise Exception('UnsupportedChannelException')
    return pintogpio[REV][channel]

def setmode(mode):
    global gpiomode
    if mode in [BOARD,BCM]:
        gpiomode = mode
    else:
        raise Exception('InvalidMode')
    return

def setup(channel, inout, pull_up_down=PUD_OFF):
    global direction
    if gpiomode == UNKNOWN:
        print("Set mode first!")
        raise Exception('InvalidModeException')
    elif gpiomode == BOARD:
        channel = convertBoardToGPIO[channel]
    direction[channel] = inout
    return None

def input(channel):
    if gpiomode == BOARD:
        channel = convertBoardToGPIO[channel]
    return state[channel]

def output(channel, mode):
    global state

    if gpiomode == BOARD:
        channel = convertBoardToGPIO[channel]
    if direction[channel] is not OUT:
        raise Exception('NotAnOutputException')
    else:
        state[channel] = mode
        if output_callback[channel] is not None:
            output_callback[channel](channel, mode)

    print("Pin {0} is now: {1}".format(getGPIOName(channel), mode))
    return None

def cleanup(channel=None):
    global direction, state
    direction = [UNKNOWN for _ in range(len(GPIO_BOARD_NAMES))]
    state = [LOW for _ in range(len(GPIO_BOARD_NAMES))]
    return None

def setwarnings(state):
    # Not implemented
    return

def add_event_callback():
    raise NotImplementedError
def add_event_detect(channel):
    raise NotImplementedError
def event_detected(channel):
    raise NotImplementedError
def getmode():
    raise NotImplementedError
def gpio_function():
    raise NotImplementedError
def remove_event_detect():
    raise NotImplementedError
def wait_for_edge(channel, edge):
    raise NotImplementedError


def set_state(channel, mode):
    """Set the specified pin state."""
    global state
    if gpiomode == BOARD:
        channel = convertBoardToGPIO[channel]
    state[channel] = mode
    return

def set_output_callback(channel, callback):
    global output_callback
    if gpiomode == UNKNOWN:
        print("Set mode first!")
        raise Exception('InvalidModeException')
    elif gpiomode == BOARD:
        channel = convertBoardToGPIO[channel]
    output_callback[channel] = callback
    return
