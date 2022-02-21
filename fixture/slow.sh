#!/bin/bash

count=1
while [ $count -lt 200 ]
do
  stdbuf -oL date
  sleep 1
  count=`expr $count + 1`
done
