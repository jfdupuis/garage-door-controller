import simRPi.GPIO as sim_gpio

import unittest
from unittest.mock import patch, call

import json

import sys
sys.modules['RPi'] = __import__('simRPi')
from garage_controller import Controller  # noqa


class MockUpdateHandler():
    def handle_updates(self):
        print("update")
        return


class ControllerTest(unittest.TestCase):
    def setUp(self):
        config_file = open('config.json')
        self.config = json.load(config_file)
        config_file.close()

    @patch("RPi.GPIO.output", autospec=True)
    def test_init(self, mock_output):
        controller = Controller(self.config)
        self.assertEqual(len(controller.doors), 2)
        mock_output.assert_has_calls(
            [call(controller.doors[0].relay_pin, True),
             call(controller.doors[1].relay_pin, True)], any_order=True)

        for door in controller.doors:
            # Test initial values
            self.assertEqual(door.last_action, None)
            self.assertEqual(door.last_action_time, 0)

    @patch("RPi.GPIO.output", autospec=True)
    def test_toggle_relay(self, mock_output):
        controller = Controller(self.config)

        for door in controller.doors:
            controller.toggle(door.id)
            mock_output.assert_has_calls(
                [call(door.relay_pin, False),
                 call(door.relay_pin, True)], any_order=False)

    @patch('time.time', autospec=True)
    @patch("RPi.GPIO.output", autospec=True)
    @patch("RPi.GPIO.input", autospec=True)
    def test_door_get_state(self, mock_input, mock_output, mock_time):
        start_time = 10.0
        mock_time.return_value = start_time

        controller = Controller(self.config)

        for door in controller.doors:
            # state_pin = 0
            mock_input.return_value = 0
            door.last_action_time = start_time

            door.last_action = None
            self.assertEqual(door.get_state(), 'closed')
            mock_input.assert_called_with(door.state_pin)

            door.last_action = 'open'
            self.assertEqual(door.get_state(), 'closed')
            mock_input.assert_called_with(door.state_pin)

            door.last_action = 'close'
            self.assertEqual(door.get_state(), 'closed')
            mock_input.assert_called_with(door.state_pin)

            mock_time.return_value = door.time_to_open + door.time_to_close

            door.last_action = 'open'
            self.assertEqual(door.get_state(), 'closed')
            mock_input.assert_called_with(door.state_pin)

            door.last_action = 'close'
            self.assertEqual(door.get_state(), 'closed')
            mock_input.assert_called_with(door.state_pin)

            # state_pin = 1
            mock_input.return_value = 1

            door.last_action = 'open'
            door.last_action_time = start_time

            mock_time.return_value = start_time + 1
            self.assertEqual(door.get_state(), 'opening')
            mock_input.assert_called_with(door.state_pin)

            mock_time.return_value = start_time + door.time_to_open + 1
            self.assertEqual(door.get_state(), 'open')
            mock_input.assert_called_with(door.state_pin)

            door.last_action = 'close'
            door.last_action_time = start_time

            mock_time.return_value = start_time + 1
            self.assertEqual(door.get_state(), 'closing')
            mock_input.assert_called_with(door.state_pin)

            mock_time.return_value = start_time + door.time_to_close + 1
            self.assertEqual(door.get_state(), 'open')
            mock_input.assert_called_with(door.state_pin)

            door.last_action = None
            self.assertEqual(door.get_state(), 'open')
            mock_input.assert_called_with(door.state_pin)

    @patch('time.time', autospec=True)
    @patch("garage_controller.Controller.send_alert", autospec=True)
    @patch("garage_controller.Controller.notify_state_change", autospec=True)
    @patch("RPi.GPIO.output", autospec=True)
    @patch("RPi.GPIO.input", side_effect=sim_gpio.input, autospec=True)
    def test_status_check_alert(self, mock_input, mock_output, mock_notify, mock_alert, mock_time):
        start_time = 10.0
        mock_time.return_value = start_time

        controller = Controller(self.config)
        controller.use_alerts = True
        controller.time_to_wait = 10

        for door in controller.doors:
            mock_input.return_value = 0
            self.assertEqual(door.get_state(), 'closed')
            mock_input.assert_called_with(door.state_pin)
            self.assertEqual(door.last_state, 'unknown')

        door = controller.doors[0]

        # Make sure the side effect works
        sim_gpio.set_state(door.state_pin, 1)
        self.assertEqual(door.get_state(), 'open')
        self.assertEqual(controller.doors[1].get_state(), 'closed')

        # unknown => open
        # unknown => closed
        controller.status_check()
        self.assertEqual(mock_notify.call_count, 2)
        mock_notify.assert_has_calls(
            [call(controller, controller.doors[0], "open"),
             call(controller, controller.doors[1], "closed")])
        mock_notify.reset_mock()

        # Timeout
        # open => open
        # closed => closed
        mock_time.return_value = start_time + door.time_to_open + controller.time_to_wait + 1
        controller.status_check()
        self.assertEqual(mock_alert.call_count, 1)
        self.assertEqual(mock_notify.call_count, 0)

        mock_notify.reset_mock()
        mock_alert.reset_mock()

        # open => closed
        # closed => closed
        sim_gpio.set_state(door.state_pin, 0)
        self.assertEqual(door.get_state(), 'closed')
        self.assertEqual(controller.doors[1].get_state(), 'closed')

        controller.status_check()
        self.assertEqual(mock_alert.call_count, 1)
        mock_notify.assert_called_once_with(controller, door, "closed")

        mock_notify.reset_mock()
        mock_alert.reset_mock()

        # No Timeout
        # closed => open
        # closed => closed
        sim_gpio.set_state(door.state_pin, 1)
        mock_time.return_value = start_time + door.time_to_open + 1
        controller.status_check()
        self.assertEqual(mock_alert.call_count, 0)
        mock_notify.assert_called_once_with(controller, door, "open")

        mock_notify.reset_mock()
        mock_alert.reset_mock()

    @patch('time.time', autospec=True)
    @patch("garage_controller.Controller.send_alert", autospec=True)
    @patch("garage_controller.Controller.notify_state_change", autospec=True)
    @patch("RPi.GPIO.output", autospec=True)
    @patch("RPi.GPIO.input", side_effect=sim_gpio.input, autospec=True)
    def test_toggle_sequence(self, mock_input, mock_output, mock_notify, mock_alert, mock_time):
        start_time = 10.0
        mock_time.return_value = start_time

        controller = Controller(self.config)
        controller.use_alerts = True

        door = controller.doors[0]

        sim_gpio.set_state(door.state_pin, 0)
        self.assertEqual(door.get_state(), 'closed')

        controller.toggle(door.id)
        mock_output.assert_has_calls(
            [call(door.relay_pin, False),
             call(door.relay_pin, True)], any_order=False)

        mock_time.return_value = start_time + door.time_to_open / 2
        sim_gpio.set_state(door.state_pin, 1)
        self.assertEqual(door.get_state(), 'opening')

        controller.status_check()
        mock_notify.assert_has_calls(
            [call(controller, controller.doors[0], "opening"),
             call(controller, controller.doors[1], "closed")])
        self.assertEqual(mock_alert.call_count, 0)

        mock_notify.reset_mock()
        mock_alert.reset_mock()

        mock_time.return_value = start_time + door.time_to_open + 1
        self.assertEqual(door.get_state(), 'open')
        controller.status_check()
        mock_notify.assert_called_once_with(controller, door, "open")
        self.assertEqual(mock_alert.call_count, 0)

        mock_notify.reset_mock()
        mock_alert.reset_mock()

        mock_time.return_value = start_time + door.time_to_open + controller.time_to_wait + 1
        self.assertEqual(door.get_state(), 'open')
        controller.status_check()
        self.assertEqual(mock_notify.call_count, 0)
        self.assertEqual(mock_alert.call_count, 1)

        mock_notify.reset_mock()
        mock_alert.reset_mock()

        controller.toggle(door.id)
        sim_gpio.set_state(door.state_pin, 1)

        mock_time.return_value = start_time + door.time_to_open + \
            controller.time_to_wait + door.time_to_close / 2
        self.assertEqual(door.get_state(), 'closing')
        controller.status_check()
        mock_notify.assert_called_once_with(controller, door, "closing")
        self.assertEqual(mock_alert.call_count, 0)

        mock_notify.reset_mock()
        mock_alert.reset_mock()

        sim_gpio.set_state(door.state_pin, 0)

        mock_time.return_value = start_time + door.time_to_open + \
            controller.time_to_wait + door.time_to_close + 1
        self.assertEqual(door.get_state(), 'closed')
        controller.status_check()
        mock_notify.assert_called_once_with(controller, door, "closed")
        self.assertEqual(mock_alert.call_count, 1)

        mock_notify.reset_mock()
        mock_alert.reset_mock()

        # With door jam while opening
        mock_time.return_value = start_time
        sim_gpio.set_state(door.state_pin, 0)
        self.assertEqual(door.get_state(), 'closed')
        controller.status_check()
        self.assertEqual(mock_notify.call_count, 0)
        self.assertEqual(mock_alert.call_count, 0)

        controller.toggle(door.id)

        sim_gpio.set_state(door.state_pin, 1)
        mock_time.return_value = start_time + door.time_to_open / 2
        controller.status_check()
        self.assertEqual(door.get_state(), 'opening')
        mock_notify.assert_called_once_with(controller, door, "opening")
        mock_notify.reset_mock()
        self.assertEqual(mock_alert.call_count, 0)

        mock_time.return_value = start_time + 2 * door.time_to_open + controller.time_to_wait + 1
        controller.status_check()
        self.assertEqual(door.get_state(), 'open')
        mock_notify.assert_called_once_with(controller, door, "open")
        mock_notify.reset_mock()
        self.assertEqual(mock_alert.call_count, 1)
        mock_alert.reset_mock()

        # Trigger close
        start_time = start_time + 2 * door.time_to_open + controller.time_to_wait + 2
        mock_time.return_value = start_time
        controller.toggle(door.id)
        self.assertEqual(door.get_state(), 'closing')
        controller.status_check()
        self.assertEqual(mock_alert.call_count, 0)
        mock_notify.assert_called_once_with(controller, door, "closing")
        mock_notify.reset_mock()

        # Jam while closing
        mock_time.return_value = start_time + 2 * door.time_to_close + controller.time_to_wait
        self.assertEqual(door.get_state(), 'open')
        controller.status_check()
        self.assertEqual(mock_alert.call_count, 1)
        mock_notify.assert_called_once_with(controller, door, "open")
        mock_notify.reset_mock()
        mock_alert.reset_mock()

        # Trigger close
        start_time = start_time + 2 * door.time_to_close + controller.time_to_wait
        mock_time.return_value = start_time
        controller.toggle(door.id)
        self.assertEqual(door.get_state(), 'closing')
        controller.status_check()
        self.assertEqual(mock_alert.call_count, 0)
        mock_notify.assert_called_once_with(controller, door, "closing")
        mock_notify.reset_mock()

        # Successfully close
        sim_gpio.set_state(door.state_pin, 0)
        mock_time.return_value = start_time + door.time_to_close - 1
        self.assertEqual(door.get_state(), 'closed')
        controller.status_check()
        self.assertEqual(mock_alert.call_count, 1)
        mock_notify.assert_called_once_with(controller, door, "closed")
        mock_notify.reset_mock()
