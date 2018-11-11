import unittest

import json

import sys
sys.modules['RPi'] = __import__('simRPi')
from garage_controller import Controller  # noqa
import garage_server  # noqa


class UptimeHandlerTest(unittest.TestCase):
    def setUp(self):
        config_file = open('config.json')
        self.config = json.load(config_file)
        config_file.close()

    def test_uptime(self):
        controller = Controller(self.config)
        uptime_handler = garage_server.UptimeHandler(controller)
        uptime = uptime_handler.getUptime()
        # Check that all field returned a numerical value greater or equal to zero
        uptime_fields = uptime.split(b":")
        for field in uptime_fields:
            self.assertGreaterEqual(float(field), 0.0)
