#!/bin/bash
# usage: run_chunks.sh <which> <start> <end> <tag> ; fresh browser per 20k chunk so the tab never runs out of memory
which=$1; s=$2; e=$3; tag=$4
for ((i=s; i<e; i+=20000)); do
  n=$(( e-i < 20000 ? e-i : 20000 ))
  f=tests/out/rt_${which}_${tag}_$i.jsonl
  if [ -f "$f" ] && [ "$(wc -l < $f)" -ge "$n" ]; then continue; fi
  timeout 1500 python3 tests/roundtrip.py $which $i $n $f > tests/out/log_${tag}.txt 2>&1 || echo "chunk $i failed" >> tests/out/log_${tag}_fail.txt
done
echo ALLDONE >> tests/out/log_${tag}.txt
