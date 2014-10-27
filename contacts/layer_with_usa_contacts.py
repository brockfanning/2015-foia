#Update Yaml files with usa_id, description, and acronyms

import yaml
import xlrd
import os
import json
from glob import glob
import re
import logging
#from fuzzywuzzy import fuzz see line 104


ACRONYM_FINDER = re.compile('\((.*?)\)') #re.compile('\((\w+)\)')

def float_to_int_str(number):
    '''converts input to ints and then to strings to clean xls data'''
    try:
        return str(int(float(number)))
    except:
        return number

def extract_acronym(usa_name):
    '''extracts acronyms from a string if there is one'''
    acronym_list = ACRONYM_FINDER.findall(usa_name)
    if len(acronym_list) == 1:
        return acronym_list[0]
    elif len(acronym_list) == 0:
        return ""
    else:
        return "Massive Error"

def return_closest(name_usacontacts,all_usa_data_keys):
    '''uses fuzzy search to look for the closest match (very slow)'''
    name_usacontacts = ACRONYM_FINDER.sub("",name_usacontacts)

    best_match = {'name_usacontacts':"none",
                  'name_all_usa_data':'none',
                  'score':0}

    for name_all_usa_data in all_usa_data_keys:
        score = fuzz.ratio(name_all_usa_data, name_usacontacts)
        if score > best_match['score'] and score >= 80:
            best_match = {'name_usacontacts':name_usacontacts,
                          'name_all_usa_data':name_all_usa_data,
                          'score':score}
    return(best_match)

def load_all_usa_data():
    '''loads data from all_usa_data.json file '''
    with open('usagov-data/all_usa_data.json', 'r') as f:
        all_usa_data = json.loads(f.read())

    data = {}

    for office in all_usa_data:
        if office.get('Language') == "en":

            data[office['Name']] = {
                                'description':office.get(
                                'Description', 'No Description'),
                                'id':office.get('Id', 'No Id'),
                                'acronym_usa_contacts':extract_acronym(office['Name'])
                                }
    return data

def load_usacontacts():
    '''Loads data from usacontacts.xls '''
    data = {}

    xls_path =  "usagov-data/foiaHub-usaContacts-matches.xlsx" #"xls" + os.sep +
    workbook = xlrd.open_workbook(xls_path)
    sheet = workbook.sheet_by_name(workbook.sheet_names()[0])
    header_names = [sheet.cell_value(0, i) for i in range(sheet.ncols)]
    for row_num in range(1, sheet.nrows):
        row = {header_names[i]: sheet.cell_value(row_num, i) for i in range(sheet.ncols)}
        row['usa_id'] = float_to_int_str(row['usa_id'])
        data[row['fh_name']] = row
    return data

def merge_data():
    '''Merges usacontacts.xls and all_usa_data.json'''
    usacontacts = load_usacontacts()
    all_usa_data = load_all_usa_data()
    merged_data = {}
    counter = 0
    found = False


    for name_usacontacts in usacontacts:
        #try to match on names
        if name_usacontacts in all_usa_data.keys():
            usacontacts[name_usacontacts]['description'] = all_usa_data[name_usacontacts]['description']
            found = True

        #try to match on ids
        if found == False:
            current_id = usacontacts[name_usacontacts]['usa_id']
            for name in all_usa_data.keys():
                if all_usa_data[name]['id'] == current_id:
                    usacontacts[name_usacontacts]['description'] = all_usa_data[name]['description']
                    found = True
                    break

        #if all else fails try fuzzy search
        '''DEPRECATED because it doesn't add more matches
        if found == False:

            closest_match = return_closest(name_usacontacts,all_usa_data.keys())
            if closest_match['name_usacontacts'] != "none":
                usacontacts[name_usacontacts]['description'] = all_usa_data[closest_match['name_all_usa_data']]['description']
                usacontacts[name_usacontacts]['usa_id'] = all_usa_data[closest_match['name_all_usa_data']]['id']

        found = False
        '''

    return usacontacts


def patch_yaml():
    '''patches yaml files with usa_id, correct acronyms,
    and descriptions if there is none'''
    data = merge_data()

    #counters for updates
    usa_ids = 0
    acronyms = 0
    descriptions = 0
    elements_traversed = 0

    #loop through the files
    for filename in glob("data" + os.sep + "*.yaml"):
        with open(filename) as f:
            yaml_data = yaml.load(f.read())

            if yaml_data['name'] in data.keys():
                elements_traversed += 1

                if data[yaml_data['name']]['usa_id'] != '':
                    yaml_data['usa_id'] = data[yaml_data['name']]['usa_id']
                    usa_ids += 1

                if data[yaml_data['name']]['acronym'] != "None":
                    yaml_data['abbreviation'] = data[yaml_data['name']]['acronym']
                    acronyms += 1

                if 'description' not in yaml_data.keys():
                    yaml_data['description'] = data[yaml_data['name']].get('description',"No Description")
                    descriptions += 1

                logging.info("%s updated", yaml_data['name'])
                del data[yaml_data['name']]
        #loop through the sub-offices of each file
        for internal_data in yaml_data['departments']:
            if internal_data['name'] in data.keys():

                elements_traversed += 1

                if data[internal_data['name']]['usa_id'] != '':
                    usa_ids += 1

                    internal_data['usa_id'] = data[internal_data['name']]['usa_id']

                if 'description' not in internal_data.keys():
                    internal_data['description'] = data[internal_data['name']].get('description',"No Description")
                    descriptions += 1

                if data[internal_data['name']]['acronym'] != "None":
                    internal_data['abbreviation'] = data[internal_data['name']]['acronym']
                    acronyms += 1

                logging.info("%s updated", internal_data['name'])
                del data[internal_data['name']]

        with open(filename, 'w') as f:
           f.write(yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True))

    logging.info("%s yaml elements_traversed",elements_traversed)
    logging.info("%s acronyms updated",acronyms)
    logging.info("%s descriptions updated",descriptions)
    logging.info("%s usa_ids updated",usa_ids)
    logging.warning("Did not update %s ids", elements_traversed - usa_ids)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    patch_yaml()