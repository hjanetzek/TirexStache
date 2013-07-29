'''
Tirex/TileStache backend

based on https://github.com/mdaines/cover/blob/master/vendor/tirex_backend.rb

@author: Hannes Janetzek

'''

import os
import socket
import pipes
import signal
import sys
import logging
import re
import time
import tempfile 

# This must match 'metatile_columns/rows' in tirex.conf 
# and METATILE(x) in render_config.h of mod_tile (8 is hardcoded)
METATILE_SIZE = 2

# layer 'name' defined in tilestache.cfg must match tirex map 'name'
TILESTACHE_CFG = "/home/jeff/workspace/PyTirex/conf/tilestache.cfg"

TILEDIR = "/var/lib/tirex/tiles"

DBG_TILEDIR = "/home/jeff/workspace/PyTirex/tiles"

# As defined by Tirex::MAX_PACKET_SIZE
MAX_PACKET_SIZE = 512

MATCH_PAIRS = re.compile(r"(.*)=(.*)\n")
  
class Tirex:
        
    def __init__(self, backend, testing = False):
        self.metatile_size = METATILE_SIZE
        self.backend = backend

        self.config = {}
        self.config["name"] = os.environ.get("TIREX_BACKEND_NAME")
        self.config["port"] = os.environ.get("TIREX_BACKEND_PORT")
        self.config["syslog_facility"] = os.environ.get("TIREX_BACKEND_SYSLOG_FACILITY")
        self.config["map_configs"] = os.environ.get("TIREX_BACKEND_MAP_CONFIGS")
        self.config["alive_timeout"] = os.environ.get("TIREX_BACKEND_ALIVE_TIMEOUT")
        self.config["pipe_fileno"] = os.environ.get("TIREX_BACKEND_PIPE_FILENO")
        self.config["socket_fileno"] = os.environ.get("TIREX_BACKEND_SOCKET_FILENO")
        self.config["debug"] = os.environ.get("TIREX_BACKEND_DEBUG")
        
        sys.stderr.write(str(self.config))
        
        self.debug = testing or self.config["debug"]  == "1"
        
        if testing:
            self.tiledir = DBG_TILEDIR
            return

        self.tiledir = TILEDIR
        self.parent_fd = int(self.config["pipe_fileno"])
        self.running = True
        self.timeout = int(self.config["alive_timeout"])
        

    def run(self):
        def stop(signum, frame):
            self.running = False
            print "stopping"
            sys.exit(0)
        
        if (self.config["socket_fileno"] != None):
            sys.stderr.write("receive on fd %s" %  self.config["socket_fileno"]);
            fd = int(self.config["socket_fileno"])
            sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_DGRAM)
        else:
            sys.stderr.write("receive on port %s" %  self.config["port"]);
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            port = int(self.config["port"])
            sock.bind(("127.0.0.1", port))
            
        signal.signal(signal.SIGHUP, stop) 
        signal.signal(signal.SIGINT, stop) 

        sock.settimeout(self.timeout)
        
        while self.running:
            
            # send alive message to backend manager
            os.write(self.parent_fd, "alive")
            
            try:
                data, addr = sock.recvfrom(MAX_PACKET_SIZE)
            except socket.timeout:
                continue
            except socket.error, e:
                sys.stderr.write("recv: %s" %e);
                continue
            
            response = self.process_message(data)
            sock.sendto(response, addr)
            
            
    def process_message(self, message):
        if self.debug:
            sys.stderr.write(">\n%s\n" %message)

        request = deserialize_msg(message)
        
        try:
            if request["type"] == "metatile_render_request":
                response = self.process_render_request(request)
            else:
                raise Exception("Unknown request type: %s" % request["type"])
        except Exception, e:
            response = { "id" : request["id"], 
                        "result": "fail", 
                        "errmsg" : e }
        
        response = serialize_msg(response)
        sys.stderr.write("<\n%s\n" %str(response))
        return response
    
    def process_render_request(self, request):
        layer = request["map"]
        x = int(request["x"])
        y = int(request["y"])
        z = int(request["z"])
        
        tiledir =  "%s/%s" %(self.tiledir, layer)
        filename = "%s/%s" % (tiledir, xyz_to_path(x, y, z) + ".meta")
        
        start = time.time()
        
        try:
            # in-memory temp file for 512k
            tmp = tempfile.SpooledTemporaryFile(1024 * 512) 
            
            self.backend.write(layer, x, y, z, self.metatile_size, tmp)
            
            dirname = os.path.dirname(filename)
            if not os.path.exists(dirname):
                try:
                    os.makedirs(dirname)
                except OSError, e:
                    sys.stderr.write("could not create %s, %s\n" %(dirname, e))
                    pass
                
            tmp.seek(0)
            
            with open(filename, 'w') as f:
                f.write(tmp.read())
                
        finally:
            tmp.close()

        os.chmod(filename, 0644)

        elapsed = time.time() - start
        
        if self.debug:
            sys.stderr.write("time: %f, %d bytes - %s -\n" %(elapsed, os.path.getsize(filename), filename))
                    
        return { "type": "metatile_render_request",
                 "result": "ok",
                 "id": request["id"],
                 "render_time": str(int(elapsed)) }
        

        

def serialize_msg(msg):
    return '\n'.join(["%s=%s" % (k, v) for (k, v) in msg.iteritems()])
    
def deserialize_msg(string):
    return dict(MATCH_PAIRS.findall(string))
    
def xyz_to_path(x, y, z):
    hashes = []
    for _ in xrange(0, 5):
        hashes.append(((x & 0x0f) << 4) | (y & 0x0f))
        x >>= 4
        y >>= 4

    return "%u/%s" % (z, "%u/%u/%u/%u/%u" % tuple(reversed(hashes)))


if __name__ == '__main__':
    import Backend
    
    b = Backend.TileStacheBackend(TILESTACHE_CFG)
    
    # not started from tirex: just testing layers
    if os.environ.get("TIREX_BACKEND_NAME") == None:
        t = Tirex(b, True)
        request = {'map': 'osm', 'prio': '1', 
                   'y': '0', 'x': '0', 'z': '2', 
                   'type': 'metatile_render_request', 
                   'id': '1375054837_19944984'}
        t.process_render_request(request)
        exit(0)
    
    t = Tirex(b)
    t.run()    
    
    
