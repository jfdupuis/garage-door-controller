from garage_controller import Controller

import json
import syslog
import time
import subprocess
import sys
import re

from twisted.cred import checkers, portal
from twisted.internet import task
from twisted.internet import reactor
from twisted.internet import ssl
from twisted.web import server
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory
from twisted.web.resource import Resource, IResource
from twisted.web.static import File
from zope.interface import implementer


@implementer(portal.IRealm)
class HttpPasswordRealm(object):
    def __init__(self, myresource):
        self.myresource = myresource

    def requestAvatar(self, user, mind, *interfaces):
        if IResource in interfaces:
            return (IResource, self.myresource, lambda: None)
        raise NotImplementedError()


class GarageDoorServer:
    def __init__(self, controller, config):
        self.controller = controller
        self.config = config
        self.updateHandler = UpdateHandler(self.controller)

    def get_config_with_default(self, config, param, default):
        if not config:
            return default
        if param not in config:
            return default
        return config[param]

    def run(self):
        task.LoopingCall(self.controller.status_check).start(0.5)
        root = File('www')
        root.putChild(b'st', StatusHandler(self))
        root.putChild(b'upd', self.updateHandler)
        root.putChild(b'cfg', ConfigHandler(self.controller))
        root.putChild(b'upt', UptimeHandler(self))

        if not self.config['site']['monitor_only']:
            if self.config['config']['use_auth']:
                click_handler = ClickHandler(self.controller)
                username = self.config['site']['username']
                password = self.config['site']['password'].encode('utf-8')
                args = {username: password}
                checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(
                    **args)
                realm = HttpPasswordRealm(click_handler)
                p = portal.Portal(realm, [checker])
                credentialFactory = BasicCredentialFactory(
                    "Garage Door Controller")
                protected_resource = HTTPAuthSessionWrapper(
                    p, [credentialFactory])
                root.putChild(b'clk', protected_resource)
            else:
                root.putChild(b'clk', ClickHandler(self.controller))
        site = server.Site(root)

        if not self.get_config_with_default(
                self.config['config'], 'use_https', False):
            # @UndefinedVariable
            reactor.listenTCP(self.config['site']['port'], site)
            reactor.run()  # @UndefinedVariable
        else:
            sslContext = ssl.DefaultOpenSSLContextFactory(
                self.config['site']['ssl_key'], self.config['site']['ssl_cert'])
            reactor.listenSSL(self.config['site']['port_secure'],
                              site, sslContext)  # @UndefinedVariable
            reactor.run()  # @UndefinedVariable


class ClickHandler(Resource):
    isLeaf = True

    def __init__(self, controller):
        Resource.__init__(self)
        self.controller = controller

    def render_GET(self, request):
        door = bytes.decode(request.args[b'id'][0])
        self.controller.toggle(door)
        return b'OK'


class StatusHandler(Resource):
    isLeaf = True

    def __init__(self, controller):
        Resource.__init__(self)
        self.controller = controller

    def render(self, request):
        door = request.args['id'][0]
        for d in self.controller.doors:
            if (d.id == door):
                return d.last_state
        return ''


class ConfigHandler(Resource):
    isLeaf = True

    def __init__(self, controller):
        Resource.__init__(self)
        self.controller = controller

    def render_GET(self, request):
        request.setHeader('Content-Type', 'application/json')
        return str.encode(json.dumps([(d.id, d.name, d.last_state, d.last_state_time)
                                      for d in self.controller.doors]))


class UptimeHandler(Resource):
    isLeaf = True

    def __init__(self, controller):
        Resource.__init__(self)
        self.uptime_pattern = re.compile(b"([:.\\w]+)")

    def getUptime(self):
        uptime = subprocess.check_output(['uptime']).strip()
        uptime = uptime.split(b",")[0]
        result = self.uptime_pattern.findall(uptime)
        return result[2]

    def render_GET(self, request):
        request.setHeader('Content-Type', 'application/json')
        uptime = self.getUptime()
        return json.dumps("Uptime: %s" % uptime)


class UpdateHandler(Resource):
    isLeaf = True

    def __init__(self, controller):
        Resource.__init__(self)
        self.delayed_requests = []
        self.controller = controller

    def handle_updates(self):
        for request in self.delayed_requests:
            updates = self.controller.get_updates(request.lastupdate)
            if updates != []:
                self.send_updates(request, updates)
                self.delayed_requests.remove(request)

    def format_updates(self, request, update):
        response = json.dumps(
            {'timestamp': int(time.time()), 'update': update})
        if hasattr(request, 'jsonpcallback'):
            return str.encode(request.jsonpcallback + '(' + response + ')')
        else:
            return str.encode(response)

    def send_updates(self, request, updates):
        request.write(self.format_updates(request, updates))
        request.finish()

    def render_GET(self, request):

        # set the request content type
        request.setHeader('Content-Type', 'application/json')

        # set args
        args = request.args

        # set jsonp callback handler name if it exists
        if b'callback' in args:
            request.jsonpcallback = args[b'callback'][0]

        # set lastupdate if it exists
        if b'lastupdate' in args:
            request.lastupdate = float(args[b'lastupdate'][0])
        else:
            request.lastupdate = 0

        # Can we accommodate this request now?
        updates = self.controller.get_updates(request.lastupdate)
        if updates != []:
            return self.format_updates(request, updates)

        request.notifyFinish().addErrback(
            lambda x: self.delayed_requests.remove(request))
        self.delayed_requests.append(request)

        # tell the client we're not done yet
        return server.NOT_DONE_YET


def main(args):
    syslog.openlog('garage_controller')

    config_filename = 'config.json'
    if len(sys.argv) == 2:
        config_filename = sys.argv[1]

    syslog.syslog('Config file: %s' % config_filename)
    config_file = open(config_filename)
    config = json.load(config_file)
    config_file.close()

    controller = Controller(config)
    garage_server = GarageDoorServer(controller, config)
    controller.set_update_handler(garage_server.updateHandler)
    garage_server.run()


if __name__ == '__main__':
    main(sys.argv[1:])
