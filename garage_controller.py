import time, syslog
import smtplib
import RPi.GPIO as gpio
import json

import sys
if sys.version_info < (3,):
    import httplib as httpclient
else:
    import http.client as httpclient

class Door(object):
    last_action = None
    last_action_time = None
    msg_sent = False
    pb_iden = None

    def __init__(self, doorId, config):
        self.id = doorId
        self.name = config['name']
        self.relay_pin = config['relay_pin']
        self.state_pin = config['state_pin']
        self.time_to_close = config.get('time_to_close', 10)
        self.time_to_open = config.get('time_to_open', 10)
        self.openhab_name = config.get('openhab_name')
        self.open_time = time.time()
        gpio.setup(self.relay_pin, gpio.OUT)
        gpio.setup(self.state_pin, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.output(self.relay_pin, True)

    def get_state(self):
        if gpio.input(self.state_pin) == 0:
            return 'closed'
        elif self.last_action == 'open':
            if time.time() - self.last_action_time >= self.time_to_open:
                return 'open'
            else:
                return 'opening'
        elif self.last_action ==  'close':
            if time.time() - self.last_action_time >= self.time_to_close:
                return 'open' # This state indicates a problem
            else:
                return 'closing'
        else:
            return 'open'

    def toggle_relay(self):
        state = self.get_state()
        if (state == 'open'):
            self.last_action = 'close'
            self.last_action_time = time.time()
        elif state == 'closed':
            self.last_action = 'open'
            self.last_action_time = time.time()
        else:
            self.last_action = None
            self.last_action_time = None

        gpio.output(self.relay_pin, False)
        time.sleep(0.2)
        gpio.output(self.relay_pin, True)

class Controller():
    def __init__(self, config):
        self.init_gpio()

        self.config = config
        self.doors = [Door(n,c) for (n,c) in list(config['doors'].items())]
        for door in self.doors:
            door.last_state = 'unknown'
            door.last_state_time = time.time()

        self.use_alerts = config['config']['use_alerts']
        self.alert_type = config['alerts']['alert_type']
        self.time_to_wait = config['alerts']['time_to_wait']
        if self.alert_type == 'smtp':
            self.use_smtp = False
            smtp_params = ("smtphost", "smtpport", "smtp_tls", "username",
                       "password", "to_email", "time_to_wait")
            self.use_smtp = ('smtp' in config['alerts']) and set(smtp_params) == set(config['alerts']['smtp'])
            syslog.syslog("we are using SMTP")
        elif self.alert_type == 'pushbullet':
            self.pushbullet_access_token = config['alerts']['pushbullet']['access_token']
            syslog.syslog("we are using Pushbullet")
        else:
            self.alert_type = None
            syslog.syslog("No alerts configured")

    def init_gpio(self):
        gpio.setwarnings(False)
        gpio.cleanup()
        gpio.setmode(gpio.BCM)

    def set_update_handler(self, update_handler):
        self.updateHandler = update_handler

    def status_check(self):
        for door in self.doors:
            new_state = door.get_state()
            if (door.last_state != new_state):
                syslog.syslog('%s: %s => %s' % (door.name, door.last_state, new_state))
                door.last_state = new_state
                door.last_state_time = time.time()
                self.updateHandler.handle_updates()
                if self.config['config']['use_openhab'] and (new_state == "open" or new_state == "closed"):
                    self.update_openhab(door.openhab_name, new_state)
            if new_state == 'open' and not door.msg_sent and time.time() - door.open_time >= self.time_to_wait:
                if self.use_alerts:
                    title = "%s's garage door open" % door.name
                    message = "%s's garage door has been open for %s" % (door.name,
                                                                     elapsed_time(int(time.time() - door.open_time)))
                    self.send_alert(title, message)
                    door.msg_sent = True

            if new_state == 'closed':
                if self.use_alerts:
                    if door.msg_sent == True:
                        title = "%s's garage doors closed" % door.name
                        message = "%s's garage door is now closed after %s "% (door.name,
                                                                               elapsed_time(int(time.time() - door.open_time)))
                        self.send_alert(title, message)
                door.open_time = time.time()
                door.msg_sent = False

    def send_alert(self, title, message):
        if self.alert_type == 'smtp':
            self.send_email(title, message)
        elif self.alert_type == 'pushbullet':
            self.send_pushbullet(title, message)

    def send_email(self, title, message):
        if self.use_smtp:
            syslog.syslog("Sending email message")
            config = self.config['alerts']['smtp']
            server = smtplib.SMTP(config["smtphost"], config["smtpport"])
            if (config["smtp_tls"] == "True") :
                server.starttls()
            server.login(config["username"], config["password"])
            server.sendmail(config["username"], config["to_email"], message)
            server.close()

    def send_pushbullet(self, door, title, message):
        syslog.syslog("Sending pushbutton message")
        config = self.config['alerts']['pushbullet']

        if door.pb_iden != None:
            conn = httpclient.HTTPSConnection("api.pushbullet.com:443")
            conn.request("DELETE", '/v2/pushes/' + door.pb_iden, "",
                         {'Authorization': 'Bearer ' + config['access_token'], 'Content-Type': 'application/json'})
            conn.getresponse()
            door.pb_iden = None

        conn = httpclient.HTTPSConnection("api.pushbullet.com:443")
        conn.request("POST", "/v2/pushes",
             json.dumps({
                 "type": "note",
                 "title": title,
                 "body": message,
             }), {'Authorization': 'Bearer ' + config['access_token'], 'Content-Type': 'application/json'})
        door.pb_iden = json.loads(conn.getresponse().read())['iden']

    def update_openhab(self, item, state):
        syslog.syslog("Updating openhab")
        config = self.config['openhab']
        conn = httpclient.HTTPConnection("%s:%s" % (config['server'], config['port']))
        conn.request("PUT", "/rest/items/%s/state" % item, state)
        conn.getresponse()


    def toggle(self, doorId):
        for d in self.doors:
            if d.id == doorId:
                syslog.syslog('%s: toggled' % d.name)
                d.toggle_relay()
                return

    def get_updates(self, lastupdate):
        updates = []
        for d in self.doors:
            if d.last_state_time >= lastupdate:
                updates.append((d.id, d.last_state, d.last_state_time))
        return updates

def elapsed_time(seconds, suffixes=['y','w','d','h','m','s'], add_s=False, separator=' '):
    """
    Takes an amount of seconds and turns it into a human-readable amount of time.
    """
    # the formatted time string to be returned
    time = []

    # the pieces of time to iterate over (days, hours, minutes, etc)
    # - the first piece in each tuple is the suffix (d, h, w)
    # - the second piece is the length in seconds (a day is 60s * 60m * 24h)
    parts = [(suffixes[0], 60 * 60 * 24 * 7 * 52),
             (suffixes[1], 60 * 60 * 24 * 7),
             (suffixes[2], 60 * 60 * 24),
             (suffixes[3], 60 * 60),
             (suffixes[4], 60),
             (suffixes[5], 1)]

    # for each time piece, grab the value and remaining seconds, and add it to
    # the time string
    for suffix, length in parts:
        value = seconds / length
        if value > 0:
            seconds = seconds % length
            time.append('%s%s' % (str(value),
                                  (suffix, (suffix, suffix + 's')[value > 1])[add_s]))
        if seconds < 1:
            break

    return separator.join(time)
