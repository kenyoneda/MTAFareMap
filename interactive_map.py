## Bokeh script to generate interactive map of MTA swipe information
# Author: Ken Yoneda
# Date: Dec 7 2016
from bokeh.layouts import row, widgetbox, column, layout
from bokeh.models import ColumnDataSource, DatetimeTickFormatter, PrintfTickFormatter, Range1d
from bokeh.models import HoverTool, PanTool, WheelZoomTool, ColorBar
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.tickers import FixedTicker
from bokeh.models.widgets import RadioButtonGroup, DataTable, TableColumn
from bokeh.models.widgets import DateFormatter, NumberFormatter, Paragraph, Select
from bokeh.plotting import figure, curdoc
from bokeh.tile_providers import WMTSTileSource
from bokeh.palettes import YlOrRd8, viridis

import pandas as pd
import numpy as np
from datetime import date

### Function to convert lat/long coordinates to web Mercator coordinates
## Input: DataFrame, Latitude Column Name, Longitude Column Name
# Credit to jbednar's example notebook on plotting Uber data:
# https://anaconda.org/jbednar/uber/notebook
def lonlat_to_meters(df, lat_name, lon_name):
    lat = df[lat_name]
    lon = df[lon_name]
    origin_shift = 2 * np.pi * 6378137 / 2.0
    df['x'] = lon * origin_shift / 180.0
    df['y'] = np.log(np.tan((90 + lat) * np.pi / 360.0)) / (np.pi / 180.0)
    df['y'] = df['y'] * origin_shift / 180.0

### Function that calculates percentage of total swipes given a dictionary of dataframes
## Input: Dictionary of DataFrames
## Returns: Arrays containing percentages for each type of metrocard
def overall_percents(df_dict):
    ff_percents, sevenD_percents, thirtyD_percents = [], [], []

    for df in df_dict.values():
        total_swipes = df['FF'].sum() + df['7D_UNL'].sum() + df['30D_UNL'].sum()
        ff_swipes = (df['FF'].sum() / total_swipes) * 100
        sevenD_swipes = (df['7D_UNL'].sum() / total_swipes) * 100
        thirtyD_swipes = (df['30D_UNL'].sum() / total_swipes) * 100
        ff_percents.append(ff_swipes)
        sevenD_percents.append(sevenD_swipes)
        thirtyD_percents.append(thirtyD_swipes)

    return ff_percents, sevenD_percents, thirtyD_percents

### Function to read in data and convert lat/long to web mercator given a list of csv's
## Input: List of csv filenames
## Returns: Dictionary of csv files
def process_data(csv_list):
    df_dict = {}

    for i in range(len(csv_list)):
        df = pd.read_csv(csv_list[i])
        lonlat_to_meters(df, 'LATITUDE', 'LONGITUDE') # Coordinate conversion
        df_dict[i] = df

    return df_dict

### MAIN
# Read in data
csv_list = ['pricehike1_final.csv', 'pricehike2_final.csv', 'pricehike3_final.csv', 'pricehike4_final.csv']
df_dict = process_data(csv_list)
df = df_dict[0] # Use for initial   
card_type_dict = {0 : 'FF_PCT', 1 : '7D_UNL_PCT', 2 : '30D_UNL_PCT'}

### PLOT SETTINGS
NYC = x_range, y_range = ((df.x.min(), df.x.max()), (df.y.min(), df.y.max()))
plot_width, plot_height = int(1000), int(800)

### BASEMAP URL
url = 'http://a.basemaps.cartocdn.com/dark_all/{Z}/{X}/{Y}.png'
attribution = "Map tiles by Carto, under CC BY 3.0. Data by OpenStreetMap, under ODbL"

### TOOL SETTINGS
hover = HoverTool(
    tooltips=[
        ('STN', '@STATION'),
        ('LINES', '@LINES'),
        ('Full Fare %', '@FF_PCT'),
        ('7D UNL %', '@7D_UNL_PCT'),
        ('30D UNL %', '@30D_UNL_PCT')
    ])
tools = [PanTool(), WheelZoomTool(), hover]

# Create map with above settings
fig = figure(tools=tools, toolbar_location='left', x_range=x_range, y_range=y_range,
                plot_width=plot_width, plot_height=plot_height)
fig.add_tile(WMTSTileSource(url=url, attribution=attribution))
fig.axis.visible = False
fig.xgrid.grid_line_color = None
fig.ygrid.grid_line_color = None

# Create initial plot
_, bins = pd.qcut(df['FF_PCT'], 5, retbins=True)
colors = YlOrRd8[0:5][::-1]
sources = {}

for i in range(len(colors)):
    mask = df[(df['FF_PCT'] > bins[i]) & (df['FF_PCT'] < bins[i + 1])]
    cds = ColumnDataSource(mask)
    sources[i] = cds
    fig.circle('x', 'y', line_color=None, fill_color=colors[i], size=5, source=sources[i])

