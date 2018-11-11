# A simple test to verify configurations of the garage controller
# alerts. This program load the config and call controller.send_alert

import unittest
from unittest.mock import patch

import json

import sys
sys.modules['RPi'] = __import__('simRPi')
from garage_controller import Controller  # noqa


def fake_syslog(message):
    print("syslog: %s" % message)


class ControllerTest(unittest.TestCase):
    def setUp(self):
        config_file = open('config_perso.json')
        self.config = json.load(config_file)
        config_file.close()

    @patch("syslog.syslog", side_effect=fake_syslog, autospec=True)
    def test_send_alert(self, mock_syslog):
        controller = Controller(self.config)
        for door in controller.doors:
            self.assertEqual(door.pb_iden, None)
            controller.send_alert(door, "Test alert", "A simple test to verify alert.")

        for door in controller.doors:
            self.assertNotEqual(door.pb_iden, None)
            controller.send_alert(door, "Test alert", "A simple test to verify alert.")
