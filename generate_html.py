#!/usr/bin/env python3
# python 3.10 works

import datetime
import json
import pytz
import requests

"""
This script reads the electricity spot prices for Finland from internet and writes them
to a table as an HTML page. The idea is to run this script once per hour to only display the current
hour and the future, and therefore the fetched price data is saved to a JSON file so that it is fetched
only once per day.
"""

# Configs:
price_data_filename = "price_data_latest.json"
html_output_filename = "spot-hintataulukko.html"
tz = pytz.timezone("Europe/Helsinki")
target_bar_max_width = 23.0  # set the width of the price visualization
show_also_history = False  # when False, makes the table start from the current time
read_prices_from_internet = False # False == automatic

data_json = {}
now = datetime.datetime.now(tz).replace(microsecond=0, second=0, minute=0)

try:
    with open(price_data_filename, 'r') as f:
        data_json = json.load(f)
except:
    read_prices_from_internet = True

# Fetch the price data from internet if necessary:
if read_prices_from_internet or (now.hour >= 14 and (datetime.datetime.strptime(data_json["prices"][0]["startDate"], "%Y-%m-%dT%H:%M:%S.%f%z") - now).total_seconds()/3600 < 20):
    print("Getting new spot price data from internet.")
    r = requests.get(url = "https://api.porssisahko.net/v1/latest-prices.json")
    data_json = r.json()
    
    with open(price_data_filename, 'wb') as f:
        f.write(r.content)

datapoints = data_json["prices"]
datapoints.reverse()  # make ASC order


# Parse the price data into a nested list [[date, hour, price, bar], [date, hour, price, bar], ...]

timestamps_str = []
hours_str = []
prices_float = []
prices_str = []

def translate_date_to_finnish(date: str) -> str:
    return date.replace("Monday", "ma").replace("Tuesday", "ti").replace("Wednesday", "ke").replace("Thursday", "to").replace("Friday", "pe").replace("Saturday", "la").replace("Sunday", "su")

for datapoint in datapoints:
    timestamp = datetime.datetime.strptime(datapoint["startDate"], "%Y-%m-%dT%H:%M:%S.%f%z")
    if show_also_history or timestamp >= now:
        timestamps_str.append(translate_date_to_finnish(timestamp.astimezone(tz).strftime("%A %-d.%-m.")))
        hours_str.append(timestamp.astimezone(tz).strftime("%H"))
        price = round(datapoint["price"], 2)
        prices_float.append(price)
        prices_str.append("{:.2f}".format(price))

max_price = max(prices_float)
width_per_price = target_bar_max_width / max_price

table_data_list = []
date_to_show = ""
for i in range(len(timestamps_str)):
    price_bar = "█" * round(prices_float[i] * width_per_price)
    if date_to_show != timestamps_str[i]:
        date_to_show = timestamps_str[i]
        table_data_list.append([date_to_show, hours_str[i], prices_str[i], price_bar])
    else:
        table_data_list.append(["", hours_str[i], prices_str[i], price_bar])  # do not repeat the same date


# Generate and write the HTML table and file:

def html_table(nested_list, column_names):
    yield '<table class="prices">'
    yield '  <tr><th>'
    yield '    </th><th>'.join(column_names)
    yield '  </th></tr>'
    for columns in nested_list:
        yield '  <tr><td>'
        yield '<td class="pricecol">'.join(('<td class="bargraph">'.join('    </td><td>'.join(columns).rsplit("<td>", 1))).rsplit("<td>", 1))  # hacky way to mark the css to the last and second last columns
        yield '  </td></tr>'
    yield '</table>'

html_page = """
<!doctype html>

<html lang="fi">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="height=device-height, initial-scale=1">
    <title>Sähkön hinta nyt</title>
    <meta name="description" content="Sähkön spot-hinta nykyhetkestä eteenpäin yksinkertaisessa taulukossa ilman mainoksia ja muuta tauhkaa.">
    <meta name="author" content="t-800m101">

    <style>
        body {
            background-color: #f9f9f9;
        }
        table.prices {
            height:85vh;
            border-spacing: 0px;
            font-size:1.7vh;
            white-space: nowrap;
            padding-bottom: 4px;
        }
        tr {
            padding: 0px;
            margin: 0px;
        }
        th, td {
            padding-top: 0px;
            padding-bottom: 0px;
            padding-left: 2px;
            padding-right: 0px;
            text-align: center;
        }
        td.bargraph {
            font-family: 'Courier New', monospace;
            text-align: left;
            color: #1a5fb4;
            letter-spacing: 0px;
        }
        td.pricecol {
            text-align: right;
            padding-right: 2px;
        }
        p{
            font-size:1.3vh;
        }
        button.refresh {
            width: 98%;
            height: 5vh;
        }
        .button {
            font-size: 1.7vh;
            font-weight: bold;
            text-decoration: none;
            background-color: #EFEFEF;
            padding: 2px 6px 2px 6px;
            border-right: 2px solid #101010;
            border-bottom: 2px solid #101010;
            display: block;
            width: 90%;
            height: 5vh;
            text-align: center;
        }
    </style>
</head>
<body>
"""
html_page += '\n'.join(html_table(table_data_list, ["Päivä", "Tunti", "Hinta", "(snt/kWh, alv. 24 %)"]))
html_page += """
<a href="https://htmlpreview.github.io/?https://github.com/t-800m101/spot-hinta/blob/main/spot-hintataulukko.html" class="button">Päivitä</a>
</body>
</html>
"""

with open(html_output_filename, 'w') as f:
    f.write(html_page)
