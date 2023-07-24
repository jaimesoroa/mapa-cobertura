# Import the usual suspects
import pandas as pd
import numpy as np
from shapely.geometry import Point
import geopandas as gpd
from geopandas import GeoDataFrame
import matplotlib as plt
import folium
import mapclassify
import datetime
import plotly.express as px
from math import radians, sin, cos, sqrt, atan2
import csv

# Create all the functions

# Read the input csv
def read_csv():

    # Read csv
    df_logs = pd.read_csv("data/locationsDates.csv", delimiter=',', skiprows=0, low_memory=False)
    # Split the "Date" column into separate date and time to create a readable format
    df_logs[['Date', 'Time_1']] = df_logs['ts'].str.split('T', expand= True)
    df_logs[['Time', 'Time_2']] = df_logs['Time_1'].str.split('Z', expand= True)
    df_logs.drop(columns= ['Time_1', 'Time_2'], inplace= True)

    # Create a new reeadable Date and Time column
    df_logs['Date_Time'] = df_logs['Date'] + ' ' + df_logs['Time']

    # Change the type of the column
    df_logs['Date_Time'] = pd.to_datetime(df_logs['Date_Time'])

    # Create a new "Error" column that will be filled later with different categories of errors depending on the time lapse between logs
    df_logs['Error'] = 0
    
    return df_logs

# Preprocess the points table
def error_column(df_logs, time_step):

    # Create different errors (from 0 to 4) depnding on the length of time lapses (0-10, 10-20, 20-40, 40-60, and more than 1 hour), only when the logId is the same.
    for i in range(len(df_logs)-1):
        if (df_logs.loc[i+1,'Date_Time'] - df_logs.loc[i,'Date_Time']) > datetime.timedelta(minutes=time_step*4) and (df_logs.loc[i+1,'logId'] == df_logs.loc[i,'logId']):
            df_logs.loc[i+1,'Error'] = 3
        elif (df_logs.loc[i+1,'Date_Time'] - df_logs.loc[i,'Date_Time']) > datetime.timedelta(minutes=time_step*2) and (df_logs.loc[i+1,'logId'] == df_logs.loc[i,'logId']):
            df_logs.loc[i+1,'Error'] = 2
        elif (df_logs.loc[i+1,'Date_Time'] - df_logs.loc[i,'Date_Time']) > datetime.timedelta(minutes=time_step) and (df_logs.loc[i+1,'logId'] == df_logs.loc[i,'logId']):
            df_logs.loc[i+1,'Error'] = 1
    
    return df_logs

# Additional preprocess
def create_dict(df_logs):#, max_latitude):

    # Add a new column names "position" to identify each log, and another one "error" to identify new points
    df_logs['Position'] = np.arange(len(df_logs))
    # Remove unwanted columns
    df_logs = df_logs.drop(columns= ['ts', 'geoType', 'clientId', 'Date', 'Time'])
    # Remove points above the max latitude
    # df_logs_south = df_logs[df_logs['lat']<max_latitude]
    # Create a list with all the unique logId
    list_logId = df_logs['logId'].unique()
    # Create the list of dictionaries
    list_dict = df_logs.to_dict(orient='records')
    
    return list_dict, list_logId

# Distance between points
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points on the Earth's surface
    using the Haversine formula.
    """
    R = 6371  # Radius of the Earth in kilometers
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance

# Create points
def add_points(points, margin_distance, list_logs, max_distance):
    """
    Add new points to the route where the distance between consecutive points for points with late signal 
    within the same logId is greater than margin_distance and there are no other points within
    this area.
    """
    
    # Create empty list for the created points, and a variable with the number of input points
    new_points = []
    num_points = len(points)
    
    # Loop that goes over each group of points by logId
    for log in list_logs:
        # Points for each different logId
        num_logs = sum(i['logId'] == log for i in points)
        temp_points = [i for i in points if i['logId'] == log]

        # Points are compared in pairs.
        for i in range(num_logs - 1):
            current_point = temp_points[i]
            next_point = temp_points[i + 1]

            distance = haversine_distance(
                current_point['lat'],
                current_point['lon'],
                next_point['lat'],
                next_point['lon']
            )
            
            '''
            For each pair, if the second point has had a delay in the signal (Error>0), and the
            distance between the pair is bigger than the margin, and smaller than the max distance,
            new points will have to be created
            '''
            if int(next_point['Error']) > 0 and distance > margin_distance and distance < max_distance:
                '''
                # Check if there are no other points within this area
                area_empty = True
                
                # Point is compared with all the other points
                for j in range(num_points - 1):
                    test_point = points[j]
                    test_distance = haversine_distance(
                        next_point['lat'],
                        next_point['lon'],
                        test_point['lat'],
                        test_point['lon']
                    )
                    
                    # A point is detected if the distance is smaller than the margin and it doesn't
                    # belong to that pair being checked.
                    if test_distance <= margin_distance and next_point['Position'] != test_point['Position']:
                        area_empty = False
                        break
                    
                if area_empty:
                '''
                # Calculate the number of new points to be added
                num_new_points = int(distance / margin_distance)
                # Calculate the latitude and longitude differences for each new point
                lat_diff = (next_point['lat'] - current_point['lat']) / (num_new_points + 1)
                lon_diff = (next_point['lon'] - current_point['lon']) / (num_new_points + 1)
                # Generate and add the new points
                for k in range(1, num_new_points + 1):
                    new_latitude = current_point['lat'] + k * lat_diff
                    new_longitude = current_point['lon'] + k * lon_diff
                    area_empty_2 = True
                    # Before each point is created, distance with potential "neighbours" is checked
                    for l in range(num_points):
                        test_point_2 = points[l]
                        test_distance_2 = haversine_distance(
                            new_latitude,
                            new_longitude,
                            test_point_2['lat'],
                            test_point_2['lon']
                        )
                        
                        # Check each new point distance with eachother point, except with themselves.
                        if test_distance_2 <= margin_distance and test_point_2['Position'] != next_point['Position'] and test_point_2['Position'] != current_point['Position']:
                            area_empty_2 = False
                            break
                    # If conditions are met, the new point is added to the list of dictionaries of new points, including all its data, 
                    # that is created based on the original point (same Id and Date_Time, Error+3 and position+100000 to distinguish them).
                    if area_empty_2:
                        new_points.append({'lat': new_latitude, 'lon': new_longitude, 'logId': log, 'Date_Time': next_point['Date_Time'],
                                       'Error': next_point['Error']+3, 'Position': next_point["Position"]+100000})
    
    # Output is a list with the original points plus the new points
    return points + new_points


if __name__ == "__main__":
    
    # Execute all functions to create an output list with created points
    
    # Start inputing the user variables
    
    margin_distance = int(input('What should be the distance margin betwen points, in km?:'))
    max_distance = int(input('What should be the maximum distance between points to consider, in km?:'))
    time_step = int(input('What is the theoretical timestep between sensor signals, in minutes?:'))
    # max_latitude = int(input('What should be the maximum latitude of the points to consider?:'))
    
    # Create the list
    
    df_logs = read_csv()
    df_logs = error_column(df_logs, time_step)
    list_dict, list_logId = create_dict(df_logs)#, max_latitude)
    output_list = add_points(list_dict, margin_distance, list_logId, max_distance)
    
    # Create csv with list of new points
    with open('output/output_list.csv', 'w', encoding='utf8', newline='') as output_file:
        fc = csv.DictWriter(output_file, fieldnames=output_list[0].keys())
        fc.writeheader()
        fc.writerows(output_list)
    output_file.close()
