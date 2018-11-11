# Run the garage server with simulated GPIO.
# This allow to run the server on a laptop for development.

import sys
sys.modules['RPi'] = __import__('simRPi')

import garage_server  # noqa


if __name__ == '__main__':
    import sys
    garage_server.main(sys.argv[1:])
