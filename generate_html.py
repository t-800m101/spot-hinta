#!/usr/bin/env python3
# python 3.10 works

import datetime
import json
import pytz
import requests
from dataclasses import dataclass, field
from typing import List, Dict

"""
This script reads the electricity spot prices for Finland from internet and writes them
to a table as an HTML page. The idea is to run this script once per hour to only display the current
hour and the future, and therefore the fetched price data is saved to a JSON file so that it is fetched
only once per day.
"""

# Configs:
price_data_filename = "price_data_latest.json"
html_output_filename_prefix = "spot-hintataulukko"
tz = pytz.timezone("Europe/Helsinki")
target_bar_max_width = 20.0  # set the width of the price visualization
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
    assert r.ok, f"Price HTTP response must be less than 400. Was {r.status_code}"
    data_json = r.json()
    
    with open(price_data_filename, 'wb') as f:
        f.write(r.content)


# Parse the data

@dataclass
class DataColumn:
    header: str
    header_css_class: str
    content_css_class: str
    data: List = field(default_factory=list)

    def total_length(self):
        return len(self.data) + 1 # header

def translate_date_to_finnish(date: str) -> str:
    return date.replace("Monday", "ma").replace("Tuesday", "ti").replace("Wednesday", "ke").replace("Thursday", "to").replace("Friday", "pe").replace("Saturday", "la").replace("Sunday", "su")

