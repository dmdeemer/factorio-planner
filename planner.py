#!/usr/bin/env python3

import json
import sys
import math
    
class Item(object):
    def __init__(self,name):
        self.name = name
        self.made_by = []
        self.used_in = []
        self.qty_req = 0
        self.qty_dep = 0

    def choose_recipe(self,forbidden_recipes=set()):
        for recipe in self.made_by:
            if recipe.name not in forbidden_recipes:
                yield recipe
    
    def __repr__(self):
        return "Item(%s)" % self.name

    all_items = {}
                
    @staticmethod
    def get_or_make_item(name):
        if name not in Item.all_items:
            Item.all_items[name] = Item(name)
        return Item.all_items[name]
    
    
class Recipe(object):
    def __init__(self,json_dict):
        self.name = json_dict['name']
        self.category = json_dict.get('category','crafting')
        recipe_dict = json_dict.get('normal',json_dict)
        self.work = recipe_dict.get('energy_required',0.5)
        self.ingredients = []
        for ingredient in recipe_dict['ingredients']:
            if type(ingredient) is dict:
                item_name = ingredient['name']
                qty = ingredient['amount']
            else:
                item_name, qty = ingredient
            item = Item.get_or_make_item(item_name)
            self.ingredients.append( (item,qty) )
            item.used_in.append(self)
        if 'result' in recipe_dict:
            results = [{'name':recipe_dict['result'],
                        'amount':recipe_dict.get('result_count',1)}]
        else:
            results = recipe_dict['results']
        self.results = []
        for result in results:
            item = Item.get_or_make_item(result['name'])
            self.results.append( (item,result['amount']) )
            item.made_by.append(self)
        self.productivity_allowed = self.name in productivity_recipes

    def __repr__(self):
        return "Recipe(%s)" % self.name

class Machine(object):
    by_crafting_category = {}
    all = []
    
    def __init__(self,json):
        self.name = json["name"]
        self.crafting_categories = json["crafting_categories"]
        self.module_slots = json.get("module_specification",{}).get("module_slots",0)
        self.crafting_speed = json["crafting_speed"]
        self.energy_source_type = json["energy_source"]["type"]
        self.number_needed = 0
        
    @staticmethod
    def best_for_category(category):
        best = None
        for machine in Machine.by_crafting_category.get(category,[]):
            if machine.energy_source_type == 'electric':
                if best is None or machine.crafting_speed > best.crafting_speed:
                    best = machine
        return best

    @staticmethod
    def load_json(machine_json):
        catlist = Machine.by_crafting_category
        for name in machine_json:
            json = machine_json[name]
            if 'crafting_categories' not in json:
                continue
            machine = Machine(json)
            Machine.all.append(machine)
            for category in machine.crafting_categories:
                if category not in catlist:
                    catlist[category] = []
                catlist[category].append(machine)

        
def load_all_json(filename):
    f = open(filename,"r")
    recipes_json, items_json, module_json, machine_json = json.load(f)
    f.close()

    global productivity_recipes
    productivity_recipes = module_json['productivity-module-3']['limitation']
    
    global all_recipes
    all_recipes = {}
        
    for name in recipes_json:
        recipe = Recipe( recipes_json[name] )
        all_recipes[recipe.name] = recipe
    
    Machine.load_json( machine_json )

def main(argv):
    load_all_json("data.json")
    plan_science()