# ColorBar Legend
color_mapper = LinearColorMapper(palette=colors, low=0, high=100)
color_bar = ColorBar(color_mapper=color_mapper, ticker=FixedTicker(ticks=[0, 20, 40, 60, 80, 100]),
                        label_standoff=12, border_line_color=None, location=(0,0), title='Percentile')
fig.add_layout(color_bar, 'right')

## Callback function for widgets
# Change data source (i.e. which DataFrame to use)
def callback_change_dataframe(new):
    # New datasources
    global df_dict, card_type_dict
    card_type = card_type_dict[metrocard_type_buttons.active] # Get card type
    df = df_dict[price_period_buttons.active] # Update dataframe source

    if (subway_line_select.value != 'ALL'):
        df = df[df.LINES.str.contains(subway_line_select.value)]

    # Update Map
    _, bins = pd.qcut(df[card_type], 5, retbins=True)

    for i in range(len(colors)):
        new_data = dict()
        mask = df[(df[card_type] > bins[i]) & (df[card_type] < bins[i + 1])]
        cds = ColumnDataSource.from_df(mask)
        sources[i].data = cds

    # Update Tables
    top_five = df.sort_values(card_type, ascending=False).head(5)[['STATION', card_type, 'LINES']]
    top_five_dict = dict(stations=top_five['STATION'], lines=top_five['LINES'],
                            percents=top_five[card_type], rank=list(range(1, 6)))
    top_five_data_source.data = top_five_dict

    bot_five = df.sort_values(card_type).head(5)[['STATION', card_type, 'LINES']]
    bot_five_dict = dict(stations=bot_five['STATION'], lines=bot_five['LINES'],
                            percents=bot_five[card_type], rank=list(range(1, 6)))
    bot_five_data_source.data = bot_five_dict

# Filter out and plot single subway line's stations
def callback_subway_line_filter(attr, old, new):
    global df_dict, card_type_dict
    card_type = card_type_dict[metrocard_type_buttons.active] # Get card type
    df = df_dict[price_period_buttons.active] # Update dataframe source

    # Filter out single subway line if ALL not selected
    if (new != 'ALL'):
        df = df[df.LINES.str.contains(new)]

    # Update Map
    _, bins = pd.qcut(df[card_type], 5, retbins=True)

    for i in range(len(colors)):
        new_data = dict()
        mask = df[(df[card_type] > bins[i]) & (df[card_type] < bins[i + 1])]
        cds = ColumnDataSource.from_df(mask)
        sources[i].data = cds

    # Update Tables
    top_five = df.sort_values(card_type, ascending=False).head(5)[['STATION', card_type, 'LINES']]
    top_five_dict = dict(stations=top_five['STATION'], lines=top_five['LINES'], 
                            percents=top_five[card_type], rank=list(range(1, 6)))
    top_five_data_source.data = top_five_dict

    bot_five = df.sort_values(card_type).head(5)[['STATION', card_type, 'LINES']]
    bot_five_dict = dict(stations=bot_five['STATION'], lines=bot_five['LINES'],
                            percents=bot_five[card_type], rank=list(range(1, 6)))
    bot_five_data_source.data = bot_five_dict

## Add widgets and corresponding callback functions
price_period_buttons = RadioButtonGroup(active=0,
    labels=['Period 1', 'Period 2', 'Period 3', 'Period 4'])
price_period_buttons.on_click(callback_change_dataframe)

metrocard_type_buttons = RadioButtonGroup(active=0,
    labels=['Full Fare', '7-Day Unlimited', '30-Day Unlimited'])
metrocard_type_buttons.on_click(callback_change_dataframe)

line_list = ['ALL', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'J', 'L', 'M', 'N', 'Q', 'R', 'S', 'Z',
            '1', '2', '3', '4', '5', '6', '7']
subway_line_select = Select(title="Subway Line:", value="ALL", options=line_list)
subway_line_select.on_change("value", callback_subway_line_filter)

## Add table showing price hike information
start_dates = [date(2009, 6, 28), date(2010, 12, 30), date(2013, 3, 3), date(2015, 3, 22)]
end_dates = [date(2010, 12, 29), date(2013, 3, 2), date(2015, 3, 21), date(2017, 1, 1)]
prices = [2.25, 2.25, 2.50, 2.75]
pct_change = pd.Series(prices).pct_change()
hike_data = dict(start_dates=start_dates, end_dates=end_dates, prices=prices, pct_change=pct_change)
hike_data_source = ColumnDataSource(hike_data)
columns = [
    TableColumn(field='start_dates', title='Start Date', formatter=DateFormatter(format='m/d/yy')),
    TableColumn(field='end_dates', title='End Date', formatter=DateFormatter(format='m/d/yy')),
    TableColumn(field='prices', title='Price', formatter=NumberFormatter(format='$0,0.00')),
    TableColumn(field='pct_change', title='% Change', formatter=NumberFormatter(format='+0.00%'))
    ]