class PriceTable:
    def __init__(self, price_data: List[dict], target_bar_max_width: float, show_also_history: bool):
        self.price_data = sorted(price_data, key=lambda d: d['startDate'])
        
        self.date_column = DataColumn(header="Päivä", header_css_class="date", content_css_class="date")
        self.hour_column = DataColumn(header="Tunti", header_css_class="hour", content_css_class="hour")
        self.price_column = DataColumn(header="Hinta", header_css_class="price", content_css_class="price")
        self.bar_graph_column = DataColumn(header="(snt/kWh, alv. 24 %)", header_css_class="bargraph", content_css_class="bargraph")
        
        # Find the max price:
        all_prices = []
        for datapoint in self.price_data:
            timestamp = datetime.datetime.strptime(datapoint["startDate"], "%Y-%m-%dT%H:%M:%S.%f%z")
            if show_also_history or timestamp >= now:
                all_prices.append(datapoint["price"])
        self.max_price = max(all_prices)

        # Bar graph scaling based on that:
        self.__bar_width_per_price = target_bar_max_width / self.max_price if self.max_price > 0 else 1

        # Parse rest of the data:
        date_to_show = ""
        for datapoint in self.price_data:
            timestamp = datetime.datetime.strptime(datapoint["startDate"], "%Y-%m-%dT%H:%M:%S.%f%z")
            if show_also_history or timestamp >= now:
                # Parse date
                timestamp_as_string = translate_date_to_finnish(timestamp.astimezone(tz).strftime("%A %-d.%-m."))
                if date_to_show != timestamp_as_string:
                    date_to_show = timestamp_as_string
                    self.date_column.data.append(timestamp_as_string)
                else:
                    self.date_column.data.append("")  # do not repeat the same date

                # Parse hour
                self.hour_column.data.append(timestamp.astimezone(tz).strftime("%H"))
                
                # Parse price
                price = round(datapoint["price"], 2)
                self.price_column.data.append("{:.2f}".format(price))

                # Create bar graph bar
                price_bar_width = round(price * self.__bar_width_per_price)
                if price_bar_width >= 0:
                    self.bar_graph_column.data.append("█" * price_bar_width)
                else:
                    self.bar_graph_column.data.append("◁")

    def length(self):
        assert self.date_column.total_length() == self.hour_column.total_length() == self.price_column.total_length() == self.bar_graph_column.total_length(), "Column lengths must match"
        return self.date_column.total_length()

    def get_html_table_vertical(self):
        table_len = self.length()
        assert table_len > 0, "Table must contain data"
        html = '<table class="prices">'
        for i_row in range(table_len):
            i = i_row - 1
            if i_row == 0:
                # headers:
                html += f'<tr><th class="{self.date_column.header_css_class}">{self.date_column.header}</th><th class="{self.hour_column.header_css_class}">{self.hour_column.header}</th><th class="{self.price_column.header_css_class}">{self.price_column.header}</th><th class="{self.bar_graph_column.header_css_class}">{self.bar_graph_column.header}</th></tr>'
            else:
                html += f'<tr><td class="{self.date_column.content_css_class}">{self.date_column.data[i]}</td><td class="{self.hour_column.content_css_class}">{self.hour_column.data[i]}</td><td class="{self.price_column.content_css_class}">{self.price_column.data[i]}</td><td class="{self.bar_graph_column.content_css_class}">{self.bar_graph_column.data[i]}</td></tr>'
        html += '</table>'
        return html
    
    def get_html_page(self, current_layout_suffix: str, next_layout_suffix: str, orientation: str = "vertical", color_theme: str = "light"):
        if orientation == "vertical":
            self.price_column.header = "Hinta"
            self.bar_graph_column.header = "(snt/kWh, alv. 24 %)"
        else:
            self.price_column.header = ""
            self.bar_graph_column.header = "Hinta<br>(snt/kWh,<br>alv. 24 %)"

        html_page = f"""
            <!doctype html>

            <html lang="fi" {'style="writing-mode: sideways-lr;"' if orientation != "vertical" else ''}>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="{'height=device-height' if orientation == "vertical" else 'width=device-width'}, initial-scale=1">
                <title>Sähkön hinta nyt</title>
                <meta name="description" content="Sähkön spot-hinta nykyhetkestä eteenpäin yksinkertaisessa taulukossa ilman mainoksia ja muuta tauhkaa.">
                <meta name="author" content="t-800m101">

                <style>
                    body {{
                        background-color: {'#f9f9f9' if color_theme == "light" else 'black'};
                        color: {'black' if color_theme == "light" else '#00FF00'};
                    }}
                    table.prices {{
                        {'height:85vh' if orientation == "vertical" else 'width:85vw'};
                        border-spacing: 0px;
                        font-size:1.7{'vh' if orientation == "vertical" else 'vw'};
                        white-space: nowrap;
                        padding-{'bottom' if orientation == "vertical" else 'right'}: 4px;
                    }}
                    tr {{
                        padding: 0px;
                        margin: 0px;
                    }}
                    
                    th {{
                        padding-left: 2px;
                        padding-right: 0px;
                        text-align: {'center' if orientation == "vertical" else 'left'};
                        {'padding-bottom: 4px;' if orientation != "vertical" else 'padding-bottom: 0px;'}
                        {'padding-top: 4vh;' if orientation != "vertical" else 'padding-top: 0px;'}
                        {'writing-mode: horizontal-tb;' if orientation != "vertical" else ''}
                    }}
                    th.bargraph {{
                        font-weight: normal;
                        text-align: left;
                    }}
                    th.price {{
                        {'padding-left: 5px;' if orientation == "vertical" else ''}
                    }}

                    td {{
                        padding-top: 0px;
                        padding-bottom: 0px;
                        padding-left: 2px;
                        padding-right: 0px;
                        text-align: center;
                    }}
                    td.hour {{
                        {'padding-bottom: 4px;' if orientation != "vertical" else ''}
                        {'padding-top: 4vh;' if orientation != "vertical" else ''}
                        {'writing-mode: horizontal-tb;' if orientation != "vertical" else ''}
                    }}
                    td.price {{
                        text-align: right;
                        {'padding-right: 2px;' if orientation == "vertical" else 'padding-top: 2px;'}
                        {'padding-left: 2px;' if orientation == "vertical" else 'padding-bottom: 20px;'}
                    }}
                    td.bargraph {{
                        font-family: 'Courier New', monospace;
                        text-align: left;
                        color: {'#1a5fb4' if color_theme == "light" else '#008000'};
                        letter-spacing: 0px;
                    }}
                    
                    p {{
                        font-size:1.3{'vh' if orientation == "vertical" else 'vw'};
                    }}
                    .button {{
                        font-size: 1.2{'vh' if orientation == "vertical" else 'vw'};
                        font-weight: bold;
                        text-decoration: none;
                        padding-{'top' if orientation == "vertical" else 'left'}: 2px;
                        color: {'black' if color_theme == "light" else 'white'};
                        background-color: {'#EFEFEF' if color_theme == "light" else '#2F4F4F'};
                        border-right: 2px solid #101010;
                        border-bottom: 2px solid #101010;
                        display: inline-block;
                        {'width' if orientation == "vertical" else 'height'}: 70%;
                        {'height' if orientation == "vertical" else 'width'}: {'5vh' if orientation == "vertical" else '4.5vw'};
                        text-align: center;
                    }}
                    .footerbutton {{
                        font-size: 1.2{'vh' if orientation == "vertical" else 'vw'};
                        font-weight: bold;
                        text-decoration: none;
                        padding-{'top' if orientation == "vertical" else 'left'}: 2px;
                        color: {'black' if color_theme == "light" else 'white'};
                        background-color: {'#EFEFEF' if color_theme == "light" else '#2F4F4F'};
                        border-right: 2px solid #101010;
                        border-bottom: 2px solid #101010;
                        display: inline-block;
                        {'width' if orientation == "vertical" else 'height'}: 15%;
                        {'height' if orientation == "vertical" else 'width'}: {'5vh' if orientation == "vertical" else '4.5vw'};
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
            """
        html_page += self.get_html_table_vertical()
        html_page += f"""
            <a href="https://htmlpreview.github.io/?https://github.com/t-800m101/spot-hinta/blob/main/spot-hintataulukko{next_layout_suffix}.html" class="footerbutton">Vaihda<br>ulkoasu</a>
            <a href="https://htmlpreview.github.io/?https://github.com/t-800m101/spot-hinta/blob/main/spot-hintataulukko{current_layout_suffix}.html" class="button">Päivitä<br>taulukko</a>
            </body>
            </html>
            """
        return html_page

data_table = PriceTable(data_json["prices"], target_bar_max_width, show_also_history)
data_table_horizontal = PriceTable(data_json["prices"], 18, show_also_history)


# Generate and write the HTML tables to files:

with open(html_output_filename_prefix + ".html", 'w') as f:
    f.write(data_table.get_html_page("", "_tumma", "vertical", "light"))

with open(html_output_filename_prefix + "_tumma.html", 'w') as f:
    f.write(data_table.get_html_page("_tumma", "_vaaka_tumma", "vertical", "dark"))

with open(html_output_filename_prefix + "_vaaka_tumma.html", 'w') as f:
    f.write(data_table_horizontal.get_html_page("_vaaka_tumma", "_vaaka", "horizontal", "dark"))

with open(html_output_filename_prefix + "_vaaka.html", 'w') as f:
    f.write(data_table_horizontal.get_html_page("_vaaka", "", "horizontal", "light"))




