import asynctest
import asyncio
from unittest.mock import Mock, patch, call

from beka.peering import Peering

class RouteCatcher(object):
    def __init__(self):
        self.route_updates = []

    def handle(self, route_update):
        self.route_updates.append(route_update)

class FakeStateMachine(object):
    def __init__(self):
        self.output_messages = asyncio.Queue()
        self.route_updates = asyncio.Queue()

class FakeSocket(object):
    reader = None

    def __init__(self):
        pass

    def makefile(self, *args, **kwargs):
        return None

class FakeChopper(object):
    def __init__(self):
        pass

class PeeringTestCase(asynctest.TestCase):
    def setUp(self):
        self.route_catcher = RouteCatcher()
        self.state_machine = FakeStateMachine()
        self.peering = Peering(
            state_machine=self.state_machine,
            peer_address="1.2.3.4:179",
            socket=FakeSocket(),
            route_handler=self.route_catcher.handle
        )
        self.peering.chopper = FakeChopper()

    async def test_print_route_updates(self):
        fake_route_update = "FAKE ROUTE UPDATE"
        self.state_machine.route_updates.put_nowait(fake_route_update)
        task = asyncio.ensure_future(self.peering.print_route_updates())
        for _ in range(10):
            await asyncio.sleep(0)
            if self.route_catcher.route_updates:
                break
        self.assertEqual(len(self.route_catcher.route_updates), 1)
        self.assertEqual(self.route_catcher.route_updates[0], fake_route_update)
        task.cancel()

    async def test_run_starts_threads(self):
        task = asyncio.ensure_future(self.peering.run())
        await asyncio.sleep(0)
        self.assertEqual(len(self.peering.tasks), 4)
        self.peering.shutdown()
        await task
