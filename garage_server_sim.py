import sys
sys.modules['RPi'] = __import__('simRPi')

import garage_server

if __name__ == '__main__':
    import sys
    garage_server.main(sys.argv[1:])
