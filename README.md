Work in progress, but WFM :)

* see configuration and comments in __init__.py
* change paths in '''renderer''' (this is the executable called by tirex-backend-manager) 
* cfg contains a example configuration for osm-proxy and vector-tiles.
* test the setup with:

 $sudo -u tirex tirex-master -d [-c ./cfg]
 $sudo -u tirex tirex-backend-manager -d [-c ./cfg]
 $tirex-batch --prio=1 map=proxy z=0 x=0 y=0
 $tirex-batch --prio=1 map=vtm z=0 x=0 y=0
 $find /var/lib/tirex/tiles/
 
The vector-tiles provider is available at:
https://github.com/opensciencemap/TileStache/tree/master/TileStache/OSciMap4
