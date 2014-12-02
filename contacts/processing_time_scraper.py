#!/usr/bin/env python
from bs4 import BeautifulSoup
import logging
from glob import glob
import os
import csv
import re
import requests
import yaml

""" This script scrapes processing times data from foia.gov and dumps
    the data in both the yaml files and `request_time_data.csv`."""


def load_mapping():
    """ Loads mapping of yamls to foia.gov data """

    key = {}
    years = get_years()
    with open('layering_data/data_mapping_key.csv', 'r') as csvfile:
        datareader = csv.reader(csvfile)
        for row in datareader:
            for year in years:
                key["{0}_{1}_{2}".format(row[0], year, row[1])] = \
                    "{0}_{1}_{2}".format(row[2], year, row[1])
    return key


def apply_mapping(data):
    """ Applies mapping to make foia.gov data compatiable with yaml data """

    mapping = load_mapping()
    new_data = {}
    for key in data.keys():
        if key in mapping.keys():
            new_data[mapping[key]] = data[key]
        else:
            new_data[key] = data[key]
    return new_data


def delete_empty_data(data):
    """ Deletes any items with the value `NA` or '' a dictionary """

    keys = list(data.keys())
    for key in keys:
        if data[key] == "NA" or data[key] == '':
            del data[key]
    return data


def append_time_stats(yaml_data, data, year, short_filename):
    """ Appends request time stats to list under key request_time_stats"""

    if not yaml_data.get('request_time_stats'):
        yaml_data['request_time_stats'] = {}
    del data[yaml_data['name'] + year + short_filename]['Agency']
    del data[yaml_data['name'] + year + short_filename]['Year']
    del data[yaml_data['name'] + year + short_filename]['Component']
    yaml_data['request_time_stats'][year.strip("_")] = \
        delete_empty_data(data[yaml_data['name'] + year + short_filename])
    return yaml_data


def patch_yamls(data):
    """ Patches yaml files with average times """

    years = get_years()
    for filename in glob("data" + os.sep + "*.yaml"):
        short_filename = '_%s' % filename.strip('.yaml').strip('/data')
        with open(filename) as f:
            yaml_data = yaml.load(f.read())
        for year in years:
            year = "_%s" % year
            if yaml_data['name'] + year + short_filename in data.keys():
                yaml_data = append_time_stats(
                    yaml_data, data, year, short_filename)
                del data[yaml_data['name'] + year + short_filename]
            for internal_data in yaml_data['departments']:
                key = internal_data['name'] + year + short_filename
                if key in data.keys():
                    internal_data = append_time_stats(
                        internal_data, data, year, short_filename)
        with open(filename, 'w') as f:
            f.write(yaml.dump(
                yaml_data, default_flow_style=False, allow_unicode=True))


def make_column_names():
    """ Generates column names """

    columns = ['Year', 'Agency']
    kinds = ['Simple', 'Complex', 'Expedited Processing']
    measures = ['Average', 'Median', 'Lowest', 'Highest']
    names = []
    for kind in kinds:
        for measure in measures:
            names.append('{0}-{1} No. of Days'.format(kind, measure))
    columns.extend(names)
    return columns


def get_row_data(key, row_data, column_names):
    """
    Collects row data using column names while cleaning up
    anything after the _s
    """

    data = [re.sub("_.*", "", key)]
    for column in column_names:
        data.append(row_data.get(column))
    return data


def write_csv(data):
    """ Writes data to csv """

    column_names = make_column_names()
    with open('request_time_data.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['name'] + column_names)
        for key in sorted(data.keys()):
            writer.writerow(get_row_data(key, data[key], column_names))


def clean_html(html_text):
    """ Converts <1 to 1 in html text"""

    return html_text.replace("><1<", ">less than 1<")


def fetch_page(url, params):
    """
    Returns a cached agency processing time page if it exists,
    otherwise the function creates a cache and returns the html.
    """

    filename = "html/{0}_{1}_timedata.html"
    filename = filename.format(
        params.get('agencyName', "all"), params['requestYear'])
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            return f.read()
    else:
        response = requests.get(url, params=params)
        with open(filename, 'w') as f:
            f.write(response.text)
        return response.text


def zip_and_clean(columns, row):
    """ Converts 0 and Nones to NAs and zips together a row and columns """
    data = dict(zip(columns, row))
    if data.get(''):
        del data['']
    return data


def get_key_values(row_items, columns, year, title):
    """ Parses through each table row and returns a key-value pair """

    row_array = []
    for item in row_items:
        if item.span:
            row_array.append(item.span.text)
        else:
            row_array.append(item.text)
    value = zip_and_clean(columns, row_array)
    key = title + "_%s" % year + "_%s" % value['Agency']
    return key, value


def parse_html(url, params, data):
    """ Gets, caches, and parses html from foia.gov """

    soup = BeautifulSoup(clean_html(fetch_page(url, params)))
    year = params['requestYear']
    table = soup.find("table", {"id": "agencyInfo0"})
    columns = [column.text for column in table.findAll("th")]
    for row in table.findAll("tr"):
        row_items = row.findAll("td")
        if len(row_items) > 2:
            title = row.findAll('span')[1].attrs['title']
            key, value = get_key_values(row_items, columns, year, title)
            data[key] = value
    return data


def get_years():
    """ Gets year data by scraping the data page """

    r = requests.get('http://www.foia.gov/data.html')
    soup = BeautifulSoup(r.text)
    boxes = soup.findAll("input", {"type": "checkbox"})
    years = []
    for box in boxes:
        years.extend(re.findall('\d+', box.attrs.get('name', 'Nothing')))
    return(list(set(years)))


def all_years(url, params, data):
    """ Loops through yearly data """

    for year in get_years():
        params["requestYear"] = year
        data = parse_html(url, params, data)
    return data


def scrape_times():
    """ Loops through foia.gov data for processing time """

    url = "http://www.foia.gov/foia/Services/DataProcessTime.jsp"
    params = {"advanceSearch": "71001.gt.-999999"}
    data = {}
    data = all_years(url, params, data)
    logging.info("compelete: %s", params.get('agencyName', "all"))
    agencies = set([value['Agency'] for value in data.values()])
    for agency in agencies:
        params["agencyName"] = agency
        data = all_years(url, params, data)
        logging.info("compelete: %s", params.get('agencyName', "all"))
    data = apply_mapping(data)
    write_csv(data)
    patch_yamls(data)


if __name__ == "__main__":

    """
    This script scrapes processing times data from foia.gov and dumps
    the data in both the yaml files and `request_time_data.csv.
    """

    logging.basicConfig(level=logging.INFO)
    scrape_times()