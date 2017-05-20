# factorio-planner
Calculates recipes, quantities, machines, and raw inputs for a Factorio factory

## Dependencies

A LUA interpreter and a Python 3.x interpreter.

## Usage
1) Use the get-data.sh script to get Factorio's base mod data from an 
existing Factorio install, and convert it into JSON format:

    ./get-data.sh <path-to-factorio>

(This involves merging several directories into one and applying a simple 
patch to the data.  It works in version 0.15.9 and 0.15.12, other versions 
untested)

2) Run planner.py

**planner.py** uses the previously-generated **data.json** file for lists 
of recipes, modules, and machines, and plans the number of machines needed 
for your factory.  Currently, the factory outputs are hard-coded: Each 
science at 1/s and Rocket parts at 1/10s, plus a satellite every 1000s.  
Also hardcoded is the intention to use productivity 3 modules wherever
possible, and to have 4 beacons affecting each assembler

## Known issues

* Oil isn't calculated properly yet.  A possible workaround is to add all 
oil recipes to the prohibited list, which will convert oil products to raw 
inputs.  (You will need to add them to the hardcoded stack-size list.  
What is the stack size of a fluid, you ask?  2500.)

* There is no user-interface yet
