#!/usr/bin/sh

course_dir=$1

for i in $1/*; do 
    n=$(echo $i | sed -e 's/.*fri_kpov\///')
    o=$(readlink $i/preparation | sed -e 's/.*tasks\///')
    ./add_task.py $i/preparation kpov_2019/$n-preparation-$o; 
done
