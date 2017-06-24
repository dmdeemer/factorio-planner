#!/usr/bin/env python3

import json
import sys
import math
import numpy as np

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
                return recipe

    stack_sizes = {
        'iron-ore':50,
        'copper-ore':50,
        'coal':50,
        'stone':50,
        'water':2500,
        'crude-oil':2500,
        'heavy-oil':2500,
        'light-oil':2500,
        'petroleum-gas':2500,
        'steam':2500
    }

    def stack_size(self):
        # We aren't loading this from the JSON, but
        # we only have two stack sizes we care about.
        #  Ores are 50, fluids are 2500 (10 barrels)
        if self.name in Item.stack_sizes:
            return Item.stack_sizes[self.name]
        print( "Don't know stack size for " + self.name )
        exit(1)

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
        self.productivity_allowed = self.name in Module.productivity_recipes
        self.prepared = False
        
    all = {}

    def prepare(self):
        if self.prepared:
            return
        self.prepared = True
        
        self.machine = Machine.best_for_category( self.category )
        if self.machine is None:
            print( "No machine for " + self.category )
            exit(1)

        prod3_module = Module.all['productivity-module-3']
        speed3_module = Module.all['speed-module-3']

        self.effects = Effects()
        if self.productivity_allowed:
            self.effects.apply_module( prod3_module, self.machine.module_slots )
        #else:
        #    self.effects.apply_module( speed3_module, self.machine.module_slots )

        # assume 4 speed beacons per machine:
        num_beacons = 8 if (self.category == 'smelting') else 4
        self.effects.apply_module( speed3_module, num_beacons )

        self.effects.clip_mults()


    def compute(self):
        if( len(self.results) > 1 ):
            print( "Error, recipes with more than one result should be CompoundRecipes" )
            exit(1)
            
        self.prepare()
        
        (result,qty_per_batch) = self.results[0]
        qty_to_make = result.qty_req + result.qty_dep
        batches_to_make = qty_to_make / (qty_per_batch * self.effects.prod_mult)

        for (item,qty_input) in self.ingredients:
            item.qty_dep += qty_input * batches_to_make

        (machines_needed, machines_needed_1x) = self.calc_machines_needed(batches_to_make)
        self.show(machines_needed, machines_needed_1x)
        self.machine.number_needed += machines_needed

    def calc_machines_needed(self,batches_to_make):
        crafting_speed = self.machine.crafting_speed * self.effects.speed_mult
        machines_needed = math.ceil( batches_to_make * self.work / crafting_speed )
        machines_needed_1x = batches_to_make * self.work
        return (machines_needed, machines_needed_1x)

    def show(self,machines_needed,machines_needed_1x):
        prod_mark = "***" if self.productivity_allowed else "   "
        machine_name = self.machine.abbreviation

        print( "%s (%8.2f) %3d %s - %s" % (prod_mark, machines_needed_1x, machines_needed,
                                        machine_name, self.name) )
    
    @staticmethod
    def load_json( recipes_json ):
        for name in recipes_json:
            recipe = Recipe( recipes_json[name] )
            Recipe.all[recipe.name] = recipe


    def __repr__(self):
        return "Recipe(%s)" % self.name

class CompoundRecipe(Recipe):
    def __init__(self,name,recipes):
        self.name = name
        self.recipes = recipes
        Recipe.all[name] = self
        self.inputs = set()
        self.outputs = set()
        for recipe in recipes:
            self.inputs.update( {item for (item,qty) in recipe.ingredients} )
            self.outputs.update( {item for (item,qty) in recipe.results} )
        self.inputs -= self.outputs
        
        for item in self.inputs:
            item.used_in.append(self)
        for item in self.outputs:
            item.made_by.append(self)
        
        self.ingredients = [(item,0) for item in self.inputs]
        self.results = [(item,0) for item in self.outputs]
    
    def compute(self):
        idx = 0
        item_map = {}
        for recipe in self.recipes:
            recipe.prepare()
            for (item,qty) in recipe.ingredients:
                if item.name not in item_map:
                    item_map[item.name] = idx
                    idx+=1
            for (item,qty) in recipe.results:
                if item.name not in item_map:
                    item_map[item.name] = idx
                    idx+=1
        
        N = len(self.inputs) + len(self.recipes)
        if N != idx:
            print( "Error: CompoundRecipe %s is %sconstrained" % (self.name, "under" if N < idx else "over") )
            print( idx )
            print( self.inputs )
            print( self.recipes )
            
            exit(1)
            
        # Linear equation is M*x = b
        #   M is recipes (and pseudo-recipes for inputs)
        #   x is number of batches of each recipe
        #   b is desired outputs
        M = np.matrix(np.zeros((N,N)))
        b = np.matrix(np.zeros((N,1)))

        idx = 0 # column in M, row is given by item_map
        results = []
        # populate M
        for item in self.inputs:
            M[item_map[item.name],idx] = 1
            results.append(item)
            idx += 1
            
        for recipe in self.recipes:
            for (item,qty) in recipe.ingredients:
                row = item_map[item.name]
                M[row,idx] += -qty
            for (item,qty) in recipe.results:
                row = item_map[item.name]
                M[row,idx] += qty * recipe.effects.prod_mult
            results.append(recipe)
            idx += 1
                
        for item in self.outputs:
            row = item_map[item.name]
            b[row,0] = item.qty_req + item.qty_dep
        
        x = M**-1 * b
        
        for (idx,result) in enumerate(results):
            if type(result) is Item:
                result.qty_dep += x[idx]
            if type(result) is Recipe:
                batches_to_make = x[idx]
                    
                (machines_needed, machines_needed_1x) = result.calc_machines_needed(batches_to_make)
                result.show(machines_needed, machines_needed_1x)
                result.machine.number_needed += machines_needed
                


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

