import garage_server

import sys
sys.modules['RPi'] = __import__('simRPi')

if __name__ == '__main__':
    import sys
    garage_server.main(sys.argv[1:])
