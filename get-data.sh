#!/bin/bash

SRC=${1:-../../factorio-0.15.9/data}
DST=base/

rm -rf ${DST}
mkdir ${DST}
cp ${SRC}/core/lualib/* ${DST}
cp -r ${SRC}/base/{locale,migrations,prototypes,data.lua} ${DST}
cp load.lua ${DST}

( cd ${DST} && patch -p1 < ../data.patch )

