#!/bin/bash
sudo mount /dev/nvme0n1 /data; sudo service mongod start; source ~/env/bin/activate; cd
 ~/arxiv-sanity-preserver/; python serve.py --prod --port 8080;
