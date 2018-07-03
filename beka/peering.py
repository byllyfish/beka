import asyncio

from .chopper import Chopper
from .event import EventTimerExpired, EventMessageReceived
from .bgp_message import BgpMessage, BgpMessageParser, BgpMessagePacker
from .route import RouteAddition, RouteRemoval
from .error import SocketClosedError, IdleError

import time

class Peering(object):
    def __init__(self, state_machine, peer_address, socket, route_handler, error_handler=None):
        self.state_machine = state_machine
        self.peer_address = peer_address[0]
        self.peer_port = peer_address[1]
        self.socket = socket
        self.route_handler = route_handler
        self.error_handler = error_handler
        self.start_time = int(time.time())

    def uptime(self):
        return int(time.time()) - self.start_time

    async def run(self):
        self._shutdown_future = asyncio.get_event_loop().create_future()
        self.chopper = Chopper(self.socket.reader)
        self.parser = BgpMessageParser()
        self.packer = BgpMessagePacker()
        self.state_machine.open_handler = self.open_handler
        self.tasks = []

        self.tasks.append(asyncio.ensure_future(self.send_messages()))
        self.tasks.append(asyncio.ensure_future(self.print_route_updates()))
        self.tasks.append(asyncio.ensure_future(self.kick_timers()))
        self.tasks.append(asyncio.ensure_future(self.receive_messages()))

        await self._shutdown_future

        for task in self.tasks:
            task.cancel()
        await self.empty_message_queue()

    def open_handler(self, capabilities):
        self.parser.capabilities = capabilities
        self.packer.capabilities = capabilities

    async def receive_messages(self):
        while True:
            try:
                message_type, serialised_message = await self.chopper.next()
            except SocketClosedError as e:
                if self.error_handler:
                    self.error_handler("Peering %s: %s" % (self.peer_address, e))
                self.shutdown()
                break
            message = self.parser.parse(message_type, serialised_message)
            event = EventMessageReceived(message)
            tick = int(time.time())
            try:
                self.state_machine.event(event, tick)
            except IdleError as e:
                if self.error_handler:
                    self.error_handler("Peering %s: %s" % (self.peer_address, e))
                self.shutdown()
                break

    async def send_messages(self):
        while True:
            message = await self.state_machine.output_messages.get()
            self.socket.send(self.packer.pack(message))

    async def empty_message_queue(self):
        while self.state_machine.output_messages.qsize():
            message = await self.state_machine.output_messages.get()
            self.socket.send(self.packer.pack(message))

    async def print_route_updates(self):
        while True:
            route_update = await self.state_machine.route_updates.get()
            self.route_handler(route_update)

    async def kick_timers(self):
        while True:
            await asyncio.sleep(1)
            tick = int(time.time())
            try:
                self.state_machine.event(EventTimerExpired(), tick)
            except IdleError as e:
                if self.error_handler:
                    self.error_handler("Peering %s: %s" % (self.peer_address, e))
                self.shutdown()
                break

    def shutdown(self):
        self._shutdown_future.set_result(0)

