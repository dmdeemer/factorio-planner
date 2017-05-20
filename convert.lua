defines = {}
defines.direction = {}
defines.direction.north = "N"
defines.direction.south = "S"
defines.direction.east = "E"
defines.direction.west = "W"

require "dataloader"
require "data"
json = require "json"

machines = {}
for k,v in pairs( data.raw["assembling-machine"] ) do machines[k] = v end
for k,v in pairs( data.raw["rocket-silo"] ) do machines[k] = v end
for k,v in pairs( data.raw["furnace"] ) do machines[k] = v end


print( json.encode( { data.raw.recipe, data.raw.item, data.raw.module, machines } ) )
