#!/bin/bash
mv patch patch.orig
diff -U10 base.orig base > patch

