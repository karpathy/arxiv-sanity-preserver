#!/bin/bash

#create user based on owner and group of data directory
SUID=$(stat -c %u data)
SGID=$(stat -c %g data)
if [ ! "$SUID" == "0" ]; then
  groupadd -g $SGID sanity
  useradd -u $SUID -g $SGID sanity
  SUSER=sanity
else
  SUSER=root
fi

echo Changing to $SUSER
exec sudo -u $SUSER /bin/bash - << EOF
mkdir -p /usr/src/app/data/{pdf,txt,thumbs,tmp}

[ -f data/secret_key.txt ] || head -c 1024 < /dev/urandom > data/secret_key.txt
[ -f data/as.db ] || sqlite3 as.db < schema.sql

exec $@
EOF
