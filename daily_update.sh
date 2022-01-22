#!/bin/bash
# add to crontab -e 
# 16 04 * * * . /home/ubuntu/.profile; /home/ubuntu/arxiv-sanity-preserver/daily_update.sh 2>>/data/daily_update.log
# the single dot is the command to source profile
export awscli=aws # installed into the virualenv with pip install aws --update
source /home/ubuntu/env/bin/activate; 
cd /home/ubuntu/arxiv-sanity-preserver/;
python /home/ubuntu/arxiv-sanity-preserver/OAI_seed_db.py --from-date '2020-07-01' --set "physics:cond-mat"; 
#python OAI_seed_db.py --from-date '2020-02-01' --set "cs"; 
python /home/ubuntu/arxiv-sanity-preserver/download_pdfs.py  # how to set from-date?

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
|| ln -s /home/ubuntu/arxiv-sanity-preserver/pdf_failed_conversion_to.jpg \
/data/jpg"$dir_fileroot".jpg; \
rm "${filename%.*}"*.png );

}
export -f create_txt_and_thumbs

cd /data/pdf; find ./ -type d -exec sh -c 'mkdir -p /data/txt/${1#"./"}; \
mkdir -p /data/jpg/${1#"./"}; ' sh {} \;

time find /data/pdf/ -type f -name "*.pdf"|parallel create_txt_and_thumbs {}

#"$awscli" s3 sync /data/txt s3://abbrivia.private-arxiv/jpg_txt/ \
#	--exclude "*" --include "*.txt" --include "*.jpg" &

#"$awscli" s3 sync s3://abbrivia.private-arxiv/jpg_txt /data/jpg/  \
#	--exclude "*" --include "*.jpg"
#"$awscli" s3 sync s3://abbrivia.private-arxiv/jpg_txt /data/txt/  \
#	--exclude "*" --include "*.txt"

export WORKER_ID=i-0b8a8a78e1f18b2c5
while ! [ "x$("$awscli" ec2 start-instances --region eu-central-1 \
--instance-ids "$WORKER_ID" --output text|grep "CURRENTSTATE" \
|cut -f3)" = "xrunning" ];
do 
	echo "$WORKER_ID not running"
	sleep 60;
done;
export WORKER_IP="$("$awscli" ec2 describe-instances --output text \
	--region eu-central-1 --instance-ids "$WORKER_ID" \
	--query 'Reservations[*].Instances[*].PublicIpAddress' )"
export WORKER_CONNECT='ubuntu@'"$WORKER_IP"
echo "$WORKER_CONNECT"

# copy all txt files to the processing instance
# setup its ephemeral disk /data if lost 
#lsblk
ssh-keygen -f "/home/ubuntu/.ssh/known_hosts" -R "$WORKER_IP"
ssh -o "StrictHostKeyChecking no" "$WORKER_CONNECT" << SSH
if findmnt --source /dev/xvdb --target /data >/dev/null && [ "x$(stat --format '%U' '/data/txt')" = "xubuntu" ] ;
then 
echo "/data/txt is mounted to /dev/xvdb owned by ubuntu, proceeding";
else 
echo "resetting /data"; 
sudo mkfs -t xfs /dev/xvdb; sudo mkdir -p /data; 
sudo mount /dev/xvdb /data; sudo chown ubuntu.ubuntu /data; 
mkdir -p /data/{pdf,txt,jpg}/{00..20}{01..12}; 
mkdir -p /data/{pdf,txt,jpg}/{90..99}{01..12}; 
mkdir -p /data/pickles/; 
fi
SSH
#TODO add --files-from=FILE       read list of source-file names from FILE
#time rsync -zr --ignore-existing --size-only --progress /data/txt/ "$WORKER_CONNECT":/data/txt
time tar -cf - /data/txt/ |ssh "$WORKER_CONNECT" 'cd / && tar xBf -'

scp /home/ubuntu/arxiv-sanity-preserver/{db.p,as.db} "$WORKER_CONNECT":/home/ubuntu/arxiv-sanity-preserver/

#rsync -havz --progress /home/ubuntu/arxiv-sanity-preserver/ "$WORKER_CONNECT":/home/ubuntu/arxiv-sanity-preserver/
time ssh "$WORKER_CONNECT" << SSH
source /home/ubuntu/env/bin/activate; cd /home/ubuntu/arxiv-sanity-preserver/; \
python analyze.py; 
python buildsvm.py; 
python make_cache.py;
SSH

scp ""$WORKER_CONNECT":/data/pickles/*" /data/pickles/

scp ""$WORKER_CONNECT":/home/ubuntu/arxiv-sanity-preserver/{db2.p,serve_cache.p}" /home/ubuntu/arxiv-sanity-preserver/

"$awscli" ec2 stop-instances --region eu-central-1 --instance-ids "$WORKER_ID" 
