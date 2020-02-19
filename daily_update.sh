#!/bin/bash
export WORKER_ID=i-0b8a8a78e1f18b2c5
aws ec2 start-instances --region eu-central-1 --instance-ids "$WORKER_ID"
# how to find WORKER_DNS out by instance id?
export WORKER_DNS=ubuntu@ec2-3-125-115-48.eu-central-1.compute.amazonaws.com 
source ~/env/bin/activate; python OAI_seed_db.py --from-date '2020-02-01'; 
python download_pdfs.py  # how to set from-date?

# For PDF to txt conversion 
# fix imagemagic policy issue preventing creation of the thumbnails
# https://stackoverflow.com/a/52863413
# MANUALLY add 
# <policy domain="module" rights="read|write" pattern="{PS,PDF,XPS}" /> 
# to /etc/ImageMagick-6/policy.xml
# on webserver where archive-sanity-preserver is installed.

function create_txt_and_thumbs {
pdfpath=/data/pdf #/data/pdf/2002/2002.01868.pdf
filename="$1"
#echo "$filename"
shortpath=${1#/*pdf} #/2002/2002.01868.dir
dir_fileroot=${shortpath%.pdf} # /2002/2002.01868

[ ! -e /data/txt"$dir_fileroot".txt ] && ( (timeout 120 pdftotext $filename \
/data/txt"$dir_fileroot".txt) || touch /data/txt"$dir_fileroot".txt);

[ ! -e /data/jpg"$dir_fileroot".jpg ] && (timeout 120 convert $filename[0-7] \
-thumbnail x156 "${filename%.*}".png; \
montage -mode concatenate -quality 80 \
-tile x1 "${filename%.*}"*.png /data/jpg"$dir_fileroot".jpg \
|| ln -s ~/arxiv-sanity-preserver/pdf_failed_conversion_to.jpg \
/data/jpg"$dir_fileroot".jpg; \
rm "${filename%.*}"*.png );

}
export -f create_txt_and_thumbs

cd /data/pdf; find ./ -type d -exec sh -c 'mkdir -p /data/txt/${1#"./"}; \
mkdir -p /data/jpg/${1#"./"}; ' sh {} \;

time find /data/pdf/ -type f -name "*.pdf"|parallel create_txt_and_thumbs {}

aws s3 sync /data/txt s3://abbrivia.private-arxiv/jpg_txt/ \
	--exclude "*" --include "*.txt" &

while [ $(aws ec2 start-instances --region eu-central-1 \
--instance-ids "$WORKER_ID" --output text|grep "CURRENTSTATE" \
|cut -f3) != 'running' ];
do sleep 60;
done;

# copy all txt files to the processing instance
# setup its ephemeral disk /data if lost 
#lsblk
ssh "$WORKER_DNS" << SSH
ls /data || ( sudo mkfs -t xfs /dev/xvdb && sudo mkdir /data; \
sudo mount /dev/xvdb /data; sudo chown ubuntu.ubuntu /data )
mkdir -p /data/txt /data/pickles 
SSH
time rsync -r --size-only --progress /data/txt/ "$WORKER_DNS":/data/txt
scp /home/ubuntu/arxiv-sanity-preserver/db.p \
"$WORKER_DNS":/home/ubuntu/arxiv-sanity-preserver/
#rsync -havz --progress /home/ubuntu/arxiv-sanity-preserver/ "$WORKER_DNS":/home/ubuntu/arxiv-sanity-preserver/
time ssh "$WORKER_DNS" << SSH
source /home/ubuntu/env/bin/activate; cd /home/ubuntu/arxiv-sanity-preserver/; \
python analyze.py;
SSH
for file in sim_dict.p tfidf.p tfidf_meta.p; do scp \
""$WORKER_DNS":/data/pickles/$file" /data/pickles/ ; done;
#aws ec2 stop-instances --region eu-central-1 --instance-ids "$WORKER_ID" 
source ~/env/bin/activate; cd ~/arxiv-sanity-preserver/; python buildsvm.py; \
python make_cache.py;
