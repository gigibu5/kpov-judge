#!/bin/sh

if [ $# -lt 2 ]; then
  echo "usage: ${0} course_name course_dir"
  exit 1
fi

course_name=$1
course_dir=$2



for i in ${course_dir}/*; do 
    n=$(basename $i)
    o=$(readlink ${i}/preparation | sed -e 's/.*tasks\///')
    ./add_task.py "${i}/preparation" "${course_name}/$n-preparation-$o"; 
done