class Module(object):
    def __init__(self,json):
        self.name = json['name']

        def get_bonus(name):
            effect = json['effect']
            return effect[name]['bonus'] if name in effect else 0.0

        self.speed_bonus =   get_bonus('speed')
        self.power_bonus =   get_bonus('consumption')
        self.prod_bonus =    get_bonus('productivity')
        self.pollute_bonus = get_bonus('pollution')

    all={}

    productivity_recipes = []

    @staticmethod
    def load_json(module_json):
        for name in module_json:
            module = Module(module_json[name])
            Module.all[module.name] = module
        Module.productivity_recipes = module_json['productivity-module-3']['limitation']

class Effects(object):
    def __init__(self):
        self.speed_mult = 1.0
        self.power_mult = 1.0
        self.prod_mult = 1.0
        self.pollute_mult = 1.0

    def apply_module(self,module,qty):
        self.speed_mult   += module.speed_bonus * qty
        self.power_mult   += module.power_bonus * qty
        self.prod_mult    += module.prod_bonus * qty
        self.pollute_mult += module.pollute_bonus * qty

    def clip_mults(self):
        self.speed_mult = max(0.2,self.speed_mult)
        self.power_mult = max(0.2,self.power_mult)
        # There are no negative effects for
        # pollution and productivity yet

def load_all_json(filename):
    f = open(filename,"r")
    recipes_json, items_json, module_json, machine_json = json.load(f)
    f.close()

    Module.load_json( module_json )
    Recipe.load_json( recipes_json ) # Need productivity_recipes form Module
    Machine.load_json( machine_json )

    machine_abbreviations = {
    "electric-furnace":     "FURN",
    "chemical-plant":       "CHEM",
    "assembling-machine-3": "ASM3",
    "rocket-silo":          "SILO",
    "oil-refinery":         "RFNR",
    }
    
    for machine in Machine.all:
        if machine.name in machine_abbreviations:
            machine.abbreviation = machine_abbreviations[machine.name]
            
    oil_recipes = [Recipe.all[x] for x in ( #'advanced-oil-processing',
                                            'coal-liquefaction',
                                            'heavy-oil-cracking',
                                            'light-oil-cracking' ) ]
    OilProduction = CompoundRecipe( 'compound-oil-production', oil_recipes )

def main(argv):
    load_all_json("data.json")
    plan_science()

def plan_science():
    scipack1 = ('science-pack-1',1)
    scipack2 = ('science-pack-2',1)
    scipack3 = ('science-pack-3',1)
    milt_scipack = ('military-science-pack',1)
    prod_scipack = ('production-science-pack',1)
    tech_scipack = ('high-tech-science-pack',1)
    space_scipack = ('rocket-part',0.1)
    satellite = ('satellite',.001)

    outputs=[scipack1,scipack2,scipack3,milt_scipack,prod_scipack,tech_scipack,space_scipack,satellite]

    global_scalar = 1.0/1.2 # For productivity modules in labs

    forbidden_recipes = set([
        'basic-oil-processing',
        'coal-liquefaction',
        'advanced-oil-processing',
        'heavy-oil-cracking',
        'light-oil-cracking',
        'solid-fuel-from-petroleum-gas',
        'solid-fuel-from-heavy-oil'])


    # X is a working list of items we need to make
    X = [ Item.all_items[x[0]] for x in outputs ]
    # D is the working list of items we have already made
    D = []

    recipes_used = set()
    raw_materials = set()

    while len(X) > 0:
        item = X.pop(0)
        recipe = item.choose_recipe( forbidden_recipes )
        if recipe is not None:
            recipes_used.add(recipe)
            ingred_names = []
            for (ingred,qty) in recipe.ingredients:
                if ingred not in D and ingred not in X:
                    X.append(ingred)
                ingred_names.append(ingred.name)
        else:
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
        recipe.compute()

    for item in raw_materials:
        stacks_per_min = 60 * item.qty_dep / item.stack_size()
        print( "RAW %8.2f/s (%6.2f stack/min) %s" % (item.qty_dep, stacks_per_min, item.name) )

    for machine in Machine.all:
        if machine.number_needed > 0:
            print( "%d %s" % (machine.number_needed, machine.name) )

if __name__ == '__main__':
    main(sys.argv)
