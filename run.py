import asyncio
import sys
import yaml
import signal

from beka.beka import Beka

def printmsg(msg):
    sys.stderr.write("%s\n" % msg)
    sys.stderr.flush()

class Server(object):
    def __init__(self):
        self.peering_hosts = []
        self.bekas = []

    async def run(self):
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self.signal_handler)
        tasks = []

        with open("beka.yaml") as file:
            config = yaml.load(file.read())
        for router in config["routers"]:
            printmsg("Starting Beka on %s" % router["local_address"])
            beka = Beka(
                router["local_address"],
                router["bgp_port"],
                router["local_as"],
                router["router_id"],
                self.peer_up_handler,
                self.peer_down_handler,
                self.route_handler,
                self.error_handler
            )
            for peer in router["peers"]:
                beka.add_neighbor(
                    "passive",
                    peer["peer_ip"],
                    peer["peer_as"],
                )
            if "routes" in router:
                for route in router["routes"]:
                    beka.add_route(
                        route["prefix"],
                        route["next_hop"]
                    )
            self.bekas.append(beka)
            tasks.append(asyncio.ensure_future(beka.run()))

        await asyncio.wait(tasks)
        printmsg("All tasks gone, exiting")

    def signal_handler(self):
        printmsg("[SIGINT] Shutting down")
        self.shutdown()

    def shutdown(self):
        for beka in self.bekas:
            printmsg("Shutting down Beka %s" % beka)
            beka.shutdown()

    def peer_up_handler(self, peer_ip, peer_as):
        printmsg("[Peer up] %s %d" % (peer_ip, peer_as))

    def peer_down_handler(self, peer_ip, peer_as):
        printmsg("[Peer down] %s %s" % (peer_ip, peer_as))

    def error_handler(self, msg):
        printmsg("[Error] %s" % msg)

    def route_handler(self, route_update):
        if route_update.is_withdraw:
            printmsg("[Route handler] Route removed: %s" % route_update)
        else:
            printmsg("[Route handler] New route received: %s" % route_update)

if __name__ == "__main__":
    server = Server()
    asyncio.get_event_loop().run_until_complete(server.run())