hike_table = DataTable(source=hike_data_source, columns=columns, row_headers=False, sortable=False,
                        selectable=False, editable=False, width=400, height=150)

## Plot a line chart representing percentage of total swipes over time
ff_percents, sevenD_percents, thirtyD_percents = overall_percents(df_dict)
line_colors = viridis(11)[::-1]
line_chart = figure(plot_width=400, plot_height=400, x_axis_type='datetime', toolbar_location=None, title='% of Total Swipes',
          x_axis_label='Year')
x = [date(2010, 12, 29), date(2013, 3, 2), date(2015, 3, 21), date(2016, 12, 31)]
line_chart.line(x, ff_percents, line_width=5, line_color=line_colors[0], legend='Full Fare')
line_chart.line(x, sevenD_percents, line_width=5, line_color=line_colors[3], legend='7D UNL')
line_chart.line(x, thirtyD_percents, line_width=5, line_color=line_colors[6], legend='30D UNL')
line_chart.circle(x, ff_percents, fill_color='white', size=7)
line_chart.circle(x, sevenD_percents, fill_color='white', size=7)
line_chart.circle(x, thirtyD_percents, fill_color='white', size=7)
line_chart.xaxis.formatter = DatetimeTickFormatter(years='%Y')
line_chart.yaxis.formatter = PrintfTickFormatter(format='%f%%')
line_chart.xaxis.major_label_orientation = 3.14/4
line_chart.set(y_range=Range1d(0, 75))

## Add table showing top 5 stations (% of {FF, 7D, 30D} swipes)
top_five = df.sort_values('FF_PCT', ascending=False).head(5)[['STATION', 'FF_PCT', 'LINES']]
top_five_dict = dict(stations=top_five['STATION'], lines=top_five['LINES'],
                        percents=top_five['FF_PCT'], rank=list(range(1, 6)))
top_five_data_source = ColumnDataSource(top_five_dict)
columns = [
    TableColumn(field='rank', title='Rank', width=20),
    TableColumn(field='stations', title='Station', width=200),
    TableColumn(field='lines', title='Lines', width=100),
    TableColumn(field='percents', title='%', formatter=NumberFormatter(format='0.00%'), width=100)
    ]
top_five_table = DataTable(source=top_five_data_source, columns=columns, row_headers=False, sortable=False,
                            selectable=False, editable=False)
top_five_title = Paragraph(text='Top 5 Stations', width=600, height=25)

## Add table showing bottom 5 stations (% of {FF, 7D, 30D} swipes)
bot_five = df.sort_values('FF_PCT').head(5)[['STATION', 'FF_PCT', 'LINES']]
bot_five_dict = dict(stations=bot_five['STATION'], lines=bot_five['LINES'],
                        percents=bot_five['FF_PCT'], rank=list(range(1, 6)))
bot_five_data_source = ColumnDataSource(bot_five_dict)
columns = [
    TableColumn(field='rank', title='Rank', width=20),
    TableColumn(field='stations', title='Station', width=200),
    TableColumn(field='lines', title='Lines', width=100),
    TableColumn(field='percents', title='%', formatter=NumberFormatter(format='0.00%'), width=100)
    ]
bot_five_table = DataTable(source=bot_five_data_source, columns=columns, row_headers=False, sortable=False,
                            selectable=False, editable=False)
bot_five_title = Paragraph(text='Bottom 5 Stations', width=600, height=25)

## Add description
description_text = """This map shows the usage rates of different types of MetroCards 
    (i.e. Full Fare, 7-Day Unlimited, 30-Day Unlimited) at every station, which are represented by the dots. 
    For every station, if you hover over the dot, you can see information about the percentage of swipes at 
    the station for each MetroCard type. 
    The color of the dot represents the percentile rank of each station in terms of usage
    (see the legend on the right of the map). The darker the color, the more a station registers 
    swipes for that type of MetroCard (as a percentage). 
    In addition, there are two tables at the bottom which show the top/bottom 5 stations
    in terms of usage - the top 5 stations will appear dark red while the bottom 5 stations will appear 
    bright yellow. There is also a line graph that represents overall percent of total swipes for all 
    stations over time. 
    Lastly, there is a table with price information (Full Fare) for different periods of time,
    which corresponds to the time period filter buttons at the top."""
description = Paragraph(text=description_text, width=1300)

## LAYOUT
widgets = widgetbox(price_period_buttons, metrocard_type_buttons, subway_line_select, width=400, height=200)
column1 = layout([[widgets], [hike_table], [line_chart]])
table1 = layout([top_five_title], [top_five_table])
table2 = layout([bot_five_title], [bot_five_table])
layout = layout([[description], [column1, fig], [table1, Paragraph(width=50), table2]])
            
# Add to document
curdoc().add_root(layout)
curdoc().title = 'Interactive Map of MTA Swipe Information'