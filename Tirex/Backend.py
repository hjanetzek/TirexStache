import os
import struct
import array
import Queue
import threading
import time

from TileStache import parseConfigfile
from ModestMaps.Core import Coordinate

class TileStacheBackend:
    
    def __init__(self, configFile):
        self.config = parseConfigfile(configFile)
        self.num_threads = 4
    
    def write(self, tile_layer, tile_x, tile_y, tile_z, meta_size, out):
        
        ##layer = self.config.layers["osm"]
        layer = self.config.layers[tile_layer]
        
        if layer == None:
            raise Exception("layer not configured %s" %tile_layer)
                  
        # 4 byte magic
        out.write(struct.pack('4s', "META"))
        
        num_tiles = meta_size * meta_size
        
        # 16 byte
        out.write(struct.pack('4i', num_tiles, tile_x, tile_y, tile_z))
        
        # Record the position where the table of contents will be written
        toc_position = out.tell()
        
        # Seek to the position of the first tile
        out.seek(8 * num_tiles, os.SEEK_CUR)
        
        # Write the tiles, storing positions and sizes in the table of contents
        toc = array.array('i')

        if hasattr(layer.provider, 'extension'):
            extension = layer.provider.extension        
        else:
            extension = "png"

        mimetype, filetype = layer.getTypeByExtension(extension)
        
        offset = out.tell()
        
        zmax = 1 << tile_z
        
        queue = Queue.Queue()
        tiles = []

        for x in xrange(0, meta_size):
            for y in xrange(0, meta_size):
                
                # NB: most awkward param order.
                t = JobItem(Coordinate(tile_y + y, tile_x + x,tile_z))
                tiles.append(t)
                
                if (t.coord.column < zmax and t.coord.row < zmax):
                    queue.put(t)
                    
        
        threads = []
        for _ in range(self.num_threads):
            t = JobThread(queue, layer)
            t.setDaemon(True)
            t.start()
            threads.append(t)

        # allows to cancel via SIGINT, needed here?         
        while not queue.empty():
            time.sleep(1.0)
        
        queue.join()
        
        for t in tiles:
            tile_position = offset
            
            if t.data != None:
                t.data.save(out, filetype)
                offset = out.tell()

            toc.append(tile_position)
            toc.append(offset - tile_position)
                
        out.seek(toc_position)
        out.write(toc.tostring())
                
        
class JobThread(threading.Thread):
    def __init__(self, queue, layer):
        threading.Thread.__init__(self)
        self.queue = queue
        self.layer = layer
        self.initial = queue.qsize()              
        
    def run(self):
        l = self.layer
              
        while True != None:
            try:   
                item = self.queue.get(False)
            except Queue.Empty: 
                break
            
            try:
                item.data = l.provider.renderTile(l.dim, l.dim, l.projection.srs, item.coord)
            finally:
                self.queue.task_done()
            
class JobItem:
    def __init__(self, coord):
        self.coord = coord
        self.data = None
         
