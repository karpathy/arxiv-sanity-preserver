#!/bin/bash
sudo mount /dev/nvme0n1 /data; sudo service mongod start; source ~/env/bin/activate; cd
 ~/arxiv-sanity-preserver/; python twitter_daemon.py 2>&1 1>/dev/null &; python serve.py --prod --port 8080;
 