def plan_science():
    outputs = [
        ( 'science-pack-1', 1 ),
        ( 'science-pack-2', 1 ),
        ( 'science-pack-3', 1 ),
        ( 'military-science-pack', 1 ),
        ( 'production-science-pack', 1 ),
        ( 'high-tech-science-pack', 1 ),
        ( 'rocket-part', 0.1 ),
        ( 'satellite', 0.001 ) ]

    global_scalar = 1.0

    forbidden_recipes = set([
        'basic-oil-processing',
        'coal-liquefaction',
        #'advanced-oil-processing',
        'heavy-oil-cracking',
        'light-oil-cracking',
        'solid-fuel-from-petroleum-gas',
        'solid-fuel-from-heavy-oil'])

    machine_abbreviations = {
      "electric-furnace":     "FURN",
      "chemical-plant":       "CHEM",
      "assembling-machine-3": "ASM3",
      "rocket-silo":          "SILO",
      "oil-refinery":         "RFNR",
    }


    X = [ Item.all_items[x[0]] for x in outputs ]
    D = []
    
    recipes_used = set()
    raw_materials = set()
    
    while len(X) > 0:
        item = X.pop(0)
        recipe_found = False
        for recipe in item.choose_recipe( forbidden_recipes ):
            recipes_used.add(recipe)
            recipe_found = True
            ingred_names = []
            for (ingred,qty) in recipe.ingredients:
                if ingred not in D and ingred not in X:
                    X.append(ingred)
                ingred_names.append(ingred.name)
        if not recipe_found:
            raw_materials.add(item)
        D.append(item)
        
    raw_materials = list(raw_materials)
    recipes_used = list(recipes_used)

    max_iter = 10000
    
    recipe_order = []
    items_produced = set(raw_materials)
    while len(recipes_used) > 0:
        max_iter -= 1
        if max_iter < 1:
            print( "Maximum iterations reached" )
            print(repr(recipes_used))
            print(repr(items_produced))
            exit(1)
        recipe = recipes_used.pop(0)
        all_produced = True
        ingreds = set([item for (item,qty) in recipe.ingredients])
        results = set([item for (item,qty) in recipe.results])
        ingreds -= results
        for item in ingreds:
            all_produced = all_produced and (item in items_produced)
        if not all_produced:
            recipes_used.append(recipe)
            continue
        recipe_order.append(recipe)
        for item in results:
            items_produced.add(item)

    recipe_order.reverse()
    
    for (iname,qty) in outputs:
        Item.all_items[iname].qty_req = qty * global_scalar
    
    for recipe in recipe_order:
        machine = Machine.best_for_category( recipe.category )
        if machine is None:
            print( "No machine for " + recipe.category )
            exit(1)

        power_mult = 1.0
        speed_mult = 1.0
        prod_mult = 1.0
        if recipe.productivity_allowed:
            prod_mult += machine.module_slots * 0.10
            speed_mult -= machine.module_slots * 0.15
            power_mult += machine.module_slots * 0.80
        else:
            speed_mult += 0.5 * machine.module_slots
            power_mult += 0.7 * machine.module_slots
            
        # assume 4 speed beacons per machine:
        speed_mult += 0.5 * 4
        power_mult += 0.7 * 4

        batches_to_make = 0;
        for (result,qty_per_batch) in recipe.results:
            qty_to_make = result.qty_req + result.qty_dep
            batches_to_make = max(batches_to_make, qty_to_make / qty_per_batch )
        batches_to_make /= prod_mult
            
            
        crafting_speed = machine.crafting_speed * speed_mult
        machines_needed = math.ceil( batches_to_make * recipe.work / crafting_speed )
            
        machine.number_needed += machines_needed
            
        batches_to_make /= prod_mult
        for (item,qty_input) in recipe.ingredients:
            item.qty_dep += qty_input * batches_to_make
        
        ingred_names = [item.name for (item,qty) in recipe.ingredients]
        prod_mark = "***" if recipe.productivity_allowed else "   "
        
        machine_name = machine.name
        machine_name = machine_abbreviations.get(machine_name,machine_name)
        
        print( "%s %8.2f %3d %s - %s" % (prod_mark, qty_to_make, machines_needed, 
                                         machine_name, recipe.name) )
                                                                        
    for item in raw_materials:
        print( "RAW %8.2f %s" % (item.qty_dep, item.name) )

    for machine in Machine.all:
        if machine.number_needed > 0:
            print( "%d %s" % (machine.number_needed, machine.name) )

if __name__ == '__main__':
    main(sys.argv)